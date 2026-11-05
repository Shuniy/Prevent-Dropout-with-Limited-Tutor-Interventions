"""Staged Step 6 evaluation using the existing closed-loop environment and policies."""

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import time
import tomllib

import numpy as np
from scipy.stats import spearmanr

from ..intervention.feedback_notes import NoteQuality
from ..school.closed_loop_controller import ClosedLoopCMDPController
from ..school.cmdp_scenarios import build_school
from ..school.constrained_planner import ConstrainedAllocationPlanner
from ..school.fairness_planner import FairnessPlanner
from ..school.feedback_validation import validate_feedback_episode
from ..school.observation_model import ObservationConfig
from ..school.retention_value import estimate_all_student_benefits
from ..school.robust_fair_planner import FairRobustPlanner
from ..school.scenario_config import ScenarioConfig
from ..school.uncertainty_scenarios import UncertaintyScenarioConfig
from ..utils.constants import DEFAULT_STUDENT_DATA_PATH, PROJECT_ROOT
from .paired_statistics import paired_comparison
from .scorecards import episode_summary, score_episode

CONFIG = PROJECT_ROOT / "configs/research_evaluation_v1.toml"
PROTOCOL = PROJECT_ROOT / "docs/research_evaluation_protocol.md"
TABLES = ("belief_metrics", "risk_metrics", "group_access", "fairness_shortfalls",
          "retention_by_group", "monthly_results", "solver_diagnostics", "mentor_workload")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path, rows):
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nnot_executed\n", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_config(path=CONFIG):
    with Path(path).open("rb") as stream:
        config = tomllib.load(stream)
    development = set(config["evaluation"]["development_seeds"])
    heldout = set(config["evaluation"]["evaluation_seeds"])
    if development & heldout or not development or not heldout:
        raise ValueError("development and evaluation seeds must be nonempty and disjoint")
    for name in ("secondary_seeds", "live_seeds"):
        if not set(config["evaluation"][name]) <= heldout:
            raise ValueError(f"{name} must be a subset of frozen evaluation seeds")
    return config


def fingerprint():
    paths = sorted((PROJECT_ROOT / "src").rglob("*.py"))
    paths += sorted((PROJECT_ROOT / "scripts").glob("*.py"))
    paths += [CONFIG, PROTOCOL, DEFAULT_STUDENT_DATA_PATH, PROJECT_ROOT / "requirements.txt"]
    return {str(p.relative_to(PROJECT_ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}


def freeze(output, amendment=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    versions = sorted(output.glob("configuration_manifest*.json"))
    current = fingerprint()
    if versions:
        previous = json.loads(versions[-1].read_text())
        if previous["file_hashes"] == current:
            return previous
        if not amendment:
            raise ValueError("frozen inputs changed: supply --amend with an explicit protocol amendment")
    config = load_config()
    versions_count = len(versions) + 1
    manifest = {"version": versions_count, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": config, "file_hashes": current, "amendment": amendment,
        "previous_manifest": versions[-1].name if versions else None,
        "heldout_already_executed": any((output / "episodes").glob("evaluation*")),
        "python": platform.python_version(), "declared_python_support": ">=3.12,<3.14",
        "packages": {name: importlib.metadata.version(name) for name in
                     ("numpy", "scipy", "matplotlib", "pandas", "jsonschema")},
        "solver": {"backend": "scipy.optimize.milp/HiGHS", "mip_rel_gap": 0,
            "objective_tolerance": FairnessPlanner.OBJECTIVE_TOLERANCE,
            "fairness_tolerance": FairnessPlanner.FAIRNESS_TOLERANCE,
            "monthly_seconds": config["scenario"]["planner_time_limit"]},
        "streams": {"population": "fixed enrolled source prefix; no population resampling",
            "transition": "SHA256(seed,student,month,environment_transition)",
            "observation": "SHA256(seed,student,month,observation:mechanism)",
            "note": "SHA256(seed,student,month,note:mechanism)",
            "policy": "deterministic canonical tie-breaking; no random policy draws"}}
    name = "configuration_manifest.json" if not versions else f"configuration_manifest_v{versions_count:03d}.json"
    write_json(output / name, manifest)
    if not versions:
        write_json(output / "protocol.json", {"version": config["version"],
            "protocol_text": PROTOCOL.read_text(), "configuration": config,
            "protocol_sha256": current[str(PROTOCOL.relative_to(PROJECT_ROOT))]})
        (output / "research_evaluation_protocol_frozen.md").write_bytes(PROTOCOL.read_bytes())
    return manifest


def checked_manifest(output):
    versions = sorted(Path(output).glob("configuration_manifest*.json"))
    if not versions:
        raise ValueError("freeze the protocol/configuration before running experiments")
    manifest = json.loads(versions[-1].read_text())
    if manifest["file_hashes"] != fingerprint():
        raise ValueError("frozen source/configuration changed; record an explicit --amend before execution")
    return manifest


def make_policy(config, name, *, radius=None):
    scenario = ScenarioConfig(**config["scenario"])
    from ..school.transition_model import programme_matrix
    kwargs = {"time_limit": scenario.planner_time_limit,
        "failure_mode": scenario.planner_failure_mode,
        "treatment_matrix": programme_matrix(scenario.effect_strength)}
    if name == "ResourceOnlyPoint":
        return ConstrainedAllocationPlanner(**kwargs)
    fair = {"minimum_access": scenario.fairness_min_access,
        "window_months": scenario.fairness_window,
        "grouping_attribute": scenario.fairness_grouping_attribute,
        "allow_shortfall": scenario.fairness_allow_shortfall, **kwargs}
    if name == "FairPoint":
        return FairnessPlanner(**fair)
    if name != "FairRobust":
        raise ValueError("unknown research policy")
    uncertainty = dict(config["uncertainty"])
    if radius is not None:
        uncertainty["radius"] = radius
    return FairRobustPlanner(uncertainty_config=UncertaintyScenarioConfig(**uncertainty), **fair)


def make_controller(config, name, mode, seed, *, setting="primary", budget=None,
                    effect=None, radius=None, missingness=None, extractor=None, sparse=False):
    parameters = dict(config["scenario"], seed=seed)
    if budget is not None:
        parameters["budget"] = budget
    if effect is not None:
        parameters["effect_strength"] = effect
    scenario = ScenarioConfig(**parameters)
    policy_config = {**config, "scenario": asdict(scenario)}
    school = build_school(scenario)
    quality = NoteQuality(**config["notes"])
    qualities = {}
    if mode in ("d_matched", "noisy_notes"):
        qualities = {s.student_id: NoteQuality(**config[
            "primary_notes_true" if s.disadvantage_proxy_group is True else "primary_notes_false"])
            for s in school.students}
    if missingness is not None:
        quality = replace(quality, omission_probability=missingness)
        qualities = {s.student_id: quality for s in school.students}
    # D-matched is the existing note-matched mode with the exact D note channel.
    controller_mode = "b_matched" if mode == "d_matched" else mode
    return ClosedLoopCMDPController(school.create_cmdp_environment(config=scenario),
        make_policy(policy_config, name, radius=radius), mode=controller_mode,
        extractor=extractor, observation_config=ObservationConfig(**config["observation"]),
        note_quality=quality, note_quality_by_student=qualities,
        max_notes_per_month=config["evaluation"]["llm_notes_per_month"] if sparse else None)


def digest_controller(controller):
    """Reproducible policy-relevant trace; runtime diagnostics are excluded."""
    payload = {"truth": controller.evaluator_truth,
        "snapshots": [asdict(s) for s in controller.snapshots],
        "decisions": [{k: row[k] for k in ("month", "admitted_ids", "benefits",
            "remaining_budget_before", "remaining_budget_after")} for row in controller.decisions]}
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def save_trace(controller, destination):
    """Compressed complete inputs/outputs, preserving previous Step1–5 outputs."""
    payload = {"configuration": asdict(controller.environment.config),
        "mode": controller.mode, "note_quality": asdict(controller.note_quality),
        "note_quality_by_student": {sid: asdict(q) for sid, q in controller.note_quality_by_student.items()},
        "observations": [asdict(e) for e in controller.events],
        "registry": [asdict(e) for e in controller.registry],
        "notes": [asdict(n) for n in controller.notes],
        "extracted": [asdict(b) for b in controller.batches],
        "snapshots": [asdict(s) for s in controller.snapshots],
        "decisions": controller.decisions, "truth_evaluator_only": controller.evaluator_truth,
        "extraction_failures": controller.failures,
        "extraction_attempts": controller.extraction_attempts,
        "risk_estimates": [asdict(r) for r in controller.risks]}
    with gzip.open(destination / "trace.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(payload, stream, allow_nan=False)


def run_one(output, config, manifest, phase, name, mode, seed, **options):
    settings = {k: v for k, v in options.items() if k != "extractor"}
    setting = settings.pop("setting", "primary")
    identity = {"phase": phase, "policy": name, "mode": mode, "seed": seed,
                "setting": setting, **settings, "manifest_version": manifest["version"]}
    token = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    destination = Path(output) / "episodes" / f"{phase}_{name}_{mode}_{seed}_{token}"
    if (destination / "summary.json").exists():
        return json.loads((destination / "summary.json").read_text())
    execution = {"policy": name, "mode": mode, "seed": seed,
        "manifest_version": manifest["version"],
        "budget": options.get("budget", config["scenario"]["budget"]),
        "effect": options.get("effect", config["scenario"].get("effect_strength", 1.0)),
        "radius": (options.get("radius", config["uncertainty"]["radius"])
                   if name == "FairRobust" else None),
        "missingness": options.get("missingness"), "sparse": options.get("sparse", False)}
    execution_key = sha256(json.dumps(execution, sort_keys=True).encode()).hexdigest()
    # A default sensitivity cell is exactly the already executed primary world.
    # Reference its immutable trace instead of solving or inferring again.
    for previous in sorted((Path(output) / "episodes").glob("*/summary.json")):
        saved = json.loads(previous.read_text())
        if saved.get("execution_key") == execution_key:
            summary = {**saved, **identity, "reused_from": str(previous.relative_to(output))}
            destination.mkdir(parents=True, exist_ok=True)
            write_json(destination / "summary.json", summary)
            return summary
    controller = make_controller(config, name, mode, seed, **options)
    started = time.perf_counter()
    controller.run_episode()
    validate_feedback_episode(controller)
    scores = score_episode(controller)
    summary = {**episode_summary(controller, name, mode, setting, seed), **identity,
        "wall_seconds": time.perf_counter() - started,
        "trace_digest": digest_controller(controller),
        "execution_key": execution_key,
        "extraction_failures": len(controller.failures),
        "note_count": len(controller.notes),
        "trace_path": str(destination.relative_to(output) / "trace.json.gz")}
    destination.mkdir(parents=True, exist_ok=True)
    save_trace(controller, destination)
    for table, rows in scores.items():
        if table.endswith("records"):
            # Fine-grained records for calibration/failure analysis; compressed.
            with gzip.open(destination / f"{table}.json.gz", "wt", encoding="utf-8") as stream:
                json.dump(rows, stream, allow_nan=False)
        else:
            write_json(destination / f"{table}.json", rows)
    write_json(destination / "summary.json", summary)  # completion marker last
    print(f"{phase} {setting}: {name}/{mode} seed={seed} retention={summary['retention_rate']:.3f}", flush=True)
    return summary


def run_pairs(output, config, manifest, phase, seeds, mode="d_matched", **options):
    results = []
    for seed in seeds:
        for name in ("FairPoint", "FairRobust"):
            results.append(run_one(output, config, manifest, phase, name, mode, seed, **options))
    return results


def pilot(output, config, manifest):
    rows = run_pairs(output, config, manifest, "development", config["evaluation"]["development_seeds"])
    # Exact reproducibility and reverse-order checks use a small full-horizon world.
    small = {**config, "scenario": {**config["scenario"], "num_students": 12}}
    expected, order = {}, []
    for name in ("FairPoint", "FairRobust", "FairRobust", "FairPoint"):
        controller = make_controller(small, name, "d_matched", 0).run_episode()
        validate_feedback_episode(controller)
        digest = digest_controller(controller)
        if name in expected and digest != expected[name]:
            raise AssertionError("policy execution order changed deterministic trace")
        expected[name] = digest
        order.append(name)
    null_truth = []
    for name in ("FairPoint", "FairRobust", "ResourceOnlyPoint"):
        controller = make_controller(small, name, "d_matched", 0, effect=0).run_episode()
        null_truth.append(controller.evaluator_truth)
    if not all(truth == null_truth[0] for truth in null_truth):
        raise AssertionError("alpha0 trajectories differ despite coupled transition draws")
    write_json(Path(output) / "development_gate.json", {"passed": True, "episodes": len(rows),
        "manifest_version": manifest["version"], "policy_order": order,
        "repeat_trace_digests": expected, "null_effect_exact_truth_equal": True,
        "independent_seed_count": len(config["evaluation"]["development_seeds"])})


def require_pilot(output, manifest):
    path = Path(output) / "development_gate.json"
    gate = json.loads(path.read_text()) if path.exists() else {}
    if not gate.get("passed") or gate.get("manifest_version") != manifest["version"]:
        raise ValueError("run the development pilot under the active frozen configuration first")


def primary(output, config, manifest):
    require_pilot(output, manifest)
    rows = run_pairs(output, config, manifest, "evaluation", config["evaluation"]["evaluation_seeds"])
    write_json(Path(output) / "primary_complete.json", {"manifest_version": manifest["version"],
        "n_paired_seeds": len(config["evaluation"]["evaluation_seeds"]), "episodes": len(rows)})


def secondary(output, config, manifest):
    require_pilot(output, manifest)
    primary_path = Path(output) / "primary_complete.json"
    if (not primary_path.exists() or
            json.loads(primary_path.read_text()).get("manifest_version") != manifest["version"]):
        raise ValueError("execute primary comparison before secondary experiments")
    seeds = config["evaluation"]["secondary_seeds"]
    for mode in ("oracle", "structured", "b_matched"):
        run_pairs(output, config, manifest, "secondary", seeds, mode=mode, setting="information")
    for label, parameter, values in (
        ("missingness", "missingness", config["evaluation"]["missingness_levels"]),
        ("budget", "budget", config["evaluation"]["budgets"]),
        ("effect", "effect", config["evaluation"]["effect_strengths"]),
        ("uncertainty", "radius", config["evaluation"]["uncertainty_radii"])):
        for value in values:
            rows = run_pairs(output, config, manifest, "secondary", seeds,
                setting=f"{label}_{value:g}", **{parameter: value})
            if label == "effect" and value == 0:
                for seed in seeds:
                    pair = [row for row in rows if row["seed"] == seed]
                    truths = []
                    for row in pair:
                        with gzip.open(Path(output) / row["trace_path"], "rt") as stream:
                            truths.append(json.load(stream)["truth_evaluator_only"])
                    if truths[0] != truths[1]:
                        raise AssertionError("held-out alpha0 truth trajectories differ")
    for seed in seeds:
        run_one(output, config, manifest, "secondary", "ResourceOnlyPoint", "d_matched", seed,
                setting="fairness_ablation")
    snapshot_comparisons(output, config, seeds)


def snapshot_comparisons(output, config, seeds):
    rows = []
    for seed in seeds:
        for mode, sparse in (("structured", False), ("b_matched", False), ("d_matched", False)):
            controller = make_controller(config, "FairPoint", mode, seed)
            controller.initialize()
            state = controller.prepare_decision_snapshot(1)
            left = make_policy(config, "FairPoint").plan(state)
            right = make_policy(config, "FairRobust").plan(state)
            l_ids, r_ids = {a.student_id for a in left.assignments}, {a.student_id for a in right.assignments}
            l_pairs, r_pairs = {(a.student_id, a.mentor_id) for a in left.assignments}, {(a.student_id, a.mentor_id) for a in right.assignments}
            rows.append({"seed": seed, "mode": mode, "comparison": "FairRobust_minus_FairPoint",
                "month": 1, "same_snapshot": True, "same_feasible_set": True,
                "selection_disagreement_rate": len(l_ids ^ r_ids) / len(state.students),
                "selection_jaccard": len(l_ids & r_ids) / len(l_ids | r_ids) if l_ids | r_ids else 1,
                "mentor_assignment_jaccard": len(l_pairs & r_pairs) / len(l_pairs | r_pairs) if l_pairs | r_pairs else 1,
                "point_count": len(l_ids), "robust_count": len(r_ids),
                "point_nominal_objective": left.objective, "robust_nominal_objective": right.objective})
    write_csv(Path(output) / "snapshot_assignment_comparison.csv", rows)


def live(output, config, manifest):
    require_pilot(output, manifest)
    from .extraction_evaluation import make_cached_extractor
    extractor = make_cached_extractor(Path(output) / "extraction" / "cache", **config["llm"])
    for seed in config["evaluation"]["live_seeds"]:
        for mode in ("b_matched", "llm_notes", "d_matched", "noisy_notes"):
            run_pairs(output, config, manifest, "live", [seed], mode=mode,
                      setting="sparse_real_llm", sparse=True, extractor=extractor)
    write_json(Path(output) / "live_runtime.json", {"new_inference_calls": extractor.calls,
        "extractor_version": extractor.version, "configuration": extractor.configuration,
        "n_world_seeds": len(config["evaluation"]["live_seeds"]),
        "note": "Temperature0 is not a bitwise determinism guarantee; cache replay is deterministic."})
    live_snapshot_comparisons(output, config, extractor)


def live_snapshot_comparisons(output, config, extractor):
    rows = []
    for seed in config["evaluation"]["live_seeds"]:
        for gold_mode, llm_mode in (("b_matched", "llm_notes"), ("d_matched", "noisy_notes")):
            controls = []
            for mode in (gold_mode, llm_mode):
                controller = make_controller(config, "FairPoint", mode, seed, extractor=extractor, sparse=True)
                controller.initialize()
                state = controller.prepare_decision_snapshot(1)
                allocation = make_policy(config, "FairPoint").plan(state)
                controls.append((controller, state, allocation))
            left, right = controls
            if left[0].notes != right[0].notes:
                raise AssertionError("gold/LLM snapshot notes differ")
            lbenefit = estimate_all_student_benefits(left[1], left[0].policy.wait_matrix, left[0].policy.programme_matrix)
            rbenefit = estimate_all_student_benefits(right[1], right[0].policy.wait_matrix, right[0].policy.programme_matrix)
            ids = sorted(lbenefit.keys() | rbenefit.keys())
            lassign = {a.student_id: a.mentor_id for a in left[2].assignments}
            rassign = {a.student_id: a.mentor_id for a in right[2].assignments}
            lrisks = {r.student_id: r.probability for r in left[1].risk_estimates}
            rrisks = {r.student_id: r.probability for r in right[1].risk_estimates}
            for a, b in zip(left[1].students, right[1].students):
                rows.append({"seed": seed, "gold_mode": gold_mode, "llm_mode": llm_mode,
                    "month": 1, "student_id": a.student_id, "same_notes": True,
                    "belief_l1": sum(abs(x-y) for x,y in zip(a.condition_probabilities,b.condition_probabilities)),
                    "risk_difference": rrisks[a.student_id]-lrisks[a.student_id],
                    "benefit_difference": rbenefit.get(a.student_id,0)-lbenefit.get(a.student_id,0),
                    "eligibility_changed": a.eligible != b.eligible,
                    "selected_gold": a.student_id in lassign, "selected_llm": a.student_id in rassign,
                    "mentor_changed": lassign.get(a.student_id) != rassign.get(a.student_id)})
            ranks = spearmanr([lbenefit.get(sid,0) for sid in ids], [rbenefit.get(sid,0) for sid in ids])
            write_json(Path(output) / f"live_snapshot_rank_{seed}_{gold_mode}.json",
                {"spearman_average_ties": float(ranks.statistic) if np.isfinite(ranks.statistic) else None,
                 "same_notes": True, "cutoff": 1, "seed": seed})
    write_csv(Path(output) / "extraction_snapshot_comparison.csv", rows)


def aggregate(output):
    output = Path(output)
    manifest = checked_manifest(output)
    summaries = []
    scores = {table: [] for table in TABLES}
    for path in sorted((output / "episodes").glob("*/summary.json")):
        summary = json.loads(path.read_text())
        if summary["manifest_version"] != manifest["version"]:
            continue
        summaries.append(summary)
        labels = {k: summary[k] for k in ("phase", "policy", "mode", "seed", "setting", "manifest_version")}
        source = output / Path(summary["trace_path"]).parent
        for table in TABLES:
            file = source / f"{table}.json"
            if file.exists():
                scores[table].extend({**labels, **row} for row in json.loads(file.read_text()))
    write_csv(output / "episode_results.csv", summaries)
    for table, rows in scores.items():
        write_csv(output / f"{table}.csv", rows)
    metrics = ("retention_rate", "normalized_shortfall", "access_gap", "worst_group_access",
               "waiting_disparity", "spending", "solver_runtime_seconds")
    comparisons = []
    keys = sorted({(r["phase"],r["setting"],r["mode"]) for r in summaries})
    for phase, setting, mode in keys:
        subset = [r for r in summaries if (r["phase"],r["setting"],r["mode"]) == (phase,setting,mode)]
        for metric in metrics:
            p = [r for r in subset if r["policy"] == "FairPoint"]
            q = [r for r in subset if r["policy"] == "FairRobust"]
            if p and q:
                comparison = paired_comparison(q, p, metric)
                comparisons.append({"phase":phase,"setting":setting,"mode":mode,"metric":metric, **comparison})
    write_csv(output / "all_policy_comparisons.csv", comparisons)
    write_csv(output / "primary_policy_comparison.csv", [r for r in comparisons if r["phase"] == "evaluation"])
    for label in ("budget", "effect", "uncertainty", "missingness"):
        write_csv(output / f"{label}_sensitivity.csv", [r for r in comparisons if r["setting"].startswith(label+"_")])
    info = []
    for mode in ("oracle", "structured", "b_matched"):
        for metric in metrics:
            a = [r for r in summaries if r["phase"] == "secondary" and r["setting"] == "information" and r["policy"] == "FairPoint" and r["mode"] == mode]
            b = [r for r in summaries if r["phase"] == "evaluation" and r["policy"] == "FairPoint" and r["seed"] in {x["seed"] for x in a}]
            if a and b:
                info.append({"mode":mode,"reference_mode":"d_matched","metric":metric, **paired_comparison(a,b,metric)})
    write_csv(output / "information_mode_comparison.csv", info)
    ablations = [r for r in comparisons if r["setting"].startswith("uncertainty_")]
    for metric in metrics:
        a = [r for r in summaries if r["setting"] == "fairness_ablation"]
        b = [r for r in summaries if r["phase"] == "evaluation" and r["policy"] == "FairPoint" and r["seed"] in {x["seed"] for x in a}]
        if a and b:
            ablations.append({"phase":"secondary","setting":"ResourceOnlyPoint_minus_FairPoint","mode":"d_matched","metric":metric, **paired_comparison(a,b,metric)})
    write_csv(output / "ablation_results.csv", ablations)
    return summaries


def main(default_stage=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("freeze","pilot","primary","secondary","live","report","all"), default=default_stage or "all")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results/research_evaluation_v1")
    parser.add_argument("--amend", help="explicit versioned amendment reason; preserves prior manifest")
    args = parser.parse_args()
    if args.stage in ("freeze", "all") or args.amend:
        freeze(args.output, args.amend)
    if args.stage == "freeze":
        return
    manifest = checked_manifest(args.output)
    config = manifest["configuration"]
    stages = ("pilot","primary","secondary","live","report") if args.stage == "all" else (args.stage,)
    for stage in stages:
        if stage == "report":
            aggregate(args.output)
            from .research_report import generate_report
            generate_report(args.output)
        else:
            {"pilot":pilot,"primary":primary,"secondary":secondary,"live":live}[stage](args.output, config, manifest)
            aggregate(args.output)


if __name__ == "__main__":
    main()

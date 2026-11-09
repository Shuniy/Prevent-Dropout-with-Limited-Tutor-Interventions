"""Staged Step 6 evaluation using the existing closed-loop environment and policies."""

import argparse
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time
import tomllib
from urllib.parse import urlsplit

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
from .provenance import (active_directory, digest as content_digest, extractor_identity, runtime_identity,
    source_fingerprints, verify_manifest, verify_versions, write_exclusive,
    seal_directory, verify_directory, staged_artifacts, read_record)
from .research_records import (primary_design, execution_inputs, completed_records,
    primary_completion, trace_directory, validate_execution_configuration)
from .report_artifacts import report_generation
from ..school.policy_configuration import serialize_policy
from ..school.state_estimator import StudentStateEstimator
from ..school.transition_model import P_WAIT, programme_matrix

CONFIG = PROJECT_ROOT / "configs/research_evaluation.toml"
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
    return validate_config(config)


def validate_config(config):
    def reject_credentials(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower().replace('-', '_') in {
                        'api_key', 'access_token', 'auth_token', 'authorization', 'password', 'secret', 'token'}:
                    raise ValueError('credentials must be supplied outside frozen experiment configuration')
                if key == 'base_url' and isinstance(item, str):
                    endpoint = urlsplit(item)
                    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
                        raise ValueError('authentication URL components must not enter frozen configuration')
                reject_credentials(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                reject_credentials(item)
    reject_credentials(config)
    for name in ('development_seeds', 'evaluation_seeds', 'secondary_seeds', 'live_seeds'):
        seeds = config['evaluation'][name]
        if any(type(s) is not int for s in seeds) or len(seeds) != len(set(seeds)):
            raise ValueError(f'{name} must contain unique integer seeds')
    development = set(config["evaluation"]["development_seeds"])
    heldout = set(config["evaluation"]["evaluation_seeds"])
    if development & heldout or not development or not heldout:
        raise ValueError("development and evaluation seeds must be nonempty and disjoint")
    for name in ("secondary_seeds", "live_seeds"):
        if not set(config["evaluation"][name]) <= heldout:
            raise ValueError(f"{name} must be a subset of frozen evaluation seeds")
    return config


def fingerprint():
    return {**source_fingerprints(), **{str(p.relative_to(PROJECT_ROOT)): sha256(p.read_bytes()).hexdigest()
            for p in (CONFIG, PROTOCOL, DEFAULT_STUDENT_DATA_PATH)}}


def freeze(output, amendment=None, *, configuration=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    current = fingerprint()
    runtime = runtime_identity()
    config = load_config() if configuration is None else validate_config(deepcopy(configuration))
    previous = None
    if (output / "configuration_manifest.json").exists():
        verify_versions(output)
        previous = verify_manifest(active_directory(output))
        if (previous['manifest_version'] == 4 and previous["file_hashes"] == current and previous['runtime'] == runtime
                and previous['configuration'] == config and previous['protocol_text'] == PROTOCOL.read_text()):
            return previous
        if not amendment or not amendment.strip():
            raise ValueError("frozen inputs changed: supply --amend with an explicit protocol amendment")
    manifest = {'manifest_version': 4, 'runtime': runtime,
        'report_contract_version': 1, 'primary_evaluation': primary_design(config),
        'execution_defaults': {
            'scenario': asdict(ScenarioConfig(**config['scenario'])),
            'observation_model': asdict(ObservationConfig(**config['observation'])),
            'note_quality': asdict(NoteQuality(**config['notes'])),
            'matched_note_quality_by_student': {s.student_id: asdict(NoteQuality(**config[
                'primary_notes_true' if s.disadvantage_proxy_group is True else 'primary_notes_false']))
                for s in build_school(ScenarioConfig(**config['scenario'])).students},
            'wait_matrix': P_WAIT.tolist(), 'programme_matrix_alpha1': programme_matrix(1).tolist(),
            'programme_interpolation': 'wait_plus_alpha_times_programme_minus_wait_v1'},
        'predecessor': previous['input_digest'] if previous else None,
        'protocol_text': PROTOCOL.read_text(),
        'effective_policies': {name: serialize_policy(make_policy(config, name))
            for name in ('ResourceOnlyPoint', 'FairPoint', 'FairRobust')},
        'estimator': StudentStateEstimator(observation_config=ObservationConfig(**config['observation']),
            treatment_matrix=programme_matrix(config['scenario'].get('effect_strength', 1))).configuration,
        'extractor_contract': extractor_identity(None),
        "configuration": config, "file_hashes": current, "amendment": amendment,
        "heldout_already_executed": any(output.glob("**/episodes/evaluation*/summary.json")),
        "solver": {"backend": "scipy.optimize.milp/HiGHS", "mip_rel_gap": 0,
            "objective_tolerance": FairnessPlanner.OBJECTIVE_TOLERANCE,
            "fairness_tolerance": FairnessPlanner.FAIRNESS_TOLERANCE,
            "monthly_seconds": config["scenario"]["planner_time_limit"]},
        "streams": {"population": "fixed enrolled source prefix; no population resampling",
            "transition": "SHA256(seed,student,month,environment_transition)",
            "observation": "SHA256(seed,student,month,observation:mechanism)",
            "note": "SHA256(seed,student,month,note:mechanism)",
            "policy": "deterministic canonical tie-breaking; no random policy draws"}}
    manifest['input_digest'] = content_digest(manifest)
    manifest['frozen_at_utc'] = datetime.now(timezone.utc).isoformat()
    manifest = json.loads(json.dumps(manifest))
    version = output/'versions'/manifest['input_digest']
    version.mkdir(parents=True, exist_ok=False)
    for destination in ([version, output] if previous is None else [version]):
        write_exclusive(destination/'configuration_manifest.json', manifest)
        write_exclusive(destination/'protocol.json', {'protocol_text': manifest['protocol_text'],
            'configuration': config, 'protocol_sha256': sha256(manifest['protocol_text'].encode()).hexdigest()})
        with (destination/'research_evaluation_protocol_frozen.md').open('x', encoding='utf-8') as stream:
            stream.write(manifest['protocol_text'])
    pointer = output/'current_version.tmp'
    write_json(pointer, {'input_digest': manifest['input_digest']})
    pointer.replace(output/'current_version.json')
    return manifest


def checked_manifest(output):
    manifest = verify_manifest(active_directory(output))
    if manifest['manifest_version'] != 4:
        raise ValueError('historical execution identity; create an explicit amended experiment version')
    if manifest["file_hashes"] != fingerprint() or manifest['runtime'] != runtime_identity():
        raise ValueError("frozen source/configuration changed; record an explicit --amend before execution")
    return manifest


def make_policy(config, name, *, radius=None):
    scenario = ScenarioConfig(**config["scenario"])
    kwargs = {"time_limit": scenario.planner_time_limit,
        "failure_mode": scenario.planner_failure_mode,
        "treatment_matrix": programme_matrix(scenario.effect_strength)}
    if name == "ResourceOnlyPoint":
        return ConstrainedAllocationPlanner(**kwargs)
    if not scenario.fairness_enabled:
        raise ValueError("named fair research policies require fairness_enabled=True; use ResourceOnlyPoint for the ablation")
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
        max_notes_per_month=config["evaluation"]["llm_notes_per_month"] if sparse else None,
        max_monitoring_notes_per_month=config["evaluation"].get("monitoring_notes_per_month", 1),
        extraction_contract=config["evaluation"].get("extraction_contract", "actionable_monitoring"))


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
        "extraction_contract": controller.extraction_contract,
        "max_monitoring_notes_per_month": controller.max_monitoring_notes_per_month,
        "max_notes_per_month": controller.max_notes_per_month,
        "note_selection": controller.note_selection,
        "extraction_diagnostics": controller.extraction_diagnostics(),
        "decision_diagnostics": controller.decision_diagnostics,
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
    # Canonical replay directory includes all model settings, outcome evidence,
    # posterior updates, fairness ledgers and the exact initial synthetic world.
    from ..school.feedback_experiments import save_episode
    save_episode(controller, destination/'replay')


def run_one(output, config, manifest, phase, name, mode, seed, **options):
    if set(options)-{'setting', 'budget', 'effect', 'radius', 'missingness', 'sparse', 'extractor'}:
        raise ValueError('unsupported execution options; only allowlisted settings may enter provenance')
    if type(seed) is not int or phase not in ('development', 'evaluation', 'secondary', 'live'):
        raise ValueError('execution requires an integer seed and a declared research phase')
    if config != manifest['configuration']:
        raise ValueError('execution configuration differs from immutable manifest')
    output = active_directory(output)
    checked = checked_manifest(output)
    if checked['input_digest'] != manifest['input_digest']:
        raise ValueError('incompatible active experiment identity')
    setting = options.get('setting', 'primary')
    execution = execution_inputs(config, manifest['input_digest'], phase, name, mode, seed,
        **{k: v for k, v in options.items() if k not in ('extractor', 'setting')},
        setting=setting, extractor_identity=extractor_identity(options.get('extractor')))
    # Canonical effective defaults prevent an explicit-default spelling from
    # becoming an unrecorded retry or duplicate primary cell.
    identity = dict(execution)
    execution_key = content_digest(execution)
    token = execution_key[:12]
    destination = Path(output) / "episodes" / f"{phase}_{name}_{mode}_{seed}_{token}"
    if (destination / "summary.json").exists():
        verify_directory(destination)
        saved = json.loads((destination / "summary.json").read_text())
        if any(saved.get(k) != v for k, v in identity.items()):
            raise ValueError('cached experiment identity mismatch')
        return saved
    with staged_artifacts(destination, identity=identity, failure_marker=True) as staging:
        write_exclusive(staging/'execution.json', identity)
        controller = make_controller(config, name, mode, seed, **options)
        controller.experiment_identity = manifest['input_digest']
        started = time.perf_counter()
        controller.run_episode()
        validate_feedback_episode(controller)
        scores = score_episode(controller)
        summary = {**episode_summary(controller, name, mode, setting, seed), **identity,
            'validation': {'scientific_and_resource_invariants': True},
            "wall_seconds": time.perf_counter() - started,
            "trace_digest": digest_controller(controller),
            "execution_key": execution_key, 'execution_inputs': execution,
            "extraction_failures": len(controller.failures), **controller.extraction_diagnostics(),
            "note_count": len(controller.notes),
            "trace_path": str(destination.relative_to(output) / "trace.json.gz")}
        save_trace(controller, staging)
        reconstruction = read_record(staging/'replay/experiment_config.json')
        summary['episode_identity'] = reconstruction['episode_identity']
        validate_execution_configuration(manifest, summary, reconstruction)
        for table, rows in scores.items():
            if table.endswith("records"):
                with gzip.open(staging / f"{table}.json.gz", "wt", encoding="utf-8") as stream:
                    json.dump(rows, stream, allow_nan=False)
            else:
                write_json(staging / f"{table}.json", rows)
        write_json(staging/'summary.json', summary)
        seal_directory(staging)
        verify_directory(staging)
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
        "input_digest": manifest["input_digest"], "policy_order": order,
        "repeat_trace_digests": expected, "null_effect_exact_truth_equal": True,
        "independent_seed_count": len(config["evaluation"]["development_seeds"])})


def require_pilot(output, manifest):
    path = Path(output) / "development_gate.json"
    gate = json.loads(path.read_text()) if path.exists() else {}
    if not gate.get("passed") or gate.get("input_digest") != manifest["input_digest"]:
        raise ValueError("run the development pilot under the active frozen configuration first")


def primary(output, config, manifest):
    require_pilot(output, manifest)
    run_pairs(output, config, manifest, "evaluation", config["evaluation"]["evaluation_seeds"])
    aggregate(output)
    status = read_record(active_directory(output)/'aggregation_status.json')
    if not status['primary_complete']:
        raise ValueError('primary comparison did not complete the frozen validated matrix')


def secondary(output, config, manifest):
    require_pilot(output, manifest)
    primary_path = Path(output) / "primary_complete.json"
    if (not primary_path.exists() or
            json.loads(primary_path.read_text()).get("input_digest") != manifest["input_digest"]):
        raise ValueError("execute primary comparison before secondary experiments")
    current = primary_completion(Path(output), manifest, completed_records(output, manifest))
    if not current['primary_complete']:
        raise ValueError('execute complete validated primary comparison before secondary experiments')
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
    closed_loop_calls = extractor.calls
    live_snapshot_comparisons(output, config, extractor)
    write_json(Path(output) / "live_runtime.json", {"new_inference_calls": extractor.calls,
        "closed_loop_inference_calls": closed_loop_calls,
        "snapshot_inference_calls": extractor.calls - closed_loop_calls,
        "configuration": extractor.configuration,
        "n_world_seeds": len(config["evaluation"]["live_seeds"]),
        "note": "Temperature0 is not a bitwise determinism guarantee; cache replay is deterministic."})


def live_snapshot_comparisons(output, config, extractor):
    """Fork a shared gold month-1 history immediately before cutoff-2 extraction.

    These are conditional extraction contrasts, not unrelated closed-loop worlds.
    No observations after the forked decision are reused across trajectories.
    """
    if config["scenario"]["horizon"] < 2:
        raise ValueError("snapshot comparison requires at least two decision months")
    rows = []
    for seed in config["evaluation"]["live_seeds"]:
        for gold_mode, llm_mode in (("b_matched", "llm_notes"), ("d_matched", "noisy_notes")):
            common = make_controller(config, "FairPoint", gold_mode, seed, sparse=True)
            common.run_month()
            controls = []
            for mode in (gold_mode, llm_mode):
                controller = deepcopy(common)
                controller.mode = "b_matched" if mode == "d_matched" else mode
                controller.extractor = extractor
                state = controller.prepare_decision_snapshot(2)
                allocation = controller.allocate(state)
                controls.append((controller, state, allocation))
            left, right = controls
            if (left[0].notes != right[0].notes or left[0].note_selection != right[0].note_selection
                    or left[1].mentors != right[1].mentors
                    or left[1].remaining_budget_exact != right[1].remaining_budget_exact
                    or [(s.student_id, s.eligible, s.programme_months) for s in left[1].students]
                    != [(s.student_id, s.eligible, s.programme_months) for s in right[1].students]):
                raise AssertionError("gold/LLM comparison inputs differ")
            diagnostics = right[0].extraction_diagnostics(2)
            status = ("UNAVAILABLE / NOT EXERCISED" if not diagnostics["extractor_attempts"] else
                      "UNAVAILABLE / UNUSABLE" if not diagnostics["eligible_students_with_new_usable_evidence"] else "EXERCISED")
            exercised = diagnostics["extractor_attempts"] > 0
            lbenefit = estimate_all_student_benefits(left[1], left[0].policy.wait_matrix, left[0].policy.programme_matrix)
            rbenefit = estimate_all_student_benefits(right[1], right[0].policy.wait_matrix, right[0].policy.programme_matrix)
            ids = sorted(lbenefit.keys() | rbenefit.keys())
            lassign = {a.student_id: a.mentor_id for a in left[2].assignments}
            rassign = {a.student_id: a.mentor_id for a in right[2].assignments}
            lrisks = {r.student_id: r.probability for r in left[1].risk_estimates}
            rrisks = {r.student_id: r.probability for r in right[1].risk_estimates}
            for a, b in zip(left[1].students, right[1].students):
                rows.append({"seed": seed, "gold_mode": gold_mode, "llm_mode": llm_mode,
                    "month": 2, "student_id": a.student_id, "same_notes": True,
                    "status": status, **diagnostics,
                    "belief_l1": sum(abs(x-y) for x,y in zip(a.condition_probabilities,b.condition_probabilities)) if exercised else None,
                    "risk_difference": rrisks[a.student_id]-lrisks[a.student_id] if exercised else None,
                    "benefit_difference": rbenefit.get(a.student_id,0)-lbenefit.get(a.student_id,0) if exercised else None,
                    "eligibility_changed": a.eligible != b.eligible,
                    "selected_gold": a.student_id in lassign, "selected_llm": a.student_id in rassign,
                    "mentor_changed": (lassign.get(a.student_id) != rassign.get(a.student_id)) if exercised else None})
            lv, rv = [lbenefit.get(sid,0) for sid in ids], [rbenefit.get(sid,0) for sid in ids]
            rank = (float(spearmanr(lv, rv).statistic) if status == "EXERCISED"
                    and len(set(lv)) > 1 and len(set(rv)) > 1 else None)
            write_json(Path(output) / f"live_snapshot_rank_{seed}_{gold_mode}.json",
                {"spearman_average_ties": rank, "status": status, **diagnostics,
                 "decision_cutoffs_compared": [2] if exercised else [],
                 "same_notes": True, "cutoff": 2, "seed": seed,
                 "shared_history": common.decisions,
                 "selection": [s for s in right[0].note_selection if s["cutoff"] == 2],
                 "attempts": [a for a in right[0].extraction_attempts if a["as_of_month"] == 2],
                 "gold_snapshot": asdict(left[1]), "extracted_snapshot": asdict(right[1]),
                 "gold_allocation": asdict(left[2]), "extracted_allocation": asdict(right[2])})
    write_csv(Path(output) / "extraction_snapshot_comparison.csv", rows)
    return rows


def _aggregate(output, destination):
    output = active_directory(output)
    manifest = checked_manifest(output)
    summaries = []
    scores = {table: [] for table in TABLES}
    records = [(path, read_record(path))
               for path in sorted((output/'episodes').glob('*/summary.json'))]
    for path, summary in records:
        if summary.get("input_digest") != manifest["input_digest"]:
            raise ValueError(f'incompatible experiment identity: {path}')
    records = completed_records(output, manifest)
    status = primary_completion(output, manifest, records)
    extractor_versions = {}
    cell_configurations = {}
    for path, summary in records:
        extraction = summary.get('extractor_identity')
        key = summary['mode']
        if key in extractor_versions and extractor_versions[key] != extraction:
            raise ValueError('incompatible extractor/model versions in aggregation')
        extractor_versions[key] = extraction
        verify_directory(path.parent)
        if 'execution_inputs' not in summary:
            raise ValueError('missing execution configuration provenance')
        cell = tuple(summary[k] for k in ('phase', 'setting', 'mode', 'policy'))
        effective = {k: v for k, v in summary['execution_inputs'].items() if k != 'seed'}
        if cell in cell_configurations and cell_configurations[cell] != effective:
            raise ValueError('incompatible execution settings within an aggregation cell')
        cell_configurations[cell] = effective
        summaries.append(summary)
        labels = {k: summary[k] for k in ("phase", "policy", "mode", "seed", "setting", "input_digest")}
        labels['primary_cell_valid'] = ((summary['phase'], summary['setting'], summary['mode']) ==
            ('evaluation', 'primary', 'd_matched') and
            [summary['policy'], summary['seed']] in status['completed_primary_cells'])
        source = trace_directory(output, summary)
        verify_directory(source)
        for table in TABLES:
            file = source / f"{table}.json"
            if not file.exists():
                raise ValueError(f'missing scorecard provenance: {file}')
            scores[table].extend({**labels, **row} for row in json.loads(file.read_text()))
    output = destination
    write_json(output/'aggregation_status.json', status)
    if status['primary_complete']:
        write_json(output/'primary_complete.json', {'input_digest': manifest['input_digest'],
            'n_paired_seeds': status['completed_paired_seeds'], 'episodes': status['actual_primary_episodes'],
            'contributing_episodes': status['contributing_episodes']})
    write_csv(output/'episode_results.csv', [{**row, 'primary_cell_valid':
        (row['phase'], row['setting'], row['mode']) == ('evaluation', 'primary', 'd_matched')
        and [row['policy'], row['seed']] in status['completed_primary_cells']} for row in summaries])
    for table, rows in scores.items():
        write_csv(output / f"{table}.csv", rows)
    metrics = ("retention_rate", "normalized_shortfall", "access_gap", "worst_group_access",
               "waiting_disparity", "spending", "solver_runtime_seconds")
    comparisons = []
    def matched(a, b):
        seeds = {r['seed'] for r in a} & {r['seed'] for r in b}
        return [r for r in a if r['seed'] in seeds], [r for r in b if r['seed'] in seeds]
    keys = sorted({(r["phase"],r["setting"],r["mode"]) for r in summaries})
    for phase, setting, mode in keys:
        subset = [r for r in summaries if (r["phase"],r["setting"],r["mode"]) == (phase,setting,mode)]
        if (phase, setting, mode) == ('evaluation', 'primary', 'd_matched'):
            subset = [r for r in subset if [r['policy'], r['seed']] in status['completed_primary_cells']]
        for metric in metrics:
            p = [r for r in subset if r["policy"] == "FairPoint"]
            q = [r for r in subset if r["policy"] == "FairRobust"]
            p, q = matched(p, q)
            if p and q:
                comparison = paired_comparison(q, p, metric)
                comparisons.append({"phase":phase,"setting":setting,"mode":mode,"metric":metric,
                    'primary_evaluation_complete': status['primary_complete'],
                    'statistics_scope': status['statistics_scope'] if (phase, setting, mode) ==
                        ('evaluation', 'primary', 'd_matched') else 'exploratory_completed_subset', **comparison})
    write_csv(output / "all_policy_comparisons.csv", comparisons)
    primary_comparisons = [r for r in comparisons if (r['phase'], r['setting'], r['mode']) ==
                           ('evaluation', 'primary', 'd_matched')]
    # A partial paired CI remains available in an explicitly exploratory table.
    write_csv(output/'exploratory_primary_comparison.csv', primary_comparisons if not status['primary_complete'] else [])
    write_csv(output/'primary_policy_comparison.csv', primary_comparisons if status['primary_complete'] else [])
    for label in ("budget", "effect", "uncertainty", "missingness"):
        write_csv(output / f"{label}_sensitivity.csv", [r for r in comparisons if r["setting"].startswith(label+"_")])
    info = []
    for mode in ("oracle", "structured", "b_matched"):
        for metric in metrics:
            a = [r for r in summaries if r["phase"] == "secondary" and r["setting"] == "information" and r["policy"] == "FairPoint" and r["mode"] == mode]
            b = [r for r in summaries if (r['phase'], r['setting'], r['mode'], r['policy']) ==
                 ('evaluation', 'primary', 'd_matched', 'FairPoint')]
            a, b = matched(a, b)
            if a and b:
                info.append({"mode":mode,"reference_mode":"d_matched","metric":metric, **paired_comparison(a,b,metric)})
    write_csv(output / "information_mode_comparison.csv", info)
    ablations = [r for r in comparisons if r["setting"].startswith("uncertainty_")]
    for metric in metrics:
        a = [r for r in summaries if r["setting"] == "fairness_ablation"]
        b = [r for r in summaries if (r['phase'], r['setting'], r['mode'], r['policy']) ==
             ('evaluation', 'primary', 'd_matched', 'FairPoint')]
        a, b = matched(a, b)
        if a and b:
            ablations.append({"phase":"secondary","setting":"ResourceOnlyPoint_minus_FairPoint","mode":"d_matched","metric":metric, **paired_comparison(a,b,metric)})
    write_csv(output / "ablation_results.csv", ablations)
    return summaries


def aggregate(output):
    """Publish a sealed aggregate snapshot, retaining every earlier generation."""
    version = active_directory(output)
    # Check identity conflicts before opening any generation lifecycle.
    records = [(p, read_record(p)) for p in sorted((version/'episodes').glob('*/summary.json'))]
    manifest = checked_manifest(version)
    if any(row.get('input_digest') != manifest['input_digest'] for _, row in records):
        raise ValueError('incompatible experiment identity in aggregation')
    with report_generation(version, 'aggregate') as staging:
        summaries = _aggregate(version, staging)
    return summaries


def main(default_stage=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("freeze","pilot","primary","secondary","live","report","all"), default=default_stage or "all")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results/research_evaluation")
    parser.add_argument("--amend", help="explicit reason for creating a new immutable experiment version")
    args = parser.parse_args()
    if args.stage in ("freeze", "all") or args.amend:
        freeze(args.output, args.amend)
    if args.stage == "freeze":
        return
    manifest = checked_manifest(args.output)
    args.output = active_directory(args.output)
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

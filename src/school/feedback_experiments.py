"""Limited Step 5 development comparisons, auditable traces and reproduction CLI."""

import argparse
import csv
from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
import tomllib
from urllib.request import urlopen
from urllib.error import URLError

import numpy as np

from ..intervention.feedback_notes import NoteQuality
from ..intervention.observation_extractor import FixtureObservationExtractor, LLMObservationExtractor
from ..intervention.ollama_client import OllamaClient
from .closed_loop_controller import INFORMATION_MODES
from .cmdp_scenarios import build_school
from .constrained_planner import ConstrainedAllocationPlanner
from .fairness_planner import FairnessPlanner
from .observation_model import ObservationConfig
from .scenario_config import ScenarioConfig
from .transition_model import programme_matrix


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(asdict(record) if hasattr(record, "__dataclass_fields__") else record,
                                    ensure_ascii=False, allow_nan=False) + "\n")


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_episode(controller, output):
    from .feedback_validation import validate_feedback_episode
    validate_feedback_episode(controller)
    output.mkdir(parents=True, exist_ok=False)
    config = controller.environment.config
    write_jsonl(output / "initial_observations.jsonl", [
        {"kind": "event", **asdict(e)} for e in controller.events if e.event_month == 0] + [
        {"kind": "administrative_enrollment", **asdict(r)} for r in controller.registry if r.event_month == 0])
    for filename, records in (
        ("observable_events", controller.events), ("administrative_enrollment", controller.registry),
        ("mentor_notes", controller.notes), ("extracted_observations", controller.batches),
        ("estimate_updates", controller.estimator.updates), ("risk_estimates", controller.risks),
        ("decision_snapshots", controller.snapshots), ("allocation_decisions", controller.decisions),
        ("extraction_failures", controller.failures), ("fairness_windows", controller.fairness_rows)):
        write_jsonl(output / f"{filename}.jsonl", records)
    write_jsonl(output / "extraction_attempts.jsonl", controller.extraction_attempts)
    write_jsonl(output / "note_selection.jsonl", controller.note_selection)
    write_jsonl(output / "decision_extraction_diagnostics.jsonl", controller.decision_diagnostics)
    # Evaluation-only directory is never handed to a policy or extractor.
    evaluator = output / "evaluator_only"
    evaluator.mkdir()
    write_jsonl(evaluator / "truth_trajectories.jsonl", controller.evaluator_truth)
    manifest = {"scenario": asdict(config), "information_mode": controller.mode,
        "observation_model": asdict(controller.observation_model.config),
        "note_quality": asdict(controller.note_quality), "max_notes_per_month": controller.max_notes_per_month,
        "extraction_contract": controller.extraction_contract,
        "max_monitoring_notes_per_month": controller.max_monitoring_notes_per_month,
        "extraction_diagnostics": controller.extraction_diagnostics(),
        "note_quality_by_student": {sid: asdict(quality) for sid, quality
                                    in controller.note_quality_by_student.items()},
        "estimator": controller.estimator.configuration,
        "allocation_policy": type(controller.policy).__name__,
        "allocation_policy_settings": controller.policy.settings,
        "fairness_stratum_rule": "enrolled_MAP_if_max_probability_at_least_0.6_else_uncertain",
        "support_need_rule": "existing_static_primary_need_no_LLM_reassignment",
        "environment_wait_matrix": controller.environment.transition_assumptions[0],
        "environment_programme_matrix": controller.environment.transition_assumptions[1]}
    if hasattr(controller, "replay_provenance"):
        manifest["replay_provenance"] = controller.replay_provenance
    (output / "experiment_config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def plot_episode(controller, output):
    # Standalone scientific figures, generated from actual execution records.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True, exist_ok=True)
    ids = sorted(controller.estimates)[:3]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True)
    for axis, sid in zip(axes, ids):
        updates = [u for u in controller.estimator.updates if u.student_id == sid]
        values = np.asarray([u.updated_belief for u in updates])
        axis.stackplot([u.month for u in updates], values.T,
                       labels=("Stable", "Vulnerable", "Disengaged", "Withdrawn"))
        axis.set(title=sid, xlabel="Decision cutoff", ylim=(0, 1))
    axes[0].set_ylabel("Estimated probability")
    axes[-1].legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(output / "belief_evolution.png", dpi=140)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(7, 3.5))
    for sid in ids:
        records = [r for r in controller.risks if r.student_id == sid]
        axis.plot([r.as_of_month for r in records], [r.probability for r in records], marker=".", label=sid)
    axis.set(xlabel="Decision cutoff", ylabel="Synthetic endpoint risk", ylim=(0, 1))
    axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "risk_evolution.png", dpi=140)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(7, 3.5))
    for row in controller.decisions:
        for sid in row["admitted_ids"]:
            axis.scatter(row["month"], sorted(controller.estimates).index(sid), color="#176b87")
    axis.set(xlabel="Admission month", ylabel="Student index", title="Actual admissions along the feedback trajectory")
    fig.tight_layout()
    fig.savefig(output / "allocation_changes.png", dpi=140)
    plt.close(fig)


def run_feedback_experiments(config, *, output, observation_config=ObservationConfig(),
        note_quality=NoteQuality(), noisy_quality=NoteQuality(omission_probability=.35,
        conflict_probability=.2, misleading_probability=.1, delay_probability=.25),
        modes=INFORMATION_MODES, policies=("resource", "fairness"), extractor=None,
        max_notes_per_month=None, max_monitoring_notes_per_month=1,
        extraction_contract="actionable_monitoring"):
    output = Path(output)
    if not modes or any(m not in INFORMATION_MODES for m in modes):
        raise ValueError("select valid information modes")
    if not policies or any(p not in ("resource", "fairness") for p in policies):
        raise ValueError("select resource and/or fairness planners")
    extractor = extractor or FixtureObservationExtractor()
    model_metadata = None
    if isinstance(extractor, LLMObservationExtractor):
        try:
            with urlopen(extractor.client.base_url + "/api/tags", timeout=5) as response:
                model_metadata = next((m for m in json.load(response).get("models", [])
                    if m["name"] == extractor.client.model), None)
        except (OSError, URLError, ValueError) as exc:
            model_metadata = {"unavailable_reason": str(exc)}
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    (output / "experiment_config.json").write_text(json.dumps({
        "stage": "development_integration_only",
        "scenario": asdict(config), "observation": asdict(observation_config),
        "notes": asdict(note_quality), "noisy_notes": asdict(noisy_quality),
        "modes": modes, "policies": policies, "max_notes_per_month": max_notes_per_month,
        "max_monitoring_notes_per_month": max_monitoring_notes_per_month,
        "extraction_contract": extraction_contract,
        "model_metadata": model_metadata,
        "llm_options": ({"model": extractor.client.model, "num_ctx": extractor.client.num_ctx,
                         "temperature": 0} if isinstance(extractor, LLMObservationExtractor) else None),
        "note": "Fixture extraction is a wiring control; no held-out research claims."}, indent=2))
    for name in policies:
        for mode in modes:
            kwargs = {"time_limit": config.planner_time_limit, "failure_mode": config.planner_failure_mode,
                      "treatment_matrix": programme_matrix(config.effect_strength)}
            policy = (ConstrainedAllocationPlanner(**kwargs) if name == "resource" else
                FairnessPlanner(minimum_access=config.fairness_min_access,
                    window_months=config.fairness_window, grouping_attribute=config.fairness_grouping_attribute,
                    allow_shortfall=config.fairness_allow_shortfall, **kwargs))
            calls_before = getattr(extractor, "calls", 0)
            controller = build_school(config).run_cmdp_feedback(policy, config=config,
                mode=mode, extractor=extractor, observation_config=observation_config,
                note_quality=noisy_quality if mode == "noisy_notes" else note_quality,
                max_notes_per_month=max_notes_per_month,
                max_monitoring_notes_per_month=max_monitoring_notes_per_month,
                extraction_contract=extraction_contract)
            destination = output / f"{name}_{mode}_seed_{config.seed}"
            save_episode(controller, destination)
            # Shared models, separate realized trajectories for every policy/mode.
            if name == policies[0] and mode == ("llm_notes" if "llm_notes" in modes else modes[0]):
                plot_episode(controller, output / "figures")
            row = {"policy": name, "mode": mode, "seed": config.seed,
                "students": config.num_students, "months": config.horizon,
                "terminal_enrolled": controller.environment.terminal_reward(),
                "programmes": sum(len(r["admitted_ids"]) for r in controller.decisions),
                "spent_budget": config.budget - controller.environment.records[-1].remaining_budget,
                "notes_generated": len(controller.notes), "extracted_batches": len(controller.batches),
                "quarantined_extractions": len(controller.failures),
                **controller.extraction_diagnostics(),
                "real_llm_calls": getattr(extractor, "calls", 0) - calls_before,
                "extractor": type(extractor).__name__ if mode in ("llm_notes", "noisy_notes") else "structured_gold",
                "normalized_window_shortfall": sum(
                    row["outstanding_before"] / row["eligible_count"]
                    for row in controller.fairness_rows
                    if row["decision_month"] == row["window_end"] and row["eligible_count"]),
                "hard_constraints_valid": True}
            rows.append(row)
            write_csv(output / "episode_results.csv", rows)
            write_csv(output / "pilot_information_comparison.csv", rows)
            print(f"{name}/{mode}: enrolled={row['terminal_enrolled']}/{config.num_students}, "
                  f"programmes={row['programmes']}, spent={row['spent_budget']}, "
                  f"quarantined={row['quarantined_extractions']}", flush=True)
    return rows


def main(*, pilot=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/cmdp_llm_feedback.toml"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--extractor", choices=("fixture", "ollama"), default="fixture")
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-notes-per-month", type=int,
                        help="Limit intervention programme notes per source month")
    parser.add_argument("--max-monitoring-notes-per-month", type=int, default=1,
                        help="Limit actionable monitoring notes per decision cutoff (default: 1)")
    parser.add_argument("--extraction-contract", choices=("actionable_monitoring", "legacy_programme_only"),
                        default="actionable_monitoring")
    parser.add_argument("--modes", nargs="+", choices=INFORMATION_MODES, default=list(INFORMATION_MODES))
    parser.add_argument("--policies", nargs="+", choices=("resource", "fairness"), default=["resource", "fairness"])
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    with args.config.open("rb") as stream:
        values = tomllib.load(stream)
    config = ScenarioConfig(**values["scenario"])
    if pilot:
        config = replace(config, num_students=12, horizon=4, budget=20)
    if args.seed is not None:
        config = replace(config, seed=args.seed)
    observation = dict(values.get("observation", {}))
    if "emissions" in observation:
        observation["emissions"] = tuple(tuple(row) for row in observation["emissions"])
    extractor = (FixtureObservationExtractor() if args.extractor == "fixture" else
                 LLMObservationExtractor(OllamaClient(args.model, timeout=args.timeout, num_ctx=8192)))
    output = args.output or Path("results/cmdp_llm_feedback") / (
        ("pilot_" if pilot else "integration_") + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    run_feedback_experiments(config, output=output, observation_config=ObservationConfig(**observation),
        note_quality=NoteQuality(**values.get("notes", {})),
        noisy_quality=NoteQuality(**values.get("noisy_notes", {})), extractor=extractor,
        modes=tuple(args.modes), policies=tuple(args.policies), max_notes_per_month=args.max_notes_per_month,
        max_monitoring_notes_per_month=args.max_monitoring_notes_per_month,
        extraction_contract=args.extraction_contract)
    print(f"Saved Step 5 development results: {output}")

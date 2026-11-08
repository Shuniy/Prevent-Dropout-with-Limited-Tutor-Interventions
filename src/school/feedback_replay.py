"""Replay one recorded episode without invoking a language model."""

import json
from pathlib import Path

from ..intervention.feedback_notes import NoteQuality
from ..intervention.observation_extractor import FixtureObservationExtractor
from .cmdp_scenarios import build_school
from .constrained_planner import ConstrainedAllocationPlanner
from .fairness_planner import FairnessPlanner
from .feedback_experiments import save_episode
from .observation_model import ObservationConfig
from .scenario_config import ScenarioConfig
from .transition_model import programme_matrix


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def replay_feedback_episode(source, output):
    source, output = Path(source), Path(output)
    manifest = json.loads((source / "experiment_config.json").read_text())
    config = ScenarioConfig(**manifest["scenario"])
    payloads = {}
    for batch in read_jsonl(source / "extracted_observations.jsonl"):
        payloads[batch["note_id"]] = {"student_id": batch["student_id"], "note_id": batch["note_id"],
            "observations": [{k: v for k, v in fact.items() if k not in ("event_id", "evidence_id")}
                             for fact in batch["facts"]]}
    extractor = FixtureObservationExtractor(payloads)
    kwargs = {"time_limit": config.planner_time_limit, "failure_mode": config.planner_failure_mode,
              "treatment_matrix": programme_matrix(config.effect_strength)}
    policy = (FairnessPlanner(minimum_access=config.fairness_min_access,
        window_months=config.fairness_window, grouping_attribute=config.fairness_grouping_attribute,
        allow_shortfall=config.fairness_allow_shortfall, **kwargs)
        if manifest["allocation_policy"] == "FairnessPlanner" else ConstrainedAllocationPlanner(**kwargs))
    observation = manifest["observation_model"]
    observation["emissions"] = tuple(tuple(row) for row in observation["emissions"])
    result = build_school(config).run_cmdp_feedback(policy, config=config,
        mode=manifest["information_mode"], extractor=extractor,
        observation_config=ObservationConfig(**observation),
        note_quality=NoteQuality(**manifest["note_quality"]),
        note_quality_by_student={sid: NoteQuality(**quality) for sid, quality
                                 in manifest.get("note_quality_by_student", {}).items()},
        max_notes_per_month=manifest["max_notes_per_month"],
        max_monitoring_notes_per_month=manifest.get("max_monitoring_notes_per_month", 1),
        extraction_contract=manifest.get("extraction_contract", "legacy_programme_only"))
    expected = read_jsonl(source / "allocation_decisions.jsonl")
    if any(list(actual["admitted_ids"]) != old["admitted_ids"]
           or actual["remaining_budget_after"] != old["remaining_budget_after"]
           for actual, old in zip(result.decisions, expected)) or len(expected) != len(result.decisions):
        raise ValueError("replay allocation/resource mismatch")
    expected_truth = read_jsonl(source / "evaluator_only/truth_trajectories.jsonl")
    if json.loads(json.dumps(result.evaluator_truth)) != expected_truth:
        raise ValueError("replay transition mismatch")
    save_episode(result, output)
    if read_jsonl(output / "decision_snapshots.jsonl") != read_jsonl(source / "decision_snapshots.jsonl"):
        raise ValueError("replay decision estimate/risk mismatch")
    summary = {"source": str(source), "decisions_reproduced": len(result.decisions),
               "terminal_enrolled": result.environment.terminal_reward(), "real_llm_calls": 0,
               "snapshots_allocations_resources_and_truth_match": True}
    (output / "replay_result.json").write_text(json.dumps(summary, indent=2))
    return summary

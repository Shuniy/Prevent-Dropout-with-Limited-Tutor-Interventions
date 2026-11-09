"""Replay one recorded episode without invoking a language model."""

import json
from pathlib import Path

from ..intervention.feedback_notes import NoteQuality
from ..intervention.observation_extractor import RecordedOutcomeExtractor
from ..observations.observable_events import EnrollmentRecord, Note, ObservableEvent
from .closed_loop_controller import ClosedLoopCMDPController
from .cmdp_scenarios import build_school
from .constrained_planner import ConstrainedAllocationPlanner
from .fairness_planner import FairnessPlanner
from .feedback_experiments import save_episode
from .observation_model import ObservationConfig, SyntheticObservationModel
from .scenario_config import ScenarioConfig
from .state_estimator import StudentStateEstimator
from .transition_model import programme_matrix


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class RecordedObservations(SyntheticObservationModel):
    """Authorized input history; evaluator truth is never an extraction input."""
    def __init__(self, source, config):
        super().__init__(config)
        self.events = [ObservableEvent(**r) for r in read_jsonl(source / "observable_events.jsonl")]
        self.registry = [EnrollmentRecord(**r) for r in read_jsonl(source / "administrative_enrollment.jsonl")]

    def generate(self, conditions, *, month, **kwargs):
        return (tuple(r for r in self.events if r.event_month == month),
                tuple(r for r in self.registry if r.event_month == month))


class ReplayController(ClosedLoopCMDPController):
    def __init__(self, *args, source, replay_provenance, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorded_notes = {r["note_id"]: Note(**{**r, "source_event_ids": tuple(r["source_event_ids"])})
                              for r in read_jsonl(source / "mentor_notes.jsonl")}
        self.replay_provenance = replay_provenance

    def _generate_observations(self):
        super()._generate_observations()
        # Preserve exact recorded prose/dates, including custom fixture notes.
        self.notes = [self.recorded_notes[n.note_id] for n in self.notes]


def replay_feedback_episode(source, output):
    source, output = Path(source), Path(output)
    manifest = json.loads((source / "experiment_config.json").read_text())
    config = ScenarioConfig(**manifest["scenario"])
    attempts_path = source / "extraction_attempts.jsonl"
    if not attempts_path.exists():
        raise ValueError("complete outcome replay requires extraction_attempts.jsonl; legacy batch-only traces are insufficient")
    attempts = read_jsonl(attempts_path)
    batches = read_jsonl(source / "extracted_observations.jsonl")
    extractor = RecordedOutcomeExtractor(attempts, batches)
    if manifest["allocation_policy"] not in ("FairnessPlanner", "ConstrainedAllocationPlanner"):
        raise ValueError("replay does not reconstruct this policy configuration")
    settings = dict(manifest["allocation_policy_settings"])
    kwargs = {"time_limit": settings["time_limit"], "failure_mode": settings["failure_mode"],
              "treatment_matrix": programme_matrix(config.effect_strength)}
    policy = (FairnessPlanner(minimum_access=config.fairness_min_access,
        window_months=config.fairness_window, grouping_attribute=settings["grouping_attribute"],
        allow_shortfall=settings["allow_shortfall"], **kwargs)
        if manifest["allocation_policy"] == "FairnessPlanner" else ConstrainedAllocationPlanner(**kwargs))
    if dict(policy.settings) != settings:
        raise ValueError("replay cannot restore the recorded planner settings")
    observation = manifest["observation_model"]
    observation["emissions"] = tuple(tuple(row) for row in observation["emissions"])
    estimator_config = manifest["estimator"]
    estimator_observation = dict(estimator_config["observation_config"])
    estimator_observation["emissions"] = tuple(tuple(row) for row in estimator_observation["emissions"])
    estimator = StudentStateEstimator(prior=estimator_config["prior"],
        wait_matrix=estimator_config["wait_matrix"], treatment_matrix=estimator_config["programme_matrix"],
        observation_config=ObservationConfig(**estimator_observation))
    result = ReplayController(build_school(config).create_cmdp_environment(config=config), policy,
        source=source, replay_provenance={
            "original_model_invocations": sum(a["model_invocations"] for a in attempts),
            "original_cache_hits": sum(a["cache_hit"] for a in attempts),
            "replay_model_invocations": 0,
            "attempt_provenance": "historical original execution, not replay inference"},
        mode=manifest["information_mode"], extractor=extractor,
        estimator=estimator,
        observation_config=ObservationConfig(**observation),
        note_quality=NoteQuality(**manifest["note_quality"]),
        note_quality_by_student={sid: NoteQuality(**quality) for sid, quality
                                 in manifest.get("note_quality_by_student", {}).items()},
        max_notes_per_month=manifest["max_notes_per_month"],
        max_monitoring_notes_per_month=manifest.get("max_monitoring_notes_per_month", 1),
        extraction_contract=manifest.get("extraction_contract", "legacy_programme_only"))
    result.observation_model = RecordedObservations(source, ObservationConfig(**observation))
    # Gold routing is determined by identity in the controller; keep a separate
    # recorded adapter so injected routes remain explicitly injected.
    gold_attempts = [a for a in attempts if a["route"] == "gold"]
    gold_keys = {(a["note_id"], a["as_of_month"]) for a in gold_attempts}
    gold_extractor = RecordedOutcomeExtractor(gold_attempts,
        [b for b in batches if (b["note_id"], b["as_of_month"]) in gold_keys])
    result.gold_extractor = gold_extractor
    result.run_episode()
    if extractor.used | gold_extractor.used != set(extractor.outcomes):
        raise ValueError("recorded extraction outcomes were not all replayed")
    expected = read_jsonl(source / "allocation_decisions.jsonl")

    def deterministic_decisions(rows):
        rows = json.loads(json.dumps(rows))
        for row in rows:
            row["allocation"].pop("runtime_seconds", None)
        return rows

    if deterministic_decisions(result.decisions) != deterministic_decisions(expected):
        raise ValueError("replay allocation/resource mismatch")
    expected_truth = read_jsonl(source / "evaluator_only/truth_trajectories.jsonl")
    if json.loads(json.dumps(result.evaluator_truth)) != expected_truth:
        raise ValueError("replay transition mismatch")
    save_episode(result, output)
    checked = ("mentor_notes", "note_selection", "extracted_observations", "extraction_attempts",
               "extraction_failures", "estimate_updates", "risk_estimates", "decision_snapshots",
               "decision_extraction_diagnostics", "observable_events", "administrative_enrollment")
    for name in checked:
        if read_jsonl(output / f"{name}.jsonl") != read_jsonl(source / f"{name}.jsonl"):
            raise ValueError(f"replay {name} mismatch")
    summary = {"source": str(source), "decisions_reproduced": len(result.decisions),
               "terminal_enrolled": result.environment.terminal_reward(), "real_llm_calls": 0,
               "snapshots_allocations_resources_and_truth_match": True,
               "evidence_processing_history_match": True, "checked_records": checked,
               "extraction_attempts": len(attempts),
               "accepted_extractions": sum(a["status"] == "accepted" for a in attempts),
               "quarantined_extractions": sum(a["status"] == "quarantined" for a in attempts),
               **result.replay_provenance}
    (output / "replay_result.json").write_text(json.dumps(summary, indent=2))
    return summary

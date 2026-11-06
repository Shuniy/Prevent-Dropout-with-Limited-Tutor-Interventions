"""Independent trace checks and a fixed-record demonstration of sequential feedback."""

from dataclasses import asdict
import json
from pathlib import Path

from ..intervention.observation_extractor import FixtureObservationExtractor
from ..observations.observable_events import EnrollmentRecord, ObservableEvent
from .closed_loop_controller import ClosedLoopCMDPController
from .cmdp_scenarios import build_school
from .constrained_planner import ConstrainedAllocationPlanner
from .constraints import validate_allocation
from .observation_model import ObservationConfig
from .scenario_config import ScenarioConfig
from .student_condition import StudentCondition


def validate_feedback_episode(controller):
    config = controller.environment.config
    if len(controller.snapshots) != config.horizon or len(controller.decisions) != config.horizon:
        raise ValueError("episode does not contain exactly the configured decisions")
    seen = set()
    previous_budget = config.budget
    for snapshot, decision, record in zip(controller.snapshots, controller.decisions, controller.environment.records):
        snapshot.validate_estimates()
        validate_allocation(snapshot, record.allocation.assignments)
        ids = {a.student_id for a in record.allocation.assignments}
        if ids & seen:
            raise ValueError("student received a repeated programme")
        seen.update(ids)
        if (snapshot.remaining_budget != previous_budget or record.remaining_budget < 0
                or decision["admitted_ids"] != tuple(a.student_id for a in record.allocation.assignments)):
            raise ValueError("trace admission/resource mismatch")
        spending = sum(a.cost_units for a in record.allocation.assignments)
        if abs(previous_budget - spending - record.remaining_budget) > 1e-8:
            raise ValueError("resource ledger does not balance")
        previous_budget = record.remaining_budget
    return True


class FixedMonitoringRecords:
    """A deterministic information-flow fixture; no population-level claim."""
    def __init__(self, changed):
        self.changed = changed
        self.config = ObservationConfig()

    def generate(self, conditions, *, month, seed, assignments=()):
        ids = sorted(sid for sid, _ in conditions)
        events = tuple(ObservableEvent(f"{sid}:{month}", sid, month, month + 1,
            "low_participation" if self.changed and month == 1 and sid == ids[2]
            else "regular_participation") for sid in ids)
        registry = tuple(EnrollmentRecord(sid, month, month + 1, state != StudentCondition.WITHDRAWN)
                         for sid, state in conditions)
        return events, registry


def save_feedback_demonstration(output):
    """Same seed/actions through month 1, one changed note, different month-2 admission."""
    from .feedback_experiments import save_episode

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    config = ScenarioConfig(num_students=3, num_mentors=1, horizon=3, monthly_admissions=1,
                            monthly_appointments=5, budget=15, seed=42)
    runs = []
    for label, changed in (("unchanged", False), ("new_monitoring_evidence", True)):
        controller = ClosedLoopCMDPController(build_school(config).create_cmdp_environment(config=config),
            ConstrainedAllocationPlanner(), mode="llm_notes", extractor=FixtureObservationExtractor())
        controller.observation_model = FixedMonitoringRecords(changed)
        controller.run_episode()
        validate_feedback_episode(controller)
        save_episode(controller, output / label)
        runs.append(controller)
    before, after = runs
    if (before.decisions[0]["admitted_ids"] != after.decisions[0]["admitted_ids"]
            or before.evaluator_truth[1] != after.evaluator_truth[1]
            or before.decisions[1]["admitted_ids"] == after.decisions[1]["admitted_ids"]):
        raise ValueError("fixture did not demonstrate a causal feedback allocation change")
    summary = {"seed": config.seed, "fixture": "fixed_observable_records_not_a_statistical_experiment",
        "first_admission_both_runs": before.decisions[0]["admitted_ids"],
        "month_1_truth_and_actions_equal": True,
        "month_2_without_new_evidence": before.decisions[1]["admitted_ids"],
        "month_2_with_new_evidence": after.decisions[1]["admitted_ids"],
        "month_2_benefits_without_new_evidence": before.decisions[1]["benefits"],
        "month_2_benefits_with_new_evidence": after.decisions[1]["benefits"],
        "changed_note": asdict(next(n for n in after.notes
            if n.event_month == 1 and n.student_id == after.decisions[1]["admitted_ids"][0]))}
    (output / "feedback_allocation_evidence.json").write_text(json.dumps(summary, indent=2))
    return summary

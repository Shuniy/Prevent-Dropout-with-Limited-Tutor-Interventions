"""A policy receives a snapshot, never the environment or future draws."""

from dataclasses import dataclass

from .mentor_resource import MentorResource
from .student_observation import StudentObservation


@dataclass(frozen=True)
class DecisionState:
    month: int
    months_remaining: int
    remaining_budget: float
    students: tuple[StudentObservation, ...]
    mentors: tuple[MentorResource, ...]
    observation_mode: str = "fully_observed_benchmark"
    remaining_budget_exact: str | None = None
    # Announced mentor calendar only: no future student conditions or random draws.
    known_mentor_schedule: tuple[tuple[int, tuple[MentorResource, ...]], ...] = ()
    estimated_student_states: tuple = ()
    risk_estimates: tuple = ()

    def validate_estimates(self):
        """Only actual decisions require current risks; forecasts retain the cutoff."""
        if self.observation_mode != "estimated_state_v1":
            return
        estimates = {s.student_id: s for s in self.estimated_student_states}
        risks = {r.student_id: r for r in self.risk_estimates}
        ids = {s.student_id for s in self.students}
        if (set(estimates) != ids or set(risks) != ids
                or len(estimates) != len(self.estimated_student_states)
                or len(risks) != len(self.risk_estimates)):
            raise ValueError("decision requires unique estimates and risks for every student")
        for student in self.students:
            estimate, risk = estimates[student.student_id], risks[student.student_id]
            if (estimate.as_of_month != self.month or risk.as_of_month != self.month
                    or risk.months_remaining != self.months_remaining
                    or risk.input_belief_version != estimate.estimate_id
                    or student.estimate_version != estimate.estimate_id
                    or student.condition_probabilities != estimate.condition_probabilities):
                raise ValueError("stale or mismatched estimate/risk decision cutoff")

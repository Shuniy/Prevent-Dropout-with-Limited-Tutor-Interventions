"""Feasible selected programmes and solver diagnostics."""

from dataclasses import dataclass

from .mentor_assignment import MentorAssignment


@dataclass(frozen=True)
class AllocationResult:
    assignments: tuple[MentorAssignment, ...] = ()
    status: str = "baseline"
    objective: float = 0.0
    runtime_seconds: float = 0.0
    optimality_gap: float | None = None
    objective_bound: float | None = None
    message: str = ""
    fairness_shortfall: float | None = None
    eligible_student_count: int = 0
    candidate_pair_count: int = 0
    decision_variable_count: int = 0
    available_mentor_count: int = 0
    remaining_budget: float | None = None
    current_month: int | None = None
    months_remaining: int | None = None
    benefit_estimator_version: str | None = None
    planner_version: str | None = None
    solver_version: str | None = None
    solver_settings: tuple = ()
    lexicographic_complete: bool = False
    validation_failures: int = 0
    total_programme_cost: float = 0.0
    selected_student_count: int = 0
    estimated_total_benefit: float = 0.0

    def __post_init__(self):
        # Copy a caller's list into a tuple before it enters historical records.
        if any(not isinstance(item, MentorAssignment) for item in self.assignments):
            raise ValueError("allocations must contain immutable MentorAssignment records")
        object.__setattr__(self, "assignments", tuple(self.assignments))
        object.__setattr__(self, "total_programme_cost", sum(a.cost_units for a in self.assignments))
        object.__setattr__(self, "selected_student_count", len(self.assignments))
        object.__setattr__(self, "estimated_total_benefit", self.objective)

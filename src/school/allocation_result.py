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

    def __post_init__(self):
        # Copy a caller's list into a tuple before it enters historical records.
        if any(not isinstance(item, MentorAssignment) for item in self.assignments):
            raise ValueError("allocations must contain immutable MentorAssignment records")
        object.__setattr__(self, "assignments", tuple(self.assignments))

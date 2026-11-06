"""Immutable controller beliefs and their evidence provenance."""

from dataclasses import dataclass
import math

from .student_condition import STATES, StudentCondition


def validate_belief(values):
    values = tuple(float(v) for v in values)
    if (len(values) != 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in values)
            or not math.isclose(sum(values), 1, abs_tol=1e-12, rel_tol=0)):
        raise ValueError("belief must be a normalized four-condition distribution")
    return values


@dataclass(frozen=True)
class EstimatedStudentState:
    student_id: str
    as_of_month: int
    condition_probabilities: tuple[float, ...]
    estimate_id: str
    evidence_ids: tuple[str, ...] = ()
    unresolved_observations: tuple = ()
    observed_support_history: tuple = ()
    observation_uncertainty: tuple = ()
    last_observation_month: int | None = None
    # Source-time evidence for deterministic late-arrival filtering; no truth.
    observation_history: tuple = ()
    enrollment_history: tuple = ()
    known_actions: tuple[int, ...] = ()

    def __post_init__(self):
        validate_belief(self.condition_probabilities)
        if type(self.as_of_month) is not int or self.as_of_month < 1:
            raise ValueError("belief as-of month must be positive")
        if not self.estimate_id:
            raise ValueError("belief requires an estimate identity")

    @property
    def estimated_condition(self) -> StudentCondition:
        return STATES[max(range(4), key=self.condition_probabilities.__getitem__)]

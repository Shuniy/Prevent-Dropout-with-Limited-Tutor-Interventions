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

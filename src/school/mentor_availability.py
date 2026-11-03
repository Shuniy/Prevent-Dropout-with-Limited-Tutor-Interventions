"""Mentor capacity in one allocation month."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MentorAvailability:
    """A mentor's resource limits for one simulation step."""

    step: int
    available_hours: float
    max_sessions: int

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("step must be non-negative")
        if self.available_hours < 0:
            raise ValueError("available_hours must be non-negative")
        if self.max_sessions < 0:
            raise ValueError("max_sessions must be non-negative")

"""Synthetic mentor resources used by the allocation simulation."""

from dataclasses import dataclass, field
from typing import Literal


SupportType = Literal["tutoring", "family_liaison", "transport_assessment"]

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


@dataclass
class Mentor:
    """A configurable mentor with explicit skills and capacity constraints.

    Mentor records are assumptions or generated scenario data; the source data
    contains no observed mentor population.
    """

    mentor_id: str
    support_types: list[SupportType] = field(default_factory=list)
    max_active_students: int = 0
    current_student_ids: list[str] = field(default_factory=list)
    availability_by_step: list[MentorAvailability] = field(default_factory=list)
    cost_units_per_hour: float = 0.0

    def __post_init__(self) -> None:
        if not self.mentor_id:
            raise ValueError("mentor_id must not be empty")
        if self.max_active_students < 0:
            raise ValueError("max_active_students must be non-negative")
        if self.cost_units_per_hour < 0:
            raise ValueError("cost_units_per_hour must be non-negative")
        if len(self.current_student_ids) != len(set(self.current_student_ids)):
            raise ValueError("current_student_ids must not contain duplicates")
        if self.current_caseload > self.max_active_students:
            raise ValueError("current caseload exceeds max_active_students")

        steps = [availability.step for availability in self.availability_by_step]
        if len(steps) != len(set(steps)):
            raise ValueError("availability_by_step must contain one entry per step")

    @property
    def current_caseload(self) -> int:
        return len(self.current_student_ids)

    @property
    def remaining_capacity(self) -> int:
        return self.max_active_students - self.current_caseload

    def supports(self, support_type: SupportType) -> bool:
        """Return whether the mentor is eligible for a support request."""

        supports_type = support_type in self.support_types
        return supports_type

    def availability_at(self, step: int) -> MentorAvailability | None:
        """Return this mentor's availability record for ``step``, if present."""

        return next(
            (
                availability
                for availability in self.availability_by_step
                if availability.step == step
            ),
            None,
        )

    def can_accept_student(
        self,
        student_id: str,
        support_type: SupportType,
        step: int,
        *,
        program_id: str | None = None,
        required_hours: float = 0.0,
    ) -> bool:
        """Check skill, programme, caseload, and step-resource feasibility."""

        if required_hours < 0:
            raise ValueError("required_hours must be non-negative")
        if student_id in self.current_student_ids or self.remaining_capacity <= 0:
            return False

        availability = self.availability_at(step)
        return (
            availability is not None
            and availability.max_sessions > 0
            and availability.available_hours >= required_hours
        )

    def assign_student(self, student_id: str) -> None:
        """Add a student to the active caseload without overbooking."""

        if student_id in self.current_student_ids:
            raise ValueError(f"student {student_id!r} is already assigned")
        if self.remaining_capacity <= 0:
            raise ValueError("mentor has no remaining student capacity")
        self.current_student_ids.append(student_id)

    def release_student(self, student_id: str) -> None:
        """Remove a student from the active caseload."""

        if student_id not in self.current_student_ids:
            raise ValueError(f"student {student_id!r} is not assigned")
        self.current_student_ids.remove(student_id)

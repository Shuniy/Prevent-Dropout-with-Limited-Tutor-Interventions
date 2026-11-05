"""Read-only monthly mentor resources supplied to every policy."""

from dataclasses import dataclass

from ..utils.enums import SupportType


@dataclass(frozen=True)
class MentorResource:
    mentor_id: str
    support_types: tuple[SupportType, ...]
    admissions: int
    appointments: int
    cost_per_appointment: float
    compatible_student_ids: tuple[str, ...]

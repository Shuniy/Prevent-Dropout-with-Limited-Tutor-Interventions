"""A planned allocation and its recorded participation."""

from dataclasses import dataclass
from ..utils.enums import SupportType


@dataclass(frozen=True)
class MentorAssignment:
    """One mentor allocation made by the school."""

    student_id: str
    mentor_id: str
    support_type: SupportType
    month: int
    sessions: int
    cost_units: float
    completed_sessions: int | None = None

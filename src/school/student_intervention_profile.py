"""Mutable state for one student programme."""

from dataclasses import dataclass, field
from ..utils.enums import SupportType


@dataclass
class StudentInterventionProfile:
    student_id: str
    support_type: SupportType
    planned_sessions: int
    mentor_id: str | None = None
    history_id: str | None = None
    sessions_completed: int = 0
    status: str = "unassigned"
    session_reports: list[dict] = field(default_factory=list)

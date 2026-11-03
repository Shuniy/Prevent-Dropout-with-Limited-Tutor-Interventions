"""The explicit allowlist of information permitted to leave intervention."""

from dataclasses import dataclass
from .intervention_request import InterventionRequest
from ..utils.enums import SupportType


@dataclass(frozen=True)
class InterventionResult:
    run_id: str
    programme_id: str
    month: int
    student_id: str
    mentor_id: str
    support_type: SupportType
    planned_sessions: int
    sessions_completed: int
    status: str
    analysis_status: str
    attendance_improved: str = "unknown"
    primary_barrier_resolved: str = "unknown"
    intervention_helpful: str = "unknown"

    def __post_init__(self) -> None:
        InterventionRequest(self.run_id, self.programme_id, self.month, self.student_id,
                            self.mentor_id, self.support_type, self.planned_sessions)
        if type(self.sessions_completed) is not int or not 0 <= self.sessions_completed <= self.planned_sessions:
            raise ValueError("completed sessions must be within the planned programme")
        if self.status not in {"completed", "incomplete", "unavailable"}:
            raise ValueError("invalid programme status")
        if self.analysis_status not in {"completed", "failed", "unavailable"}:
            raise ValueError("invalid analysis status")
        if self.status == "completed" and self.sessions_completed != self.planned_sessions:
            raise ValueError("completed programme requires the planned attendance")
        if self.status == "incomplete" and not 0 < self.sessions_completed < self.planned_sessions:
            raise ValueError("incomplete programme requires a short recorded history")
        if (self.status == "unavailable") != (self.analysis_status == "unavailable"):
            raise ValueError("unavailable history and analysis statuses must agree")
        if self.status == "unavailable" and self.sessions_completed:
            raise ValueError("unavailable programme cannot record attendance")
        for value in (self.attendance_improved, self.primary_barrier_resolved):
            if value not in {"yes", "no", "partial", "unknown", "conflicting"}:
                raise ValueError("invalid reported outcome")
        if self.intervention_helpful not in {"yes", "no", "mixed", "unknown", "conflicting"}:
            raise ValueError("invalid helpfulness outcome")
        if self.analysis_status != "completed" and any(value != "unknown" for value in (
                self.attendance_improved, self.primary_barrier_resolved, self.intervention_helpful)):
            raise ValueError("failed or unavailable analysis must leave outcomes unknown")

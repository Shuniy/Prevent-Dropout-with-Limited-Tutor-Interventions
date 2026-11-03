"""Immutable, minimal school input for one confidential programme."""

from dataclasses import dataclass
from ..utils.constants import ALL_SUPPORT_TYPES
from ..utils.enums import SupportType


@dataclass(frozen=True)
class InterventionRequest:
    run_id: str
    programme_id: str
    month: int
    student_id: str
    mentor_id: str
    support_type: SupportType
    planned_sessions: int

    def __post_init__(self) -> None:
        for value in (self.run_id, self.programme_id, self.student_id, self.mentor_id):
            if not isinstance(value, str) or not value:
                raise ValueError("run, programme, student and mentor IDs must be nonempty strings")
        if type(self.month) is not int or self.month < 1:
            raise ValueError("month must be a positive integer")
        if type(self.planned_sessions) is not int or self.planned_sessions < 1:
            raise ValueError("planned_sessions must be a positive integer")
        if self.support_type not in ALL_SUPPORT_TYPES:
            raise ValueError("unknown support type")

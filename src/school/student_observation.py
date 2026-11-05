"""Immutable controller inputs; hidden truth is absent in partial mode."""

from dataclasses import dataclass

from ..utils.enums import SupportType
from .student_condition import StudentCondition


@dataclass(frozen=True)
class StudentObservation:
    student_id: str
    enrolled: bool
    condition: StudentCondition | None
    support_type: SupportType
    need_score: float
    programme_months: tuple[int, ...]
    waiting_months: int
    disadvantage_proxy: bool
    sex_source: str

    @property
    def eligible(self) -> bool:
        return self.enrolled and not self.programme_months

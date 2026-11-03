"""One student's before/after evaluation in a school month."""

from dataclasses import dataclass
from .performance_snapshot import PerformanceSnapshot


@dataclass(frozen=True)
class MonthlyEvaluation:
    month: int
    student_id: str
    before: PerformanceSnapshot
    after: PerformanceSnapshot

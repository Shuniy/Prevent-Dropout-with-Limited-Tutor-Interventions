"""School-owned runtime measures, separate from unchanged source records."""

from dataclasses import dataclass


@dataclass
class StudentPerformance:
    anchor_grade: float
    math_grade: float | None
    attendance_fraction: float | None
    engagement: float | None
    enrolled: bool | None
    support_sessions_completed: int = 0
    attendance_improved: str = "unknown"
    primary_barrier_resolved: str = "unknown"
    intervention_helpful: str = "unknown"
    evaluation_reason: str = "baseline"

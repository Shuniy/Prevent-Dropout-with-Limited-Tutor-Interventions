"""Immutable performance measurements retained for monthly comparison."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceSnapshot:
    anchor_grade: float
    math_grade: float | None
    attendance_fraction: float | None
    engagement: float | None
    enrolled: bool | None
    support_sessions_completed: int
    attendance_improved: str
    primary_barrier_resolved: str
    intervention_helpful: str
    evaluation_reason: str
    need_score: float
    primary_support_type: str

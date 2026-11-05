"""Immutable realized month, recorded after every student's transition."""

from dataclasses import dataclass

from .allocation_result import AllocationResult
from .student_condition import StudentCondition


@dataclass(frozen=True)
class MonthRecord:
    month: int
    conditions: tuple[tuple[str, StudentCondition], ...]
    remaining_budget: float
    allocation: AllocationResult

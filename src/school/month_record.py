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
    mentor_capacities: tuple[tuple[str, int, int], ...]
    mean_eligible_waiting_months: float
    waiting_months: tuple[tuple[str, int], ...]
    recipient_waiting_months: tuple[int, ...]

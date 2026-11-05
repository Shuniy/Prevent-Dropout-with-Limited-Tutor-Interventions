"""Allowlisted reported outcomes from the existing extraction contract."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuredObservation:
    student_id: str
    observed_month: int
    programme_id: str
    attendance_improved: str
    primary_barrier_resolved: str
    intervention_helpful: str
    analysis_status: str

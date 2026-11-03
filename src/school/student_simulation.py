"""Student inputs for the simulation."""

from dataclasses import dataclass
from .student import Student


@dataclass
class StudentSimulation(Student):
    initial_attendance_fraction_assumed: float
    initial_engagement_assumed: float
    weeks_since_offer: int
    support_sessions_completed: int
    enrolled_initial_assumed: bool
    financial_need_verified: bool | None

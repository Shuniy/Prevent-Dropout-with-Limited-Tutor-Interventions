"""Private programme state; never attached to a school or exported there."""

from dataclasses import dataclass, field
from .intervention_request import InterventionRequest


@dataclass
class StudentInterventionProfile:
    request: InterventionRequest
    history_id: str | None
    sessions_completed: int = 0
    session_reports: list[dict] = field(default_factory=list)
    error: str | None = None

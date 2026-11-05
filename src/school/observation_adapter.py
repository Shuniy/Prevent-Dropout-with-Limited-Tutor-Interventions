"""Reports are evidence for a future estimator, never ground-truth effects."""

from ..intervention.intervention_result import InterventionResult
from .structured_observation import StructuredObservation


def observation_from_result(result: InterventionResult, current_month: int):
    """Admission-month outcomes become available at the next decision boundary.

    No rule maps 'helpful' to a risk reduction or simulated condition. A future
    explicit estimator must supply ConditionEstimate separately. Recorded notes
    are not claimed to be synchronized with this synthetic environment.
    """
    if not isinstance(result, InterventionResult):
        raise ValueError("observation adapter requires a validated InterventionResult")
    if result.month >= current_month:
        raise ValueError("programme results are available only after their admission month")
    return StructuredObservation(
        result.student_id,
        result.month + 1,
        result.programme_id,
        result.attendance_improved,
        result.primary_barrier_resolved,
        result.intervention_helpful,
        result.analysis_status,
    )

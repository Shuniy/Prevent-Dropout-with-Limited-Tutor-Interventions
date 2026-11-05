"""Model-derived synthetic endpoint risk under no additional programmes."""

from dataclasses import dataclass
import numpy as np

from .retention_value import wait_values
from .transition_model import P_WAIT, validate_matrix


@dataclass(frozen=True)
class RiskEstimate:
    student_id: str
    probability: float
    months_remaining: int
    as_of_month: int
    input_belief_version: str
    estimator_version: str
    uncertainty: tuple
    reference_policy: str = "WAIT_no_additional_programmes"
    target: str = "synthetic_terminal_non_enrollment"


class SimulatedWithdrawalRiskEstimator:
    VERSION = "synthetic_wait_endpoint_risk_v1"

    def __init__(self, wait_matrix=P_WAIT):
        self.wait = validate_matrix(wait_matrix)

    def predict(self, estimated_state, months_remaining):
        if type(months_remaining) is not int or months_remaining < 0:
            raise ValueError("risk horizon must be a non-negative integer")
        risk = 1 - np.asarray(estimated_state.condition_probabilities) @ wait_values(self.wait, months_remaining)
        return RiskEstimate(estimated_state.student_id, float(np.clip(risk, 0, 1)), months_remaining,
                            estimated_state.as_of_month, estimated_state.estimate_id, self.VERSION,
                            estimated_state.observation_uncertainty)

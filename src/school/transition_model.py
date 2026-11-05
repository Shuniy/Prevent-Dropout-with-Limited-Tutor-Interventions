"""Assumed monthly probabilities; no empirical or causal calibration is claimed."""

import hashlib
import json

import numpy as np

from .student_condition import STATES, StudentCondition


P_WAIT = np.array(
    [
        [0.88, 0.10, 0.015, 0.005],
        [0.15, 0.65, 0.17, 0.03],
        [0.03, 0.17, 0.65, 0.15],
        [0.00, 0.00, 0.00, 1.00],
    ]
)
P_PROGRAMME = np.array(
    [
        [0.94, 0.05, 0.008, 0.002],
        [0.35, 0.53, 0.10, 0.02],
        [0.10, 0.35, 0.47, 0.08],
        [0.00, 0.00, 0.00, 1.00],
    ]
)
P_WAIT.setflags(write=False)
P_PROGRAMME.setflags(write=False)


def validate_matrix(matrix) -> np.ndarray:
    probabilities = np.array(matrix, dtype=float, copy=True)
    if probabilities.shape != (4, 4):
        raise ValueError("transition matrix must have shape (4, 4)")
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities < 0)
        or np.any(probabilities > 1)
    ):
        raise ValueError("transition probabilities must be finite and within [0, 1]")
    if not np.allclose(probabilities.sum(axis=1), 1, atol=1e-12, rtol=0):
        raise ValueError("transition rows must sum to one")
    if not np.array_equal(probabilities[3], [0, 0, 0, 1]):
        raise ValueError("simulated withdrawal must be absorbing")
    probabilities.setflags(write=False)
    return probabilities


def programme_matrix(alpha: float = 1.0) -> np.ndarray:
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("effect strength alpha must be within [0, 1]")
    # P_alpha = P_wait + alpha * (P_programme - P_wait).
    return validate_matrix(P_WAIT + alpha * (P_PROGRAMME - P_WAIT))


def keyed_uniform(seed: int, student_id: str, month: int, event_type: str) -> float:
    """Stable keys avoid Python hash randomization and action-dependent draw counts."""
    key = json.dumps([seed, student_id, month, event_type], separators=(",", ":"))
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    # Use 53 bits so conversion to float always gives 0 <= U < 1.
    return (int.from_bytes(digest[:8], "big") >> 11) / 2**53


def sample_condition(condition, matrix, uniform: float) -> StudentCondition:
    if not 0 <= uniform < 1:
        raise ValueError("transition draw must be within [0, 1)")
    row = matrix[STATES.index(StudentCondition(condition))]
    index = min(int(np.searchsorted(np.cumsum(row), uniform, side="right")), 3)
    return STATES[index]

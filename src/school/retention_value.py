"""Deterministic terminal values; these are rollout benefits, not optimal Q values."""

import numpy as np
from functools import lru_cache

from .student_condition import STATES, StudentCondition
from .transition_model import validate_matrix


@lru_cache(maxsize=128)
def _value_table(matrix_key, horizon):
    matrix = np.asarray(matrix_key).reshape(4, 4)
    values = np.empty((horizon + 1, 4))
    values[0] = [1, 1, 1, 0]
    for month in range(horizon):
        values[month + 1] = matrix @ values[month]
    values.setflags(write=False)
    return values


def wait_values(matrix, horizon):
    # All twelve decision horizons share one cached backward-propagation table.
    return _value_table(tuple(matrix.ravel()), max(12, horizon))[horizon]


def expected_terminal_retention(condition, months_remaining, transition_matrix) -> float:
    if type(months_remaining) is not int or months_remaining < 0:
        raise ValueError("months_remaining must be a non-negative integer")
    matrix = validate_matrix(transition_matrix)
    # V_wait_h(s) = [P_wait ** h @ e]_s, where e = [1, 1, 1, 0].
    values = wait_values(matrix, months_remaining)
    return float(np.clip(values[STATES.index(StudentCondition(condition))], 0, 1))


def estimate_incremental_benefit(
    condition, months_remaining, wait_matrix, programme_matrix
) -> float:
    if type(months_remaining) is not int or months_remaining < 1:
        raise ValueError("benefit requires at least one remaining transition")
    wait = validate_matrix(wait_matrix)
    programme = validate_matrix(programme_matrix)
    # Delta(s) = [(P_programme - P_wait) @ P_wait ** (h - 1) @ e]_s.
    continuation = wait_values(wait, months_remaining - 1)
    benefits = (programme - wait) @ continuation
    return float(benefits[STATES.index(StudentCondition(condition))])


def estimate_all_student_benefits(state, wait_matrix, programme_matrix):
    benefits = {}
    by_condition = {}
    for student in state.students:
        if student.eligible:
            if student.condition_probabilities:
                benefits[student.student_id] = estimate_belief_benefit(
                    student.condition_probabilities, state.months_remaining,
                    wait_matrix, programme_matrix)
                continue
            if student.condition is None:
                raise ValueError(
                    "retention planning requires an explicit observed or estimated condition"
                )
            if student.condition not in by_condition:
                by_condition[student.condition] = estimate_incremental_benefit(
                    student.condition,
                    state.months_remaining,
                    wait_matrix,
                    programme_matrix,
                )
            benefits[student.student_id] = by_condition[student.condition]
    return benefits


def estimate_belief_benefit(probabilities, months_remaining, wait_matrix, programme_matrix):
    """b @ (P_programme - P_wait) @ P_wait**(h-1) @ e; risk is separate."""
    if type(months_remaining) is not int or months_remaining < 1:
        raise ValueError("benefit requires at least one remaining transition")
    from .belief_state import validate_belief
    belief = np.asarray(validate_belief(probabilities))
    wait, programme = validate_matrix(wait_matrix), validate_matrix(programme_matrix)
    return float(belief @ (programme - wait) @ wait_values(wait, months_remaining - 1))

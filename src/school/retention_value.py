"""Deterministic terminal values; these are rollout benefits, not optimal Q values."""

import numpy as np

from .student_condition import STATES, StudentCondition
from .transition_model import validate_matrix


def expected_terminal_retention(condition, months_remaining, transition_matrix) -> float:
    if type(months_remaining) is not int or months_remaining < 0:
        raise ValueError("months_remaining must be a non-negative integer")
    matrix = validate_matrix(transition_matrix)
    # V_wait_h(s) = [P_wait ** h @ e]_s, where e = [1, 1, 1, 0].
    values = np.linalg.matrix_power(matrix, months_remaining) @ np.array([1, 1, 1, 0])
    return float(values[STATES.index(StudentCondition(condition))])


def estimate_incremental_benefit(
    condition, months_remaining, wait_matrix, programme_matrix
) -> float:
    if type(months_remaining) is not int or months_remaining < 1:
        raise ValueError("benefit requires at least one remaining transition")
    wait = validate_matrix(wait_matrix)
    programme = validate_matrix(programme_matrix)
    # Delta(s) = [(P_programme - P_wait) @ P_wait ** (h - 1) @ e]_s.
    continuation = np.linalg.matrix_power(wait, months_remaining - 1) @ np.array([1, 1, 1, 0])
    benefits = (programme - wait) @ continuation
    return float(benefits[STATES.index(StudentCondition(condition))])


def estimate_all_student_benefits(state, wait_matrix, programme_matrix):
    benefits = {}
    by_condition = {}
    for student in state.students:
        if student.eligible:
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

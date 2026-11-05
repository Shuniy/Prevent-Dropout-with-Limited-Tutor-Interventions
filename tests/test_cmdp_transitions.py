from dataclasses import asdict, replace
import unittest

import numpy as np

from src.school.allocation_result import AllocationResult
from src.school.constraints import candidate_assignments
from src.school.cmdp_environment import CMDPEnvironment, initial_condition
from src.school.student_condition import STATES, StudentCondition
from src.school.retention_value import expected_terminal_retention, estimate_incremental_benefit
from src.school.transition_model import (
    P_WAIT,
    P_PROGRAMME,
    keyed_uniform,
    programme_matrix,
    sample_condition,
    validate_matrix,
)
from tests.cmdp_helpers import environment


class TransitionTests(unittest.TestCase):
    def test_matrices_and_sensitivity(self):
        for alpha in (0, 0.25, 0.5, 1):
            matrix = programme_matrix(alpha)
            np.testing.assert_allclose(matrix.sum(axis=1), 1)
            np.testing.assert_array_equal(matrix[3], [0, 0, 0, 1])
        for invalid in (np.zeros((4, 4)), np.full((4, 4), np.nan), [[1]], P_WAIT - 1):
            with self.assertRaises(ValueError):
                validate_matrix(invalid)
        with self.assertRaises(ValueError):
            programme_matrix(1.01)

    def test_initialization_order_boundaries_and_unknowns(self):
        _, students, _ = environment(1)
        student = replace(
            students[0],
            initial_attendance_fraction_assumed=0.9,
            initial_engagement_assumed=0.8,
            anchor_grade1_0_20=15,
        )
        self.assertEqual(initial_condition(student), StudentCondition.STABLE)
        for changes, expected in (
            ({"initial_attendance_fraction_assumed": 0.69}, StudentCondition.DISENGAGED),
            ({"initial_engagement_assumed": 0.39}, StudentCondition.DISENGAGED),
            ({"initial_attendance_fraction_assumed": 0.70}, StudentCondition.VULNERABLE),
            ({"initial_engagement_assumed": 0.59}, StudentCondition.VULNERABLE),
            ({"anchor_grade1_0_20": 7}, StudentCondition.VULNERABLE),
            ({"enrolled_initial_assumed": False}, None),
        ):
            self.assertEqual(initial_condition(replace(student, **changes)), expected)
        for name in (
            "enrolled_initial_assumed",
            "initial_attendance_fraction_assumed",
            "initial_engagement_assumed",
        ):
            with self.assertRaisesRegex(ValueError, "known"):
                initial_condition(replace(student, **{name: None}))

    def test_rollout_values_against_matrix_powers_and_one_step(self):
        for state_index, condition in enumerate(STATES):
            for horizon in (0, 1, 3, 12):
                expected = (np.linalg.matrix_power(P_WAIT, horizon) @ [1, 1, 1, 0])[state_index]
                self.assertAlmostEqual(
                    expected_terminal_retention(condition, horizon, P_WAIT), expected
                )
            self.assertAlmostEqual(
                estimate_incremental_benefit(condition, 1, P_WAIT, P_PROGRAMME),
                P_WAIT[state_index, 3] - P_PROGRAMME[state_index, 3],
            )
        self.assertAlmostEqual(
            expected_terminal_retention(StudentCondition.DISENGAGED, 1, P_WAIT), 0.85
        )
        with self.assertRaises(ValueError):
            estimate_incremental_benefit(StudentCondition.STABLE, 0, P_WAIT, P_PROGRAMME)

    def test_every_student_transitions_from_current_state_and_source_stays_unchanged(self):
        env, students, _ = environment(4)
        originals = [asdict(student) for student in students]
        for month in range(1, 13):
            state = env.observe()
            candidates = candidate_assignments(state)
            assignments = candidates[:1] if month == 1 else ()
            selected = {item.student_id for item in assignments}
            record = env.step(AllocationResult(assignments))
            self.assertEqual(record.month, month)
            self.assertEqual(len(record.conditions), 4)
            for student in state.students:
                matrix = P_PROGRAMME if student.student_id in selected else P_WAIT
                expected = sample_condition(
                    student.condition,
                    matrix,
                    keyed_uniform(
                        env.config.seed, student.student_id, month, "environment_transition"
                    ),
                )
                self.assertEqual(dict(record.conditions)[student.student_id], expected)
        self.assertEqual(originals, [asdict(student) for student in students])
        self.assertEqual(env.terminal_reward(), sum(s.enrolled for s in env.observe().students))
        with self.assertRaises(ValueError):
            env.step(AllocationResult())

    def test_withdrawal_absorbing_and_non_enrolled_excluded(self):
        for matrix in (P_WAIT, P_PROGRAMME):
            for draw in (0, 0.5, 0.99999):
                self.assertEqual(
                    sample_condition(StudentCondition.WITHDRAWN, matrix, draw),
                    StudentCondition.WITHDRAWN,
                )
        env, students, mentors = environment(2)
        students[0].enrolled_initial_assumed = False
        env = CMDPEnvironment(students, mentors, env.config)
        self.assertEqual(env.excluded_student_ids, (students[0].student_id,))
        self.assertEqual(len(env.observe().students), 1)


if __name__ == "__main__":
    unittest.main()

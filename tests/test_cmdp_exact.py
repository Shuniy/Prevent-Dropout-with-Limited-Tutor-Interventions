from dataclasses import replace
import unittest

from src.school.constraints import validate_allocation
from src.school.student_condition import StudentCondition
from src.school.exact_tiny_mdp import ExactTinyMDP
from src.school.retention_value import expected_terminal_retention
from src.school.transition_model import P_WAIT
from tests.cmdp_helpers import environment


class ExactTests(unittest.TestCase):
    def test_no_budget_equals_additive_wait_value(self):
        env, _, _ = environment(3, horizon=2, budget=0)
        state = env.observe()
        comparison = ExactTinyMDP(state).compare()
        expected = sum(
            expected_terminal_retention(student.condition, 2, P_WAIT) for student in state.students
        )
        self.assertAlmostEqual(comparison["exact_expected_terminal_enrollment"], expected)
        self.assertAlmostEqual(comparison["objective_gap"], 0)

    def test_one_month_matches_monthly_objective(self):
        env, _, _ = environment(2, horizon=1, budget=5, num_mentors=1)
        comparison = ExactTinyMDP(env.observe()).compare()
        self.assertAlmostEqual(comparison["objective_gap"], 0)
        validate_allocation(env.observe(), comparison["exact_first_action"])

    def test_waiting_option_exposes_heuristic_gap(self):
        env, _, _ = environment(2, horizon=3, budget=5, num_mentors=1)
        state = env.observe()
        state = replace(
            state,
            students=tuple(
                replace(student, condition=StudentCondition.STABLE) for student in state.students
            ),
        )
        comparison = ExactTinyMDP(state).compare()
        self.assertGreater(comparison["objective_gap"], 0)
        self.assertEqual(comparison["exact_first_student_ids"], [])
        self.assertEqual(len(comparison["heuristic_first_student_ids"]), 1)
        validate_allocation(state, comparison["exact_first_action"])

    def test_reference_limits(self):
        env, _, _ = environment(5, horizon=2)
        with self.assertRaises(ValueError):
            ExactTinyMDP(env.observe())

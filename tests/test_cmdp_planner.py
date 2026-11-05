from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import patch
import unittest

import numpy as np

from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.constraints import validate_allocation
from src.school.exact_tiny_mdp import enumerate_allocations
from src.school.retention_value import estimate_all_student_benefits
from src.school.cmdp_scenarios import build_environment, run_episode
from src.school.scenario_config import ScenarioConfig
from src.school.transition_model import P_WAIT, P_PROGRAMME
from src.school.student_condition import StudentCondition
from tests.cmdp_helpers import environment


class PlannerTests(unittest.TestCase):
    def test_heterogeneous_prices_and_capacity_match_exhaustive_solution(self):
        env, _, _ = environment(3, horizon=1, budget=15, monthly_admissions=1)
        state = env.observe()
        students = tuple(
            replace(student, condition=condition)
            for student, condition in zip(
                state.students,
                (StudentCondition.DISENGAGED, StudentCondition.VULNERABLE, StudentCondition.STABLE),
            )
        )
        mentors = (state.mentors[0], replace(state.mentors[1], cost_per_appointment=2))
        state = replace(state, students=students, mentors=mentors)
        allocation = ConstrainedAllocationPlanner().plan(state)
        benefits = estimate_all_student_benefits(state, P_WAIT, P_PROGRAMME)
        best = max(
            sum(benefits[item.student_id] for item in action)
            for action in enumerate_allocations(state)
        )
        self.assertAlmostEqual(allocation.objective, best)
        self.assertAlmostEqual(sum(item.cost_units for item in allocation.assignments), 15)
        validate_allocation(state, allocation.assignments)

    def test_monthly_milp_matches_exhaustive_objective(self):
        env, _, _ = environment(4, budget=5, num_mentors=2, monthly_admissions=1)
        state = env.observe()
        benefits = estimate_all_student_benefits(state, P_WAIT, P_PROGRAMME)
        best = max(
            sum(benefits[item.student_id] for item in action)
            for action in enumerate_allocations(state)
        )
        allocation = ConstrainedAllocationPlanner().plan(state)
        self.assertEqual(allocation.status, "optimal")
        self.assertAlmostEqual(allocation.objective, best)
        self.assertAlmostEqual(allocation.optimality_gap, 0)
        validate_allocation(state, allocation.assignments)

    def test_solver_failure_and_fractional_or_overbooked_outputs_are_explicit(self):
        env, _, _ = environment(3, num_mentors=1, monthly_admissions=1)
        state = env.observe()
        for status, vector, expected in (
            (2, None, "infeasible_wait_fallback"),
            (1, None, "limit_wait_fallback"),
            (0, np.full(3, 0.5), "invalid_incumbent_wait_fallback"),
            (0, np.ones(3), "invalid_incumbent_wait_fallback"),
            (0, np.array([1.0000003, -0.0000003, 0]), "optimal"),
            (1, np.array([1, 0, 0]), "feasible_limit"),
        ):
            result = SimpleNamespace(status=status, x=vector, message="test")
            with patch("src.school.constrained_planner.solve_milp", return_value=result):
                allocation = ConstrainedAllocationPlanner().plan(state)
            self.assertEqual(allocation.status, expected)
            validate_allocation(state, allocation.assignments)

    def test_empty_and_null_effect(self):
        env, _, _ = environment(budget=0)
        self.assertEqual(ConstrainedAllocationPlanner().plan(env.observe()).status, "no_candidates")
        env, _, _ = environment()
        allocation = ConstrainedAllocationPlanner(treatment_matrix=P_WAIT).plan(env.observe())
        self.assertEqual(allocation.status, "zero_benefit")
        self.assertFalse(allocation.assignments)

    def test_default_acceptance_scenario(self):
        env = run_episode(build_environment(ScenarioConfig()), ConstrainedAllocationPlanner())
        self.assertEqual(len(env.records), 12)
        self.assertTrue(all(len(record.conditions) == 100 for record in env.records))
        assignments = [item for record in env.records for item in record.allocation.assignments]
        self.assertLessEqual(len(assignments), 30)
        self.assertGreaterEqual(env.observe().remaining_budget, 0)
        self.assertEqual(len(assignments), len({item.student_id for item in assignments}))

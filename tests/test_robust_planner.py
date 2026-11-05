"""Tiny exhaustive robust objectives and shared hard resource contracts."""

from dataclasses import replace
from itertools import product
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import numpy as np

from src.school.constraints import validate_allocation
from src.school.fairness_audit import coverage_shortfall, freeze_cohorts
from src.school.fairness_planner import FairnessPlanner, feasible_vector
from src.school.robust_fair_planner import FairRobustPlanner
from src.school.uncertainty_scenarios import BeliefScenario, scenario_candidate_values
from src.school.window_optimization import validate_schedule, window_model
from tests.test_uncertainty_scenarios import estimated_state


class RobustPlannerTests(unittest.TestCase):
    def test_exhaustive_shortfall_robust_cost_and_canonical_order(self):
        state = estimated_state(3, budget=10, horizon=2, monthly_admissions=1, monthly_appointments=5)
        planner = FairRobustPlanner(minimum_access=.5)
        scenarios = planner.belief_scenarios(state)
        candidates, rows, upper, _, costs, states = window_model(
            state, 2, planner.wait_matrix, planner.programme_matrix)
        benefits = scenario_candidate_values(state, candidates, scenarios,
                                            planner.wait_matrix, planner.programme_matrix)
        cohorts = freeze_cohorts(state)
        feasible = []
        for bits in product((0, 1), repeat=len(candidates)):
            if np.any(rows @ bits > upper):
                continue
            schedule = tuple(a for a, bit in zip(candidates, bits) if bit)
            key = (coverage_shortfall(cohorts, {a.student_id for a in schedule}, .5),
                   -round(float(np.min(benefits @ bits)), 10), int(costs @ bits), tuple(-b for b in bits))
            feasible.append((key, schedule))
        expected = min(feasible, key=lambda pair: pair[0])[1]
        actual = planner.plan(state)
        self.assertEqual(actual.tentative_assignments, expected)
        self.assertTrue(actual.lexicographic_complete, actual.status + actual.message)
        self.assertAlmostEqual(dict(actual.solver_settings)["robust_worst_case_benefit"],
                               -min(feasible, key=lambda pair: pair[0])[0][1])
        validate_schedule(state, states, actual.tentative_assignments)

    def test_aggregate_scenario_minimum_is_not_sum_of_student_minima(self):
        state = estimated_state(4, budget=10, horizon=1, monthly_admissions=2)
        ids = [s.student_id for s in state.students]
        wait = np.asarray([[0, 0, 0, 1]] * 4)
        programme = np.asarray([[0, 0, 0, 1], [.5, 0, 0, .5], [1, 0, 0, 0], [0, 0, 0, 1]])
        high, low, middle = (0, 0, 1, 0), (1, 0, 0, 0), (.6, 0, .4, 0)
        scenarios = (BeliefScenario("anticorrelated_a", tuple(zip(ids, (high, low, middle, middle))),
                                   source="unit_fixture_no_evaluator_input"),
                     BeliefScenario("anticorrelated_b", tuple(zip(ids, (low, high, middle, middle))),
                                   source="unit_fixture_no_evaluator_input"))
        planner = FairRobustPlanner(minimum_access=0, wait_matrix=wait, treatment_matrix=programme)
        with patch.object(planner, "belief_scenarios", return_value=scenarios):
            result = planner.plan(state)
        self.assertEqual({a.student_id for a in result.assignments}, set(ids[:2]))
        self.assertAlmostEqual(planner.last_robust_benefit, 1)
        self.assertGreater(planner.last_robust_benefit, .8)
        self.assertTrue(result.lexicographic_complete, result.status)

    def test_zero_radius_matches_point_planner_including_q_zero(self):
        for target in (0, .3, 1):
            state = estimated_state(4, budget=10, horizon=2, monthly_admissions=1)
            point = FairnessPlanner(minimum_access=target).plan(state)
            robust = FairRobustPlanner(minimum_access=target, uncertainty_radius=0).plan(state)
            self.assertEqual(robust.assignments, point.assignments)
            self.assertEqual(robust.tentative_assignments, point.tentative_assignments)
            self.assertTrue(robust.lexicographic_complete, robust.status)

    def test_q_zero_has_no_future_pressure_and_constraints_hold(self):
        state = estimated_state(4, budget=1.49, horizon=2, cost_per_appointment=.1,
                                monthly_admissions=4, monthly_appointments=5)
        planner = FairRobustPlanner(minimum_access=0)
        result = planner.plan(state)
        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.assignments, result.tentative_assignments)
        self.assertTrue(all(a.month == state.month for a in result.assignments))
        validate_allocation(state, result.assignments)

    def test_robust_cost_and_canonical_ties_reproduce(self):
        state = estimated_state(3, budget=10, horizon=1, beliefs=[(0, 1, 0, 0)] * 3)
        cheap = replace(state.mentors[0], mentor_id="z", cost_per_appointment=1)
        expensive = replace(cheap, mentor_id="a", cost_per_appointment=2)
        state = replace(state, mentors=(expensive, cheap))
        first = FairRobustPlanner(minimum_access=1/3, uncertainty_radius=0).plan(state)
        second = FairRobustPlanner(minimum_access=1/3, uncertainty_radius=0).plan(state)
        self.assertEqual(first.assignments, second.assignments)
        self.assertTrue(all(a.mentor_id == "z" for a in first.assignments))
        self.assertEqual([a.student_id for a in first.assignments],
                         [s.student_id for s in sorted(state.students, key=lambda s: s.student_id)[:2]])

    def test_continuous_eta_is_never_rounded_for_feasibility(self):
        rows = np.asarray([[-.345, 1]])
        lower, upper = np.asarray([-np.inf]), np.asarray([0])
        result = SimpleNamespace(status=0, x=np.asarray([1., .345]))
        self.assertTrue(feasible_vector(result, rows, lower, upper, integer_count=1))
        self.assertFalse(feasible_vector(result, rows, lower, upper))
        bad = SimpleNamespace(status=0, x=np.asarray([1., .5]))
        self.assertFalse(feasible_vector(bad, rows, lower, upper, integer_count=1))

    def test_strict_fairness_can_require_negative_continuous_benefit(self):
        state = estimated_state(1, budget=5, horizon=1, beliefs=[(1, 0, 0, 0)])
        wait = np.eye(4)
        harmful = np.asarray([[.7, 0, 0, .3], [0, .7, 0, .3], [0, 0, .7, .3], [0, 0, 0, 1]])
        result = FairRobustPlanner(minimum_access=1, allow_shortfall=False,
            uncertainty_radius=0, wait_matrix=wait, treatment_matrix=harmful).plan(state)
        self.assertEqual(len(result.assignments), 1)
        self.assertAlmostEqual(dict(result.solver_settings)["robust_worst_case_benefit"], -.3)
        self.assertTrue(result.lexicographic_complete, result.status)

    def test_infeasibility_and_solver_failures_are_visible(self):
        state = estimated_state(3, budget=5, horizon=1)
        strict = FairRobustPlanner(minimum_access=1, allow_shortfall=False).plan(state)
        self.assertEqual(strict.status, "fair_robust_infeasible")
        self.assertFalse(strict.assignments)
        with patch("src.school.robust_fair_planner.solve_milp", side_effect=RuntimeError("fixture")):
            result = FairRobustPlanner().plan(state)
            self.assertIn("fallback", result.status)
            self.assertFalse(result.assignments)
            with self.assertRaises(RuntimeError):
                FairRobustPlanner(failure_mode="raise").plan(state)


if __name__ == "__main__":
    unittest.main()

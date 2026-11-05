from dataclasses import replace
from unittest.mock import patch
import unittest

from src.school.allocation_result import AllocationResult
from src.school.baseline_policy import BaselinePolicy
from src.school.constraints import candidate_assignments, validate_allocation
from src.school.student_condition import StudentCondition
from src.school.fairness_audit import audit_access, coverage_shortfall, freeze_cohorts
from src.school.fairness_planner import FairnessPlanner
from src.school.optimization import solve_milp
from src.school.cmdp_scenarios import run_episode
from tests.cmdp_helpers import environment


class FairnessTests(unittest.TestCase):
    def test_small_continuous_solver_residual_preserves_valid_realized_allocation(self):
        env, _, _ = environment(4, budget=10, monthly_admissions=1)
        calls = 0

        def solve_with_residual(objective, rows, lower, upper, **kwargs):
            nonlocal calls
            calls += 1
            result = solve_milp(objective, rows, lower, upper, **kwargs)
            if calls == 2:
                # Reproduce sub-micro-unit slack residuals seen from HiGHS.
                index = kwargs["binary_count"]
                result.x[index] -= 2e-7
            return result

        state = env.observe()
        with patch("src.school.fairness_planner.solve_milp", side_effect=solve_with_residual):
            allocation = FairnessPlanner(minimum_access=0.5).plan(state)
        self.assertEqual(allocation.status, "fairness_optimal")
        validate_allocation(state, allocation.assignments)

    def test_frozen_denominator_unique_offers_and_withdrawal(self):
        env, _, _ = environment(3, budget=5)
        state = env.observe()
        frozen = freeze_cohorts(state)
        assignment = candidate_assignments(state)[0]
        env.step(AllocationResult((assignment,)))
        run_episode(env, BaselinePolicy("wait"))
        audits = audit_access(frozen, env.records, minimum_access=1)
        for attribute in ("sex_source", "disadvantage_proxy"):
            selected = [row for row in audits if row["attribute"] == attribute]
            self.assertEqual(sum(row["eligible_count"] for row in selected), 3)
            self.assertEqual(sum(row["unique_offers"] for row in selected), 1)
            self.assertEqual(sum(row["coverage_shortfall"] for row in selected), 2)

    def test_impossible_quota_never_overrides_resources(self):
        env, _, _ = environment(6, budget=5, monthly_admissions=1)
        policy = FairnessPlanner(minimum_access=1)
        state = env.observe()
        allocation = policy.plan(state)
        validate_allocation(state, allocation.assignments)
        self.assertEqual(len(allocation.assignments), 1)
        self.assertGreater(allocation.fairness_shortfall, 0)
        env.step(allocation)
        next_allocation = policy.plan(env.observe())
        self.assertFalse(next_allocation.assignments)
        self.assertGreater(next_allocation.fairness_shortfall, 0)

    def test_prior_offers_remain_covered_and_denominator_survives_withdrawal(self):
        env, _, _ = environment(2, budget=5, num_mentors=1)
        state = env.observe()
        # Same comparable need and same two audit groups for a hand-checkable target.
        first = replace(
            state.students[0],
            condition=StudentCondition.STABLE,
            support_type="tutoring",
            disadvantage_proxy=False,
            sex_source="F",
        )
        second = replace(
            state.students[1],
            condition=StudentCondition.STABLE,
            support_type="tutoring",
            disadvantage_proxy=False,
            sex_source="F",
        )
        state = replace(state, students=(first, second))
        policy = FairnessPlanner(minimum_access=1)
        allocation = policy.plan(state)
        self.assertEqual(len(allocation.assignments), 1)
        self.assertAlmostEqual(allocation.fairness_shortfall, 1.0)  # two groups * (2-1)/2
        recipient = allocation.assignments[0].student_id
        next_students = tuple(
            replace(
                student,
                programme_months=(1,) if student.student_id == recipient else (),
                enrolled=student.student_id == recipient,
            )
            for student in state.students
        )
        next_state = replace(state, month=2, students=next_students, remaining_budget=0)
        after = policy.plan(next_state)
        self.assertAlmostEqual(after.fairness_shortfall, 1.0)
        self.assertAlmostEqual(coverage_shortfall(freeze_cohorts(state), {recipient}, 1), 1.0)

    def test_lexicographic_shortfall_matches_exhaustive_feasible_actions(self):
        from src.school.exact_tiny_mdp import enumerate_allocations

        env, _, _ = environment(4, budget=10, monthly_admissions=1)
        state = env.observe()
        cohorts = freeze_cohorts(state)
        expected = min(
            coverage_shortfall(cohorts, {item.student_id for item in action}, 0.5)
            for action in enumerate_allocations(state)
        )
        allocation = FairnessPlanner(minimum_access=0.5).plan(state)
        self.assertAlmostEqual(allocation.fairness_shortfall, expected)
        validate_allocation(state, allocation.assignments)

    def test_window_resets_and_full_run_is_feasible(self):
        env, _, _ = environment(10, budget=20)
        run_episode(env, FairnessPlanner(minimum_access=0.5, window_months=4))
        self.assertEqual(len(env.records), 12)
        self.assertGreaterEqual(env.observe().remaining_budget, 0)

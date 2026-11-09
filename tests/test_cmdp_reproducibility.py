from dataclasses import FrozenInstanceError
import unittest

from src.school.allocation_result import AllocationResult
from src.school.baseline_policy import BASELINES, BaselinePolicy
from src.school.condition_estimate import ConditionEstimate
from src.school.constraints import candidate_assignments
from src.school.student_condition import StudentCondition
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.cmdp_scenarios import run_episode
from tests.cmdp_helpers import environment


class ReproducibilityTests(unittest.TestCase):
    def test_planner_trajectories_and_assignments_reproduce(self):
        first, _, _ = environment(20, budget=50)
        second, _, _ = environment(20, budget=50)
        run_episode(first, ConstrainedAllocationPlanner())
        run_episode(second, ConstrainedAllocationPlanner())
        self.assertEqual(
            [record.conditions for record in first.records],
            [record.conditions for record in second.records],
        )
        self.assertEqual(
            [record.allocation.assignments for record in first.records],
            [record.allocation.assignments for record in second.records],
        )

    def test_same_seed_and_policy_reproduce(self):
        first, _, _ = environment(20)
        second, _, _ = environment(20)
        run_episode(first, BaselinePolicy("random", seed=17))
        run_episode(second, BaselinePolicy("random", seed=17))
        self.assertEqual(first.records, second.records)

    def test_null_effect_all_baselines_have_identical_trajectories(self):
        expected = None
        for name in BASELINES:
            env, _, _ = environment(20, effect_strength=0)
            run_episode(env, BaselinePolicy(name))
            trajectory = [record.conditions for record in env.records]
            if expected is None:
                expected = trajectory
            self.assertEqual(trajectory, expected)

    def test_action_order_and_other_students_do_not_shift_draws(self):
        first, _, _ = environment(3)
        second, _, _ = environment(3)
        candidates = candidate_assignments(first.observe())
        chosen = (candidates[0], candidates[2])
        first.step(AllocationResult(chosen))
        second.step(AllocationResult(tuple(reversed(chosen))))
        self.assertEqual(first.records[0].conditions, second.records[0].conditions)
        first, _, _ = environment(3)
        second, _, _ = environment(3)
        first.step(AllocationResult(candidate_assignments(first.observe())[:1]))
        second.step(AllocationResult())
        self.assertEqual(first.records[0].conditions[1:], second.records[0].conditions[1:])

    def test_partial_observation_and_snapshots_are_isolated(self):
        env, _, _ = environment(2)
        snapshot = env.observe(fully_observed=False)
        self.assertTrue(all(student.condition is None for student in snapshot.students))

        self.assertFalse(hasattr(snapshot, "_conditions"))
        with self.assertRaises(FrozenInstanceError):
            snapshot.students[0].condition = StudentCondition.WITHDRAWN
        # Phase 3 defines missing estimates as the lowest priority, with ID
        # tie-breaking. No hidden label is required to produce an allocation.
        self.assertEqual([s.student_id for s in BaselinePolicy("severity").rank_students(snapshot)],
                         sorted(s.student_id for s in snapshot.students if s.eligible))
        student_id = snapshot.students[0].student_id
        estimate = ConditionEstimate(
            student_id, 1, StudentCondition.DISENGAGED, "explicit_test_estimator"
        )
        before = env.observe()
        observed = env.observe(fully_observed=False, estimates=(estimate,))
        self.assertEqual(observed.students[0].condition, StudentCondition.DISENGAGED)
        self.assertEqual(BaselinePolicy("severity").rank_students(observed)[0].student_id, student_id)
        self.assertEqual(before, env.observe())
        with self.assertRaises(ValueError):
            env.observe(
                fully_observed=False,
                estimates=(ConditionEstimate(student_id, 2, StudentCondition.STABLE, "future"),),
            )
        env.step(AllocationResult())
        self.assertEqual(snapshot.month, 1)
        self.assertTrue(all(student.condition is None for student in snapshot.students))

    def test_caller_list_cannot_mutate_historical_allocations(self):
        env, _, _ = environment(2)
        mutable_assignments = list(candidate_assignments(env.observe())[:1])
        allocation = AllocationResult(mutable_assignments)
        env.step(allocation)
        mutable_assignments.clear()
        self.assertEqual(len(env.records[0].allocation.assignments), 1)

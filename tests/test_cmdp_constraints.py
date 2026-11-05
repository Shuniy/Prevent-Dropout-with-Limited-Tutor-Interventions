from dataclasses import replace
import unittest

from src.school.allocation_result import AllocationResult
from src.school.baseline_policy import BASELINES, BaselinePolicy
from src.school.constraints import candidate_assignments, validate_allocation
from src.school.cmdp_scenarios import run_episode
from tests.cmdp_helpers import environment


class ConstraintTests(unittest.TestCase):
    def test_baselines_run_with_hard_limits_and_full_charges(self):
        for name in BASELINES:
            env, _, _ = environment(25, budget=15, monthly_admissions=1, monthly_appointments=5)
            run_episode(env, BaselinePolicy(name))
            assignments = [item for record in env.records for item in record.allocation.assignments]
            self.assertLessEqual(len(assignments), 3)
            self.assertEqual(len(assignments), len({item.student_id for item in assignments}))
            self.assertEqual(env.observe().remaining_budget, 15 - 5 * len(assignments))
            for record in env.records:
                self.assertGreaterEqual(record.remaining_budget, 0)

    def test_independent_validator_rejects_invalid_allocations(self):
        env, _, _ = environment(3, num_mentors=1, budget=10, monthly_admissions=1)
        state = env.observe()
        first, second = candidate_assignments(state)[:2]
        invalid = (
            (first, first),
            (first, second),
            (replace(first, cost_units=0),),
            (replace(first, sessions=4),),
            (replace(first, month=2),),
            (replace(first, mentor_id="missing"),),
            (replace(first, support_type="reentry_support"),),
        )
        for assignments in invalid:
            with self.assertRaises(ValueError):
                validate_allocation(state, assignments)
        with self.assertRaises(ValueError):
            validate_allocation(replace(state, remaining_budget=4), (first,))
        withdrawn = replace(state.students[0], enrolled=False)
        with self.assertRaises(ValueError):
            validate_allocation(replace(state, students=(withdrawn, *state.students[1:])), (first,))

    def test_repeat_rejected_and_capacity_resets(self):
        env, _, _ = environment(5, num_mentors=1, monthly_admissions=1, monthly_appointments=5)
        first = candidate_assignments(env.observe())[0]
        env.step(AllocationResult((first,)))
        self.assertTrue(candidate_assignments(env.observe()))
        with self.assertRaises(ValueError):
            env.step(AllocationResult((replace(first, month=2),)))
        self.assertEqual(len(env.records), 1)

    def test_no_appointments_no_skills_and_zero_budget(self):
        for options in ({"budget": 0}, {"monthly_appointments": 4}, {"num_mentors": 0}):
            env, _, _ = environment(**options)
            self.assertFalse(candidate_assignments(env.observe()))
        env, students, mentors = environment()
        for mentor in mentors:
            mentor.support_types = ["reentry_support"]
        from src.school.cmdp_environment import CMDPEnvironment

        self.assertFalse(
            candidate_assignments(CMDPEnvironment(students, mentors, env.config).observe())
        )

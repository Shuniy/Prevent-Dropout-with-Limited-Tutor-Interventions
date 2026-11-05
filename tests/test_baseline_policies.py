from dataclasses import replace
import unittest

import numpy as np

from src.school.baseline_policy import BASELINES, BaselinePolicy
from src.school.constraints import validate_allocation
from src.school.greedy_matching import assign_feasible
from src.school.student_condition import StudentCondition as Condition
from tests.cmdp_helpers import environment


class BaselinePolicyTests(unittest.TestCase):
    def setUp(self):
        self.env, self.students, self.mentors = environment(3, num_mentors=2, monthly_admissions=1)
        self.state = self.env.observe()

    def ids(self, name, state=None):
        return [student.student_id for student in BaselinePolicy(name).rank_students(state or self.state)]

    def test_wait_returns_no_assignments_and_does_not_spend_or_use_mentors(self):
        from src.school.cmdp_scenarios import run_episode
        run_episode(self.env, BaselinePolicy("wait"))
        self.assertTrue(all(not record.allocation.assignments for record in self.env.records))
        self.assertEqual(self.env.observe().remaining_budget, self.env.config.budget)

    def test_severity_is_disengaged_then_vulnerable_then_stable(self):
        students = tuple(replace(s, condition=c) for s, c in zip(self.state.students, (
            Condition.STABLE, Condition.DISENGAGED, Condition.VULNERABLE)))
        state = replace(self.state, students=students)
        self.assertEqual(self.ids("severity", state), [students[i].student_id for i in (1, 2, 0)])

    def test_need_priority_uses_actual_shared_source_need_scores(self):
        from src.school.cmdp_environment import CMDPEnvironment
        from src.school.needs import calculate_needs
        # Source need rules: verified financial need=0.75, failures/4, no internet=0.5.
        for student in self.students:
            student.anchor_grade1_0_20 = 18
            student.math_grade1_0_20 = 18
            student.past_failures_count = 0
            student.internet_at_home = True
            student.travel_time_category = 1
            student.study_time_category = 2
            student.family_relationship_rating = 5
            student.health_self_rating = 5
            student.initial_attendance_fraction_assumed = 0.95
            student.initial_engagement_assumed = 0.9
            student.financial_need_verified = False
        self.students[0].internet_at_home = False
        self.students[1].financial_need_verified = True
        self.students[2].past_failures_count = 4
        self.assertEqual([s.need_score for s in self.students], [0.5, 0.75, 1.0])
        self.assertEqual([s.need_score for s in self.students],
                         [calculate_needs(s)[0]["severity"] for s in self.students])
        state = CMDPEnvironment(self.students, self.mentors, self.env.config).observe()
        self.assertEqual(self.ids("need_priority", state), [self.students[i].student_id for i in (2, 1, 0)])

    def test_waiting_ranks_descending_without_severity_tie_break(self):
        students = tuple(replace(s, waiting_months=w, condition=c) for s, w, c in zip(
            self.state.students, (4, 1, 3), (Condition.STABLE, Condition.DISENGAGED, Condition.VULNERABLE)))
        self.assertEqual(self.ids("longest_waiting", replace(self.state, students=students)),
                         [students[i].student_id for i in (0, 2, 1)])
        tied = replace(self.state, students=tuple(replace(s, waiting_months=4) for s in reversed(students)))
        self.assertEqual(self.ids("longest_waiting", tied), sorted(s.student_id for s in students))

    def test_all_deterministic_ties_use_student_ids(self):
        state = replace(self.state, students=tuple(replace(s, condition=Condition.STABLE,
                         need_score=0.5, waiting_months=3) for s in reversed(self.state.students)))
        for name in ("severity", "need_priority", "longest_waiting"):
            self.assertEqual(self.ids(name, state), sorted(s.student_id for s in state.students))

    def test_random_order_reproduces_and_is_independent_of_mentor_edges_and_global_rng(self):
        policy = BaselinePolicy("random", seed=39)
        global_state = np.random.get_state()
        expected = policy.rank_students(self.state)
        self.assertEqual(expected, policy.rank_students(self.state))
        self.assertEqual(expected, policy.rank_students(replace(self.state, mentors=())))
        self.assertEqual(expected, policy.rank_students(replace(self.state, students=tuple(reversed(self.state.students)))))
        after = np.random.get_state()
        self.assertEqual(global_state[0], after[0])
        np.testing.assert_array_equal(global_state[1], after[1])
        self.assertEqual(global_state[2:], after[2:])
        self.assertEqual(set(expected), set(self.state.students))

    def test_random_order_depends_on_seed_and_month(self):
        env, _, _ = environment(30)
        state = env.observe()
        policy = BaselinePolicy("random", seed=39)
        expected = policy.rank_students(state)
        self.assertNotEqual(expected, BaselinePolicy("random", seed=40).rank_students(state))
        self.assertNotEqual(expected, policy.rank_students(replace(state, month=state.month + 1)))

    def test_all_policies_exclude_withdrawn_and_previously_supported_students(self):
        first, second, third = self.state.students
        state = replace(self.state, students=(
            replace(first, enrolled=False, condition=Condition.WITHDRAWN),
            replace(second, programme_months=(1,)), third))
        for name in BASELINES:
            order = BaselinePolicy(name).rank_students(state)
            self.assertEqual(tuple(s.student_id for s in order), () if name == "wait" else (third.student_id,))
            validate_allocation(state, BaselinePolicy(name).plan(state).assignments)

    def test_every_policy_uses_same_matcher_without_mutating_snapshot(self):
        before = self.env.observe()
        for name in BASELINES:
            policy = BaselinePolicy(name)
            self.assertEqual(policy.plan(before).assignments, assign_feasible(before, policy.rank_students(before)))
            self.assertEqual(before, self.env.observe())

    def test_edge_cases_are_feasible_for_all_policies(self):
        cases = {
            "zero_budget": replace(self.state, remaining_budget=0),
            "insufficient_budget": replace(self.state, remaining_budget=4.99),
            "no_mentors": replace(self.state, mentors=()),
            "withdrawn": replace(self.state, students=tuple(replace(s, enrolled=False,
                         condition=Condition.WITHDRAWN) for s in self.state.students)),
            "supported": replace(self.state, students=tuple(replace(s, programme_months=(1,))
                         for s in self.state.students)),
            "incompatible": replace(self.state, mentors=tuple(replace(m, compatible_student_ids=())
                         for m in self.state.mentors)),
            "wrong_skills": replace(self.state, mentors=tuple(replace(m, support_types=()) for m in self.state.mentors)),
            "no_admissions": replace(self.state, mentors=tuple(replace(m, admissions=0) for m in self.state.mentors)),
            "few_slots": replace(self.state, mentors=tuple(replace(m, appointments=4) for m in self.state.mentors)),
            "empty_cohort": replace(self.state, students=()),
        }
        for case, state in cases.items():
            for name in BASELINES:
                with self.subTest(case=case, policy=name):
                    result = BaselinePolicy(name).plan(state)
                    self.assertEqual(result.assignments, ())
                    validate_allocation(state, result.assignments)
        for count in (1, 2):
            state = replace(self.state, students=self.state.students[:count])
            for name in BASELINES:
                result = BaselinePolicy(name).plan(state)
                self.assertEqual(len(result.assignments), 0 if name == "wait" else count)
                validate_allocation(state, result.assignments)

    def test_greedy_matching_can_lose_cardinality_with_restricted_compatibility(self):
        first, second = self.state.students[:2]
        generalist, alternative = self.state.mentors
        state = replace(self.state, students=(first, second), mentors=(
            replace(generalist, compatible_student_ids=(first.student_id, second.student_id)),
            replace(alternative, compatible_student_ids=(first.student_id,))))
        greedy = assign_feasible(state, state.students)
        self.assertEqual(len(greedy), 1)
        # A different priority yields two; greedy never silently claims optimality.
        reverse = assign_feasible(state, tuple(reversed(state.students)))
        self.assertEqual(len(reverse), 2)
        validate_allocation(state, reverse)

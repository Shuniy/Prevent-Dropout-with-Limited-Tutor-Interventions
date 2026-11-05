"""Manually checkable coverage, rolling schedule and independent audit contracts."""

from dataclasses import replace
from copy import deepcopy
from decimal import Decimal
from itertools import product
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import numpy as np

from src.school.allocation_result import AllocationResult
from src.school.baseline_policy import BaselinePolicy
from src.school.cmdp_scenarios import run_episode, build_school
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.constraints import candidate_assignments, validate_allocation
from src.school.fairness_audit import (audit_access, audit_group, coverage_shortfall,
                                      freeze_cohorts, required_access, group_retention)
from src.school.fairness_planner import FairnessPlanner
from src.school.fairness_window import FairnessWindow
from src.school.scenario_config import ScenarioConfig
from src.school.student_condition import StudentCondition as S
from src.school.window_optimization import window_model, validate_schedule
from src.school.retention_value import estimate_all_student_benefits
from src.school.access_cohort import AccessCohort
from tests.cmdp_helpers import environment


def homogeneous(count, *, group_sizes=None, **options):
    env, _, _ = environment(count, num_mentors=1, **options)
    state = env.observe()
    boundary = count if group_sizes is None else group_sizes
    return replace(state, students=tuple(
        replace(s, condition=S.VULNERABLE, support_type="tutoring", sex_source="F",
                disadvantage_proxy=i >= boundary) for i, s in enumerate(state.students)))


class CohortAndAuditTests(unittest.TestCase):
    def test_integer_ceiling_and_normalized_counts(self):
        self.assertEqual(required_access(.14, 100), 14)
        self.assertEqual(required_access(.3, 3), 1)
        self.assertEqual(required_access(0, 0), 0)
        cohorts = freeze_cohorts(homogeneous(3))
        self.assertAlmostEqual(coverage_shortfall(cohorts, set(), .3), 1 / 3)

    def test_one_authorized_dimension_and_unknowns(self):
        state = homogeneous(3)
        students = list(state.students)
        students[0] = replace(students[0], disadvantage_proxy=None, sex_source=None)
        students[1] = replace(students[1], sex_source="inferred_name")
        state = replace(state, students=tuple(students))
        for attribute in ("sex_source", "disadvantage_proxy"):
            cohorts = freeze_cohorts(state, attribute)
            self.assertEqual({c.attribute for c in cohorts}, {attribute})
            self.assertEqual(sum(len(c.student_ids) for c in cohorts), 3)
            self.assertIn(students[0].student_id,
                          next(c.student_ids for c in cohorts if c.group == "unknown" and c.student_ids))
        self.assertEqual(audit_group(students[1], "sex_source"), "unknown")
        with self.assertRaises(ValueError):
            FairnessPlanner(grouping_attribute="income")
        with self.assertRaises(ValueError):
            freeze_cohorts(replace(state, observation_mode="estimated_or_unobserved"))

    def test_frozen_condition_and_denominator_survive_changes(self):
        state = homogeneous(3)
        window = FairnessWindow.initialize(state, window_months=4, target=.3,
                                           attribute="disadvantage_proxy")
        frozen = window.cohorts
        later = replace(state, month=2, students=tuple(
            replace(s, condition=S.WITHDRAWN, enrolled=False) if i == 0 else
            replace(s, condition=S.STABLE, programme_months=(1,))
            for i, s in enumerate(state.students)))
        window.update(later)
        self.assertEqual(window.cohorts, frozen)
        self.assertEqual(sum(len(c.student_ids) for c in frozen), 3)
        self.assertEqual(len(window.recipients), 2)
        window.update(later)
        self.assertEqual(len(window.recipients), 2)
        self.assertEqual(sum(len(c.student_ids) for c in freeze_cohorts(later)), 0)

    def test_compatibility_not_budget_defines_denominator(self):
        state = homogeneous(4, budget=0)
        self.assertEqual(sum(len(c.student_ids) for c in freeze_cohorts(state)), 4)
        mentor = replace(state.mentors[0], compatible_student_ids=(state.students[0].student_id,))
        restricted = replace(state, mentors=(mentor,), known_mentor_schedule=())
        window = FairnessWindow.initialize(restricted, window_months=4, target=.3,
                                           attribute="disadvantage_proxy")
        self.assertEqual(sum(len(c.student_ids) for c in window.cohorts), 1)
        self.assertEqual(len(window.excluded_no_compatible_ids), 3)

    def test_empty_unknown_small_groups_and_waiting_audited_independently(self):
        env, _, _ = environment(3, budget=5)
        state = env.observe()
        cohorts = freeze_cohorts(state)
        assignment = candidate_assignments(state)[0]
        # Duplicate recorded assignment data is deduplicated by student for access.
        env.step(AllocationResult((assignment,)))
        run_episode(env, BaselinePolicy("wait"))
        rows = audit_access(cohorts, env.records, minimum_access=.3, end_month=4)
        self.assertTrue(any(r["access_rate"] is None for r in rows))
        self.assertEqual(sum(r["unique_admissions"] for r in rows), 1)
        self.assertTrue(all(r["max_waiting_months"] is None for r in rows if not r["eligible_count"]))
        self.assertTrue(all(r["small_group"] for r in rows if r["eligible_count"]))
        self.assertTrue(all(r["coverage_shortfall"] == max(0, r["required_students"] - r["unique_admissions"])
                            for r in rows))
        retention = group_retention(state, env.records, "sex_source")
        self.assertEqual(sum(r["initial_enrolled_count"] for r in retention), len(state.students))

    def test_missing_proxy_inputs_remain_unknown_and_income_is_not_used(self):
        _, students, _ = environment(1)
        student = students[0]
        self.assertIsNone(replace(student, internet_at_home=None).disadvantage_proxy_group)
        self.assertEqual(replace(student, financial_need_verified=None).disadvantage_proxy_group,
                         student.disadvantage_proxy_group)

    def test_overlap_counts_one_admission_and_no_duplicate_resources(self):
        state = homogeneous(1, budget=5, horizon=1)
        sid = state.students[0].student_id
        cohorts = (AccessCohort("sex_source", "F", "vulnerable", "all", (sid,)),
                   AccessCohort("disadvantage_proxy", "False", "vulnerable", "all", (sid,)))
        self.assertEqual(coverage_shortfall(cohorts, {sid, sid}, 1), 0)
        result = FairnessPlanner(minimum_access=1).plan(state)
        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.total_programme_cost, 5)


class WindowMILPTests(unittest.TestCase):
    def test_demographics_never_change_benefits_and_fair_episode_preserves_sources(self):
        state = homogeneous(4)
        planner = FairnessPlanner()
        changed = replace(state, students=tuple(replace(s, disadvantage_proxy=None, sex_source=None)
                                                 for s in state.students))
        self.assertEqual(estimate_all_student_benefits(state, planner.wait_matrix, planner.programme_matrix),
                         estimate_all_student_benefits(changed, planner.wait_matrix, planner.programme_matrix))
        config = ScenarioConfig(num_students=8)
        school = build_school(config)
        before = deepcopy((school.students, school.mentors))
        school.run_cmdp(FairnessPlanner(), config=config)
        self.assertEqual((school.students, school.mentors), before)

    def test_future_values_are_wait_projection_and_current_estimator_unchanged(self):
        state = homogeneous(2, horizon=2)
        planner = FairnessPlanner()
        candidates, _, _, values, _, _ = window_model(state, 2, planner.wait_matrix, planner.programme_matrix)
        immediate = estimate_all_student_benefits(state, planner.wait_matrix, planner.programme_matrix)
        from src.school.retention_value import estimate_incremental_benefit
        from src.school.student_condition import STATES
        future = sum(planner.wait_matrix[STATES.index(S.VULNERABLE), j]
                     * estimate_incremental_benefit(condition, 1, planner.wait_matrix, planner.programme_matrix)
                     for j, condition in enumerate(STATES))
        for candidate, value in zip(candidates, values):
            self.assertAlmostEqual(value, immediate[candidate.student_id] if candidate.month == 1 else future)

    def test_fractional_money_and_appointment_limits_hold_for_entire_schedule(self):
        state = homogeneous(4, budget=1.49, cost_per_appointment=.1,
                            monthly_admissions=4, monthly_appointments=5, horizon=2)
        planner = FairnessPlanner(minimum_access=1)
        result = planner.plan(state)
        self.assertEqual(len(result.tentative_assignments), 2)
        self.assertEqual(sum(a.cost_units for a in result.tentative_assignments), 1)
        self.assertTrue(all(sum(a.month == month for a in result.tentative_assignments) <= 1
                            for month in (1, 2)))
        validate_allocation(state, result.assignments)

    def test_tentative_budget_recomputes_exact_prices_not_rounded_assignment_floats(self):
        for offset in range(100):
            price = float(Decimal("1.2345678901234500") + Decimal(offset) / 10**16)
            exact = 5 * Decimal(str(price))
            rounded = Decimal(str(float(exact)))
            budget = float(2 * rounded)
            if 2 * rounded <= Decimal(str(budget)) < 2 * exact:
                break
        else:
            self.fail("fixture must exhibit downward cost rounding")
        state = homogeneous(2, budget=budget, cost_per_appointment=price,
                            monthly_admissions=1, horizon=2)
        result = FairnessPlanner(minimum_access=1).plan(state)
        # Two exact programme costs exceed budget, even if their display floats fit.
        self.assertEqual(len(result.tentative_assignments), 1)

    def test_twenty_student_six_programme_example_and_infeasibility(self):
        state = homogeneous(20, group_sizes=10, budget=30, monthly_admissions=2,
                            monthly_appointments=10)
        result = FairnessPlanner(minimum_access=.3, allow_shortfall=False).plan(state)
        self.assertEqual(result.status, "fairness_optimal")
        self.assertTrue(result.projected_fairness_feasible)
        schedule = result.tentative_assignments
        for group in (False, True):
            ids = {s.student_id for s in state.students if s.disadvantage_proxy == group}
            self.assertEqual(sum(a.student_id in ids for a in schedule), 3)
        self.assertEqual(len(schedule), 6)
        self.assertLessEqual(len(result.assignments), 2)
        self.assertEqual(result.assignments, tuple(a for a in schedule if a.month == 1))
        restricted = replace(state, remaining_budget=20)
        strict = FairnessPlanner(minimum_access=.3, allow_shortfall=False).plan(restricted)
        self.assertEqual(strict.status, "fairness_infeasible")
        self.assertFalse(strict.assignments)
        soft = FairnessPlanner(minimum_access=.3).plan(restricted)
        self.assertAlmostEqual(soft.projected_fairness_shortfall, .2)
        self.assertEqual(len(soft.tentative_assignments), 4)
        validate_allocation(restricted, soft.assignments)

    def test_normalization_gives_small_cells_equal_rate_weight(self):
        state = homogeneous(5, group_sizes=1, budget=5, effect_strength=0)
        result = FairnessPlanner(minimum_access=1, treatment_matrix=np.eye(4),
                                 wait_matrix=np.eye(4)).plan(state)
        self.assertEqual(result.assignments[0].student_id, state.students[0].student_id)
        self.assertAlmostEqual(result.projected_fairness_shortfall, 1)

    def test_deterministic_schedule_matches_exhaustive_lexicographic_search(self):
        state = homogeneous(3, group_sizes=1, budget=10, horizon=2,
                            monthly_admissions=1, monthly_appointments=5)
        planner = FairnessPlanner(minimum_access=.5)
        candidates, rows, upper, values, costs, states = window_model(
            state, 2, planner.wait_matrix, planner.programme_matrix)
        cohorts = freeze_cohorts(state)
        feasible = []
        for bits in product((0, 1), repeat=len(candidates)):
            if np.any(rows @ bits > upper):
                continue
            selected = tuple(a for a, bit in zip(candidates, bits) if bit)
            ids = {a.student_id for a in selected}
            key = (coverage_shortfall(cohorts, ids, .5), -round(float(values @ bits), 10),
                   int(costs @ bits), tuple(-b for b in bits))
            feasible.append((key, selected))
        expected = min(feasible, key=lambda item: item[0])[1]
        actual = planner.plan(state)
        self.assertEqual(actual.tentative_assignments, expected)
        validate_schedule(state, states, expected)
        self.assertTrue(actual.lexicographic_complete)

    def test_future_capacity_is_announced_and_tentative(self):
        state = homogeneous(2, budget=10, horizon=2, monthly_admissions=1)
        no_current = replace(state.mentors[0], admissions=0, appointments=0)
        state = replace(state, mentors=(no_current,))
        planner = FairnessPlanner(minimum_access=1, allow_shortfall=False)
        before = state.remaining_budget
        result = planner.plan(state)
        self.assertFalse(result.assignments)
        self.assertEqual(len(result.tentative_assignments), 0)
        self.assertEqual(result.status, "fairness_infeasible")  # only one future slot for two students
        # With one cohort member the announced next-month slot is sufficient.
        state = replace(state, students=state.students[:1])
        planner = FairnessPlanner(minimum_access=1, allow_shortfall=False)
        result = planner.plan(state)
        self.assertTrue(result.projected_fairness_feasible)
        self.assertEqual(result.tentative_assignments[0].month, 2)
        self.assertEqual(state.remaining_budget, before)
        self.assertFalse(planner.window.recipients)
        later = replace(state, month=2, months_remaining=1,
                        mentors=state.known_mentor_schedule[1][1],
                        students=(replace(state.students[0], enrolled=False, condition=S.WITHDRAWN),))
        actual = planner.plan(later)
        self.assertEqual(actual.status, "fairness_infeasible")
        self.assertEqual(actual.realized_fairness_shortfall, 1)
        self.assertEqual(sum(len(c.student_ids) for c in planner.window.cohorts), 1)

    def test_zero_target_exactly_delegates_resource_only_for_all_months(self):
        config = ScenarioConfig(num_students=20)
        school = build_school(config)
        fair = school.run_cmdp(FairnessPlanner(minimum_access=0), config=config)
        resource = school.run_cmdp(ConstrainedAllocationPlanner(), config=config)
        self.assertEqual([r.allocation.assignments for r in fair.environment.records],
                         [r.allocation.assignments for r in resource.environment.records])
        self.assertEqual([r.conditions for r in fair.environment.records],
                         [r.conditions for r in resource.environment.records])

    def test_zero_effect_access_spends_but_matched_outcomes_equal_wait(self):
        config = ScenarioConfig(num_students=20, effect_strength=0)
        school = build_school(config)
        fair = school.run_cmdp(FairnessPlanner(minimum_access=.3,
                              treatment_matrix=ConstrainedAllocationPlanner().wait_matrix), config=config)
        waiting = school.run_cmdp(BaselinePolicy("wait"), config=config)
        self.assertGreater(sum(len(r.allocation.assignments) for r in fair.environment.records), 0)
        self.assertTrue(all(r.allocation.objective == 0 for r in fair.environment.records))
        self.assertEqual([r.conditions for r in fair.environment.records],
                         [r.conditions for r in waiting.environment.records])

    def test_completed_ledgers_match_independent_audit_and_reset(self):
        config = ScenarioConfig(num_students=20, budget=20)
        simulation = build_school(config).run_cmdp(FairnessPlanner(minimum_access=.3), config=config)
        self.assertEqual(len(simulation.fairness_windows), 3)
        for window in simulation.fairness_windows:
            audits = audit_access(window.cohorts, simulation.environment.records,
                                  start_month=window.start, end_month=window.end, minimum_access=.3)
            self.assertEqual(sum(r["unique_admissions"] for r in audits),
                             sum(len(set(c.student_ids) & window.recipients) for c in window.cohorts))
        ids = [a.student_id for r in simulation.environment.records for a in r.allocation.assignments]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(r.remaining_budget >= 0 for r in simulation.environment.records))

    def test_ties_choose_cheapest_then_canonical_and_reproduce(self):
        state = homogeneous(3, budget=10, horizon=1)
        cheap = replace(state.mentors[0], mentor_id="z", cost_per_appointment=1)
        expensive = replace(cheap, mentor_id="a", cost_per_appointment=2)
        state = replace(state, mentors=(expensive, cheap))
        first = FairnessPlanner(minimum_access=.3).plan(state)
        second = FairnessPlanner(minimum_access=.3).plan(state)
        self.assertEqual(first.assignments, second.assignments)
        self.assertTrue(all(a.mentor_id == "z" for a in first.assignments))

    def test_solver_failure_and_timeout_are_visible(self):
        state = homogeneous(3)
        with patch("src.school.fairness_planner.solve_milp", side_effect=RuntimeError("test")):
            result = FairnessPlanner().plan(state)
            self.assertIn("fallback", result.status)
            self.assertFalse(result.assignments)
            with self.assertRaises(RuntimeError):
                FairnessPlanner(failure_mode="raise").plan(state)
        with patch("src.school.fairness_planner.solve_milp", return_value=SimpleNamespace(
                status=1, x=None, message="limit")):
            result = FairnessPlanner().plan(state)
            self.assertIn("fallback", result.status)
            self.assertFalse(result.lexicographic_complete)

    def test_configuration_loads_and_rejects_ambiguous_modes(self):
        config = ScenarioConfig.load("configs/cmdp_fairness_v1.toml")
        self.assertEqual(config.fairness_min_access, .3)
        self.assertEqual(config.fairness_grouping_attribute, "disadvantage_proxy")
        for kwargs in ({"fairness_grouping_attribute": "both"}, {"fairness_metric": "parity"},
                       {"fairness_allow_shortfall": 1}, {"fairness_small_group_threshold": 0}):
            with self.assertRaises(ValueError):
                ScenarioConfig(**kwargs)


if __name__ == "__main__":
    unittest.main()

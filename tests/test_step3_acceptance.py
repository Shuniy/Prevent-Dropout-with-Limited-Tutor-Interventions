"""Regression and acceptance checks for Step 3's mathematical contracts."""

from dataclasses import replace
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from src.school.allocation_result import AllocationResult
from src.school.cmdp_experiments import run_experiments, run_policy
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.constraints import candidate_assignments
from src.school.exact_tiny_mdp import ExactTinyMDP, enumerate_allocations
from src.school.optimization import solve_milp
from src.school.planner_exports import benefit_rows, tiny_comparisons
from src.school.retention_value import expected_terminal_retention, estimate_incremental_benefit
from src.school.scenario_config import ScenarioConfig
from src.school.student_condition import STATES
from src.school.transition_model import P_WAIT, P_PROGRAMME, programme_matrix
from tests.cmdp_helpers import environment


class Step3AcceptanceTests(unittest.TestCase):
    def test_cost_minimum_and_canonical_assignment_match_exhaustive_search(self):
        env, _, _ = environment(3, horizon=1, budget=20, monthly_admissions=1)
        state = env.observe()
        state = replace(state, mentors=(replace(state.mentors[0], cost_per_appointment=2),
                                        state.mentors[1]))
        planner = ConstrainedAllocationPlanner()
        result = planner.plan(state)
        benefit = {s.student_id: estimate_incremental_benefit(s.condition, 1, P_WAIT, P_PROGRAMME)
                   for s in state.students}
        actions = enumerate_allocations(state)
        best = max(sum(benefit[a.student_id] for a in action) for action in actions)
        cheapest = min(sum(a.cost_units for a in action) for action in actions
                       if abs(sum(benefit[a.student_id] for a in action) - best) < 1e-10)
        self.assertAlmostEqual(result.objective, best)
        self.assertEqual(result.total_programme_cost, cheapest)
        self.assertTrue(result.lexicographic_complete)
        reordered = planner.plan(replace(state, students=tuple(reversed(state.students)),
                                         mentors=tuple(reversed(state.mentors))))
        self.assertEqual(result.assignments, reordered.assignments)

    def test_cheaper_mentor_wins_even_if_more_expensive_mentor_is_first(self):
        env, _, _ = environment(1, horizon=1, budget=20)
        state = env.observe()
        state = replace(state, mentors=(replace(state.mentors[0], cost_per_appointment=2),
                                        state.mentors[1]))
        result = ConstrainedAllocationPlanner().plan(state)
        self.assertEqual(result.total_programme_cost, 5)
        self.assertEqual(result.assignments[0].mentor_id, state.mentors[1].mentor_id)

    def test_budget_overspend_rejected_atomically_and_solver_uses_exact_units(self):
        env, _, _ = environment(2, horizon=1, budget=9.99999995)
        before = env.observe()
        candidates = candidate_assignments(before)
        action = tuple(next(a for a in candidates if a.student_id == s.student_id)
                       for s in before.students)
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            env.step(AllocationResult(action))
        self.assertEqual(env.observe(), before)
        self.assertFalse(env.records)
        planned = ConstrainedAllocationPlanner().plan(before)
        self.assertEqual(planned.selected_student_count, 1)
        env.step(planned)
        self.assertEqual(env.observe().remaining_budget_exact, "4.99999995")

    def test_fractional_prices_reconcile_without_roundoff_clamping(self):
        env, _, _ = environment(3, horizon=2, budget=1.5, cost_per_appointment=0.1,
                                monthly_admissions=1)
        planner = ConstrainedAllocationPlanner()
        while not env.done:
            env.step(planner.plan(env.observe()))
        self.assertEqual(env.observe().remaining_budget_exact, "0.0")
        self.assertEqual(sum(r.allocation.total_programme_cost for r in env.records), 1.5)
        env, _, _ = environment(1, horizon=1, budget=0.35, cost_per_appointment=0.07)
        allocation = ConstrainedAllocationPlanner().plan(env.observe())
        self.assertEqual(allocation.selected_student_count, 1)
        env.step(allocation)
        self.assertEqual(env.observe().remaining_budget, 0)

    def test_all_horizons_and_effect_strengths_use_actual_transition_matrices(self):
        for condition_index, condition in enumerate(STATES):
            for horizon in range(13):
                expected = (np.linalg.matrix_power(P_WAIT, horizon) @ [1, 1, 1, 0])[condition_index]
                self.assertAlmostEqual(expected_terminal_retention(condition, horizon, P_WAIT),
                                       expected)
                if horizon:
                    continuation = np.linalg.matrix_power(P_WAIT, horizon - 1) @ [1, 1, 1, 0]
                    for alpha in (0, 0.25, 0.5, 1):
                        expected = ((programme_matrix(alpha) - P_WAIT) @ continuation)[condition_index]
                        self.assertAlmostEqual(estimate_incremental_benefit(
                            condition, horizon, P_WAIT, programme_matrix(alpha)), expected)
        for invalid in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                expected_terminal_retention(STATES[0], invalid, P_WAIT)
        with self.assertRaises(ValueError):
            expected_terminal_retention(STATES[0], 1, np.eye(3))
        # Hand-verifiable survival model: vulnerable survives with 0.8 per month.
        simple = np.eye(4)
        simple[1] = [0, 0.8, 0, 0.2]
        self.assertAlmostEqual(expected_terminal_retention(STATES[1], 3, simple), 0.512)

    def test_nonpositive_benefit_is_excluded_even_with_free_programmes(self):
        env, _, _ = environment(3, horizon=1, cost_per_appointment=0)
        state = env.observe()
        state = replace(state, students=tuple(replace(s, condition=c)
                                              for s, c in zip(state.students, STATES[:3])))
        treatment = P_WAIT.copy()
        treatment[0, 0] += 0.005
        treatment[0, 3] -= 0.005
        treatment[1, 1] -= 0.1
        treatment[1, 3] += 0.1
        result = ConstrainedAllocationPlanner(treatment_matrix=treatment).plan(state)
        self.assertEqual([a.student_id for a in result.assignments], [state.students[0].student_id])
        self.assertLess(estimate_incremental_benefit(STATES[1], 1, P_WAIT, treatment), 0)

    def test_diagnostics_and_current_conditions_are_used(self):
        env, _, _ = environment(2, horizon=1, budget=5, num_mentors=1)
        state = env.observe()
        planner = ConstrainedAllocationPlanner()
        for conditions, selected in (((STATES[0], STATES[2]), 1),
                                     ((STATES[2], STATES[0]), 0)):
            current = replace(state, students=tuple(replace(s, condition=c)
                                                    for s, c in zip(state.students, conditions)))
            result = planner.plan(current)
            self.assertEqual(result.assignments[0].student_id, state.students[selected].student_id)
            self.assertEqual((result.current_month, result.months_remaining), (1, 1))
            self.assertEqual((result.candidate_pair_count, result.eligible_student_count), (2, 2))
            self.assertEqual(result.available_mentor_count, 1)
            self.assertTrue(result.benefit_estimator_version and result.solver_version)

    def test_solver_errors_and_refinement_limits_are_visible_and_do_not_mutate(self):
        env, _, _ = environment(2, horizon=1)
        state = env.observe()
        for status, label in ((4, "numerical_failure"), (9, "solver_error")):
            with patch("src.school.constrained_planner.solve_milp", return_value=
                       SimpleNamespace(status=status, x=None, message="injected failure")):
                result = ConstrainedAllocationPlanner().plan(state)
            self.assertEqual(result.status, label + "_wait_fallback")
        with patch("src.school.constrained_planner.solve_milp", side_effect=RuntimeError("failure")):
            with self.assertRaisesRegex(RuntimeError, "unexpected_error"):
                ConstrainedAllocationPlanner(failure_mode="raise").plan(state)
        calls = 0

        def limited(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return solve_milp(*args, **kwargs)
            return SimpleNamespace(status=1, x=None, message="time limit")

        with patch("src.school.constrained_planner.solve_milp", side_effect=limited):
            result = ConstrainedAllocationPlanner().plan(state)
        self.assertEqual(result.status, "cost_refinement_incomplete")
        self.assertFalse(result.lexicographic_complete)
        self.assertTrue(result.assignments)
        self.assertEqual(env.observe(), state)

    def test_null_effect_and_zero_budget_match_wait_trajectories(self):
        for options in ({"effect_strength": 0}, {"budget": 0}):
            supported, _, _ = environment(8, horizon=4, **options)
            waiting, _, _ = environment(8, horizon=4, **options)
            planner = ConstrainedAllocationPlanner(treatment_matrix=
                                                   programme_matrix(supported.config.effect_strength))
            while not waiting.done:
                supported.step(planner.plan(supported.observe()))
                waiting.step(AllocationResult())
            self.assertEqual([r.conditions for r in supported.records],
                             [r.conditions for r in waiting.records])
            self.assertTrue(all(not r.allocation.assignments for r in supported.records))

    def test_exact_comparisons_cover_multiple_scenarios_and_preserved_budget(self):
        rows = tiny_comparisons()
        self.assertGreaterEqual(len(rows), 5)
        for row in rows:
            self.assertGreaterEqual(row["objective_gap"], -1e-9)
            self.assertLessEqual(row["exact_expected_spending"], row["budget"] + 1e-9)
            self.assertLessEqual(row["heuristic_expected_spending"], row["budget"] + 1e-9)
        reserve = next(row for row in rows if row["scenario"] == "reserve_budget")
        self.assertEqual(reserve["exact_first_spending"], 0)
        self.assertEqual(reserve["heuristic_first_spending"], 5)
        self.assertGreater(reserve["objective_gap"], 0)
        final = next(row for row in rows if row["scenario"] == "last_month")
        self.assertAlmostEqual(final["exact_expected_terminal_enrollment"], 0.995 + 0.98 + 0.92)

    def test_two_month_bellman_value_agrees_with_manual_calculation(self):
        env, _, _ = environment(1, horizon=2, budget=5, num_mentors=1)
        state = env.observe()
        state = replace(state, students=(replace(state.students[0], condition=STATES[0]),))
        # Programme now: .94*.995 + .05*.97 + .008*.85 = .9906.
        # WAIT now, programme next: .88*.998 + .10*.98 + .015*.92 = .99004.
        result = ExactTinyMDP(state).compare()
        self.assertAlmostEqual(result["exact_expected_terminal_enrollment"], 0.9906)
        self.assertEqual(len(result["exact_first_student_ids"]), 1)

    def test_empty_eligibility_compatibility_and_capacity_are_valid_wait_decisions(self):
        env, _, _ = environment(2, horizon=1)
        state = env.observe()
        for altered in (
            replace(state, students=()),
            replace(state, mentors=()),
            replace(state, students=tuple(replace(s, programme_months=(0,)) for s in state.students)),
            replace(state, students=tuple(replace(s, enrolled=False, condition=STATES[3])
                                         for s in state.students)),
            replace(state, mentors=tuple(replace(m, appointments=4) for m in state.mentors)),
            replace(state, mentors=tuple(replace(m, admissions=0) for m in state.mentors)),
            replace(state, mentors=tuple(replace(m, support_types=()) for m in state.mentors)),
            replace(state, remaining_budget=1),
        ):
            result = ConstrainedAllocationPlanner().plan(altered)
            self.assertEqual(result.status, "no_candidates")
            self.assertFalse(result.assignments)

    def test_policy_execution_order_preserves_all_nontiming_results(self):
        def without_timing(value):
            if isinstance(value, dict):
                return {key: without_timing(item) for key, item in value.items()
                        if key not in ("runtime_seconds", "solver_runtime_seconds",
                                       "max_monthly_solver_runtime_seconds")}
            if isinstance(value, (list, tuple)):
                return [without_timing(item) for item in value]
            return value

        for seed in (42, 43):
            config = ScenarioConfig(num_students=8, horizon=3, budget=10, seed=seed)
            forward = {name: without_timing(run_policy(config, name))
                       for name in ("wait", "terminal_value")}
            reverse = {name: without_timing(run_policy(config, name))
                       for name in ("terminal_value", "wait")}
            self.assertEqual(forward, reverse)

    def test_experiment_exports_include_every_episode_month_and_requested_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "step3"
            run_experiments(ScenarioConfig(num_students=3, horizon=2), output=output,
                            policies=("wait", "terminal_value"), development_seed_count=1,
                            evaluation_seed_count=1)
            for filename in ("benefit_by_condition.csv", "tiny_exact_comparison.csv",
                             "solver_diagnostics.csv", "experiment_config.json",
                             "figures/terminal_retention.png", "figures/retention_trajectories.png",
                             "figures/budget_sensitivity.png", "figures/benefit_by_horizon.png",
                             "figures/solver_runtime.png", "requirements-lock.txt"):
                self.assertTrue((output / filename).is_file(), filename)
            with (output / "solver_diagnostics.csv").open() as source:
                diagnostics = list(csv.DictReader(source))
            self.assertEqual(len(diagnostics), 4)
            self.assertEqual({row["current_month"] for row in diagnostics}, {"1", "2"})
            self.assertEqual(json.loads((output / "COMPLETED.json").read_text())["episodes"], 4)
            self.assertTrue(all(row["incremental_benefit"] == 0 for row in benefit_rows((0,))))

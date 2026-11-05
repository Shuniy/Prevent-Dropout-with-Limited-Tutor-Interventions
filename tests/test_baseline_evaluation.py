import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from src.school.allocation_result import AllocationResult
from src.school.baseline_policy import BASELINES
from src.school.baseline_validation import validate_episode, validate_experiment_grid
from src.school.cmdp_experiments import run_experiments, run_policy
from src.school.cmdp_reports import summarize
from src.school.cmdp_scenarios import build_school
from src.school.scenario_config import ScenarioConfig


class BaselineEvaluationTests(unittest.TestCase):
    def rows(self):
        rows = []
        for seed in (42, 43):
            for policy in ("wait", "random"):
                metrics, _ = run_policy(ScenarioConfig(num_students=3, horizon=2, seed=seed), policy)
                rows.append(dict(scenario="effect_1_budget_150", partition="development",
                                 seed=seed, policy=policy, **metrics))
        return rows

    def manifest(self):
        return dict(variations=[(1, 150)], policies=["wait", "random"],
                    development_seeds=[42, 43], partitions=["development"])

    def test_incomplete_or_duplicate_experiments_fail_against_manifest(self):
        rows = self.rows()
        for subset in (rows[:-1], rows[:2], [r for r in rows if r["policy"] == "wait"], rows + rows[:1]):
            with self.subTest(size=len(subset)):
                with self.assertRaisesRegex(ValueError, "incomplete experiment"):
                    summarize(subset, self.manifest())
        validate_experiment_grid(rows, self.manifest())

    def test_summary_reports_sd_and_paired_percentage_points_at_episode_level(self):
        rows = self.rows()
        for row in rows:
            row["terminal_enrolled"] = (1 if row["seed"] == 42 else 2) + (row["policy"] == "random")
            row["retention_rate"] = row["terminal_enrolled"] / 4
        result = next(row for row in summarize(rows, self.manifest()) if row["policy"] == "random")
        self.assertAlmostEqual(result["sd_terminal_enrolled"], np.std([2, 3], ddof=1))
        self.assertEqual(result["paired_differences"]["wait"]["mean"], 1)
        self.assertEqual(result["paired_percentage_point_differences"]["wait"]["mean"], 25)
        self.assertEqual(result["paired_percentage_point_differences"]["wait"]["ci95_low"], 25)

    def test_zero_budget_zero_effect_and_policy_iteration_order(self):
        for overrides in ({"budget": 0}, {"effect_strength": 0}):
            config = ScenarioConfig(num_students=8, horizon=4, **overrides)
            school = build_school(config)
            forward = {name: run_policy(config, name, school=school) for name in BASELINES}
            reverse = {name: run_policy(config, name, school=school) for name in reversed(BASELINES)}
            self.assertEqual(forward, reverse)
            expected = [month["conditions"] for month in forward["wait"][1]]
            for name, (metrics, trajectory) in forward.items():
                self.assertEqual([month["conditions"] for month in trajectory], expected)
                validate_episode(metrics, trajectory, config)
                if config.budget == 0 or name == "wait":
                    self.assertEqual(metrics["spending"], 0)
                    self.assertEqual(metrics["mentor_admission_utilization"], 0)

    def test_resource_audit_detects_corrupt_totals_and_monthly_budgets(self):
        config = ScenarioConfig(num_students=3, horizon=2)
        metrics, trajectory = run_policy(config, "random")
        with self.assertRaisesRegex(ValueError, "totals"):
            validate_episode({**metrics, "appointments": 0}, trajectory, config)
        with self.assertRaisesRegex(ValueError, "budget ledger"):
            validate_episode(metrics, [{**trajectory[0], "remaining_budget": -1}, *trajectory[1:]], config)

    def test_waiting_and_unit_cost_metrics_use_documented_denominators(self):
        config = ScenarioConfig(num_students=8, horizon=3, monthly_admissions=1, num_mentors=1, budget=10)
        metrics, trajectory = run_policy(config, "longest_waiting")
        self.assertEqual(metrics["cost_per_supported_student"], 5)
        self.assertEqual(metrics["mean_recipient_waiting_months"], 0.5)
        self.assertEqual(metrics["remaining_budget"], 0)
        self.assertEqual(metrics["programmes"], metrics["unique_students_supported"])
        self.assertEqual(metrics["appointments"], 5 * metrics["programmes"])
        self.assertEqual(metrics["spending"], sum(row["spending"] for row in metrics["monthly_summaries"]))
        self.assertEqual(metrics["enrolled_student_months"], sum(row["enrolled"] for row in metrics["monthly_summaries"][1:]))
        for row in metrics["monthly_summaries"]:
            distribution = row["eligible_waiting_distribution"]
            self.assertEqual(sum(distribution.values()), row["eligible_students"])
            self.assertEqual(max(distribution, default=0), row["max_eligible_waiting_months"])
        wait, _ = run_policy(config, "wait")
        self.assertIsNone(wait["cost_per_supported_student"])
        self.assertIsNone(wait["mean_recipient_waiting_months"])

    def test_invalid_policy_assignment_is_recorded_and_not_repaired(self):
        class InvalidPolicy:
            def plan(self, state):
                from src.school.constraints import candidate_assignments
                first = candidate_assignments(state)[0]
                return AllocationResult((first, first))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            with patch("src.school.cmdp_experiments.make_policy", return_value=InvalidPolicy()):
                with self.assertRaises(ValueError):
                    run_experiments(ScenarioConfig(num_students=2, horizon=1), output=output,
                                    policies=("random",), development_seed_count=1, evaluation_seed_count=1)
            failure = json.loads((output / "failure.json").read_text())
            self.assertEqual((failure["policy"], failure["partition"], failure["completed_episodes"]),
                             ("random", "development", 0))
            self.assertFalse((output / "COMPLETED.json").exists())

    def test_development_gate_stops_heldout_on_validation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            with patch("src.school.cmdp_experiments.validate_episode", side_effect=ValueError("ledger mismatch")):
                with self.assertRaisesRegex(ValueError, "ledger mismatch"):
                    run_experiments(ScenarioConfig(num_students=2, horizon=1), output=output,
                                    policies=("wait",), development_seed_count=1, evaluation_seed_count=1)
            self.assertEqual(json.loads((output / "failure.json").read_text())["partition"], "development")
            self.assertFalse((output / "development_validation.json").exists())

    def test_development_only_exports_are_reproducible_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "development"
            config = ScenarioConfig(num_students=3, horizon=2)
            run_experiments(config, output=output, policies=BASELINES,
                            development_seed_count=2, evaluation_seed_count=1, stage="development")
            manifest = json.loads((output / "manifest.json").read_text())
            episodes = [json.loads(line) for line in (output / "episodes.jsonl").read_text().splitlines()]
            self.assertEqual({row["partition"] for row in episodes}, {"development"})
            self.assertEqual(summarize(episodes, manifest), json.loads((output / "summary.json").read_text()))
            with (output / "episode_results.csv").open() as source:
                self.assertEqual(len(list(csv.DictReader(source))), 10)
            with (output / "monthly_results.csv").open() as source:
                self.assertEqual(len(list(csv.DictReader(source))), 30)
            self.assertEqual(len(list((output / "figures").glob("*.png"))), 8)
            self.assertFalse((output / "tiny_exact.json").exists())
            self.assertTrue((output / "COMPLETED.json").exists())
            with self.assertRaises(FileExistsError):
                run_experiments(config, output=output)

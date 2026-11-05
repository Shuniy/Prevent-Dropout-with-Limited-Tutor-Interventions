"""The saved grid is complete, paired, reproducible and gated before held-out runs."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.school.fairness_experiments import run_fairness_experiments, experiment_grid
from src.school.scenario_config import ScenarioConfig


class FairnessExperimentTests(unittest.TestCase):
    def test_complete_paired_grid_and_reproducible_outputs(self):
        config = ScenarioConfig(num_students=6, horizon=4, monthly_admissions=1,
                                monthly_appointments=5)
        with tempfile.TemporaryDirectory() as temporary:
            outputs = [Path(temporary) / name for name in ("first", "second")]
            for output in outputs:
                run_fairness_experiments(config, output=output, development_seed_count=1,
                                          evaluation_seed_count=1)
                self.assertTrue((output / "COMPLETED.json").is_file())
                self.assertEqual(len(list(csv.DictReader((output / "episode_results.csv").read_text().splitlines()))),
                                 2 * len(experiment_grid(config)))
                for name in ("episode_results", "monthly_results", "group_access", "fairness_shortfalls",
                             "fairness_targets", "fairness_retention_tradeoff", "budget_sensitivity",
                             "effect_sensitivity", "solver_diagnostics", "window_history"):
                    self.assertTrue((output / (name + ".csv")).is_file())
                self.assertEqual(len(list((output / "figures").glob("*.png"))), 5)
                rows = list(csv.DictReader((output / "episode_results.csv").read_text().splitlines()))
                for row in rows:
                    resource = next(r for r in rows if r["partition"] == row["partition"]
                                    and r["seed"] == row["seed"] and r["budget"] == row["budget"]
                                    and r["effect_strength"] == row["effect_strength"]
                                    and r["policy"] == "terminal_value")
                    if row["policy"] == "fairness_q0":
                        self.assertEqual(row["allocation_sha256"], resource["allocation_sha256"])
                    if float(row["effect_strength"]) == 0:
                        self.assertEqual(row["trajectory_sha256"], resource["trajectory_sha256"])
            def read_stable(path):
                rows = list(csv.DictReader(path.read_text().splitlines()))
                return [{k: v for k, v in row.items() if "runtime" not in k} for row in rows]
            self.assertEqual(read_stable(outputs[0] / "episode_results.csv"),
                             read_stable(outputs[1] / "episode_results.csv"))
            for name in ("group_access.csv", "window_history.csv"):
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes())
            with self.assertRaises(FileExistsError):
                run_fairness_experiments(config, output=outputs[0])

    def test_development_failure_blocks_heldout_and_records_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failed"
            with patch("src.school.fairness_experiments.run_policy", side_effect=ValueError("bad allocation")):
                with self.assertRaises(ValueError):
                    run_fairness_experiments(ScenarioConfig(), output=output,
                                              development_seed_count=1, evaluation_seed_count=1)
            self.assertTrue((output / "experiment_config.json").is_file())
            failure = json.loads((output / "failure.json").read_text())
            self.assertEqual(failure["partition"], "development")
            self.assertFalse((output / "evaluation_validation.json").exists())
            self.assertFalse((output / "COMPLETED.json").exists())

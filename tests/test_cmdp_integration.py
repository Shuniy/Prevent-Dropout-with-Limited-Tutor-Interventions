import contextlib
from dataclasses import asdict, replace
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.main import main
from src.school import School, ScenarioConfig
from src.school.allocation_result import AllocationResult
from src.school.cmdp_scenarios import build_school


class RecordingWaitPolicy:
    def __init__(self):
        self.snapshots = []

    def plan(self, state):
        self.snapshots.append(state)
        return AllocationResult()


class SchoolCMDPIntegrationTests(unittest.TestCase):
    def test_school_runs_an_injected_policy_without_changing_source_models(self):
        config = ScenarioConfig(num_students=3, horizon=2)
        school = build_school(config)
        self.assertIsInstance(school, School)
        students_before = [asdict(student) for student in school.students]
        mentors_before = [asdict(mentor) for mentor in school.mentors]
        policy = RecordingWaitPolicy()
        simulation = school.run_cmdp(policy, config=config)
        self.assertEqual([state.month for state in policy.snapshots], [1, 2])
        self.assertTrue(simulation.environment.done)
        self.assertEqual(len(simulation.environment.records), 2)
        self.assertFalse(hasattr(policy.snapshots[0], "_conditions"))
        self.assertEqual(students_before, [asdict(student) for student in school.students])
        self.assertEqual(mentors_before, [asdict(mentor) for mentor in school.mentors])
        self.assertEqual(simulation.environment.observe().remaining_budget, config.budget)

    def test_school_can_derive_configuration_and_rejects_conflicting_configuration(self):
        school = School(num_students=2, num_mentors=1, num_months=2, budget=5, seed=7)
        simulation = school.run_cmdp(RecordingWaitPolicy())
        self.assertEqual(simulation.environment.config.horizon, 2)
        self.assertEqual(simulation.environment.config.budget, 5)
        self.assertEqual(simulation.environment.config.seed, 7)
        with self.assertRaisesRegex(ValueError, "must match"):
            school.create_cmdp_environment(config=ScenarioConfig(horizon=3))

    def test_cmdp_is_the_default_and_uses_versioned_config(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments = ["school-dropout", "--output", directory]
            with (
                patch.object(sys, "argv", arguments),
                patch(
                    "src.school.cmdp_experiments.run_experiments", return_value=Path(directory)
                ) as run,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                main()
            config = run.call_args.args[0]
            self.assertEqual((config.num_students, config.horizon, config.budget), (100, 12, 150))

    def test_script_and_module_cmdp_entrypoints_save_real_reports(self):
        for entry in (["src/main.py"], ["-m", "src.main"]):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "run"
                environment = dict(
                    os.environ,
                    MPLCONFIGDIR=str(Path(directory) / "matplotlib"),
                    XDG_CACHE_HOME=str(Path(directory) / "cache"),
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        *entry,
                        "--students",
                        "3",
                        "--months",
                        "2",
                        "--budget",
                        "5",
                        "--seed",
                        "73",
                        "--policies",
                        "wait",
                        "terminal_value",
                        "--development-seeds",
                        "1",
                        "--evaluation-seeds",
                        "1",
                        "--output",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                    env=environment,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertEqual(manifest["config"]["num_students"], 3)
                self.assertEqual(manifest["config"]["budget"], 5)
                self.assertEqual(manifest["development_seeds"], [73])
                self.assertEqual(manifest["evaluation_seeds"], [10073])
                self.assertTrue((output / "report.md").is_file())
                self.assertTrue((output / "monthly_conditions.png").is_file())

    def test_invalid_cmdp_options_fail_before_creating_outputs(self):
        for options in (
            ["--development-seeds", "0"],
            ["--policies", "missing"],
            ["--sessions", "4"],
        ):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "run"
                arguments = ["school-dropout", "--output", str(output), *options]
                with (
                    patch.object(sys, "argv", arguments),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit):
                        main()
                self.assertFalse(output.exists())

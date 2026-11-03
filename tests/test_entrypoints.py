import contextlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.main import main
from tests.helpers import FakeClient, write_history


class EntrypointTests(unittest.TestCase):
    def test_allocation_runs_as_script_and_module(self):
        for entry in (["src/main.py"], ["-m", "src.main"]):
            result = subprocess.run([sys.executable, *entry, "--allocation-only", "--students", "2",
                                     "--mentors", "1", "--months", "1"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("\n"), 1)
            self.assertIn("Allocation complete", result.stdout)

    def test_intervention_cli_saves_results_without_progress_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "histories"
            # Every support type uses the same tiny transcript fixture.
            from src.utils.constants import ALL_SUPPORT_TYPES
            for support in ALL_SUPPORT_TYPES:
                write_history(root, f"{support}/student", count=2)
            output = Path(directory) / "run"
            arguments = ["school-dropout", "--students", "1", "--mentors", "1",
                         "--history-root", str(root), "--output", str(output)]
            stream = io.StringIO()
            client = FakeClient()
            with patch.object(sys, "argv", arguments), patch("src.main.OllamaClient", return_value=client), \
                 patch("src.main.SessionIndex", side_effect=AssertionError("simple mode must not build an index")), \
                 contextlib.redirect_stdout(stream):
                main()
            report = json.loads((output / "final_report.json").read_text())
            self.assertEqual(report["status"], "finished")
            self.assertEqual(stream.getvalue().count("\n"), 1)
            self.assertEqual(len(client.contexts), 1)
            self.assertEqual(len(client.contexts[0]["sessions"]), 2)

    def test_simulation_cli_preserves_optional_rag(self):
        from src.utils.constants import ALL_SUPPORT_TYPES
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "histories"
            for support in ALL_SUPPORT_TYPES:
                write_history(root, f"{support}/student", count=2)
            output = Path(directory) / "run"
            arguments = ["school-dropout", "--students", "1", "--mentors", "1", "--method", "rag",
                         "--history-root", str(root), "--output", str(output)]
            client = FakeClient()
            with patch.object(sys, "argv", arguments), patch("src.main.OllamaClient", return_value=client), \
                 contextlib.redirect_stdout(io.StringIO()):
                main()
            self.assertEqual(json.loads((output / "final_report.json").read_text())["status"], "finished")
            self.assertEqual(len(client.contexts), 2)
            self.assertEqual(client.contexts[0]["earlier_validated_memory"], [])

    def test_standalone_rag_command_saves_a_cutoff_result(self):
        from src.intervention.rag import main as rag_main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "histories"
            write_history(root, count=2)
            output = Path(directory) / "conclusion.json"
            arguments = ["rag", "02_tutoring/student", "--root", str(root),
                         "--through-session", "1", "--output", str(output)]
            client = FakeClient()
            with patch.object(sys, "argv", arguments), patch("src.intervention.rag.OllamaClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
                rag_main()
            self.assertEqual(json.loads(output.read_text())["as_of_session"], 1)
            self.assertEqual(len(client.contexts), 1)

    def test_failed_intervention_cli_exits_nonzero_and_keeps_results(self):
        from src.utils.constants import ALL_SUPPORT_TYPES
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "histories"
            for support in ALL_SUPPORT_TYPES:
                write_history(root, f"{support}/student", count=1)
            output = Path(directory) / "run"
            arguments = ["school-dropout", "--students", "1", "--mentors", "1",
                         "--history-root", str(root), "--output", str(output)]
            errors = io.StringIO()
            with patch.object(sys, "argv", arguments), patch("src.main.OllamaClient", return_value=FakeClient(fail_at=1)), contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit) as failure:
                    main()
            self.assertEqual(failure.exception.code, 1)
            self.assertIn("Intervention failed", errors.getvalue())
            self.assertEqual(json.loads((output / "final_report.json").read_text())["status"], "failed")

    def test_cli_rejects_equal_or_nested_private_output_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory) / "public"
            for private in (public, public / "private", public.parent):
                arguments = ["school-dropout", "--students", "1", "--output", str(public),
                             "--private-output", str(private)]
                with patch.object(sys, "argv", arguments), \
                     patch("src.main.OllamaClient") as client, \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as failure:
                        main()
                self.assertEqual(failure.exception.code, 1)
                client.assert_not_called()
                self.assertFalse(public.exists())

    def test_invalid_configuration_has_a_concise_cli_error(self):
        result = subprocess.run([sys.executable, "-m", "src.main", "--months", "0"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be positive", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_examples_can_be_imported_and_executed_without_import_side_effects(self):
        names = ("simple_agent", "agent_based_modelling", "markov_chains",
                 "markov_decision_process", "budgeted_mdp", "cmdp")
        for name in names:
            with self.subTest(name=name):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    module = importlib.import_module(f"src.basic_examples.{name}")
                self.assertEqual(stream.getvalue(), "")
                with contextlib.redirect_stdout(stream):
                    module.main()
                self.assertTrue(stream.getvalue().strip())


if __name__ == "__main__":
    unittest.main()

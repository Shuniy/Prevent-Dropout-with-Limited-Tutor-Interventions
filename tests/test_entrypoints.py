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
    def test_cli_rejects_removed_intervention_and_allocation_options(self):
        for option in (
            ["--cmdp"],
            ["--allocation-only"],
            ["--method", "simple"],
            ["--method", "rag"],
            ["--history-root", "histories"],
            ["--private-output", "private"],
        ):
            with self.subTest(option=option), patch.object(sys, "argv", ["school-dropout", *option]), \
                 patch("src.main.run_cmdp_experiments") as run, \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    main()
                self.assertEqual(failure.exception.code, 2)
                run.assert_not_called()

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

    def test_invalid_configuration_has_a_concise_cli_error(self):
        result = subprocess.run([sys.executable, "-m", "src.main", "--months", "0"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("horizon must be a positive integer", result.stderr)
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

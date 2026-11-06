"""Integration checks for the console-first comparison entry point."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.main import main
from src.school import simulation_comparison


class ComparisonTests(unittest.TestCase):
    def test_all_modes_share_config_and_save_after_console(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison"
            stream = io.StringIO()
            original = simulation_comparison.write_csv

            def check_order(path, rows):
                self.assertIn("# Simulation comparison", stream.getvalue())
                original(path, rows)

            argv = ["school-dropout", "--extractor", "fixture", "--students", "3",
                    "--months", "2", "--budget", "5", "--seed", "73", "--output", str(output)]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stream), \
                    patch.object(simulation_comparison, "write_csv", side_effect=check_order):
                main()
            rows = json.loads((output / "comparison.json").read_text())
            self.assertEqual(len(rows), 17)
            self.assertTrue(all(row["seed"] == 73 and row["students"] == 3 and
                                row["months"] == 2 and row["seconds"] >= 0 for row in rows))
            self.assertTrue(all(row["real_llm_calls"] == 0 for row in rows))
            manifest = json.loads((output / "manifest.json").read_text())
            for path in output.glob("*/experiment_config.json"):
                episode = json.loads(path.read_text())
                self.assertEqual(episode["scenario"], manifest["scenario"])
                self.assertEqual(episode["observation_model"], manifest["observation"])
            for policy in ("resource", "fairness"):
                matched = (output / f"{policy}_b_matched" / "mentor_notes.jsonl").read_text()
                llm = (output / f"{policy}_llm_notes" / "mentor_notes.jsonl").read_text()
                self.assertEqual(matched, llm)
            self.assertTrue((output / "report.md").exists())
            before = (output / "comparison.json").read_bytes()
            with patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(before, (output / "comparison.json").read_bytes())

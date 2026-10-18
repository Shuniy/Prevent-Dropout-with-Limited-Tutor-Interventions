"""Check shared runner behavior, path resolution and honest simulation status."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest

from src.cli import main
from src.data.dataset import DATA_DIR
from src.experiments.runner import population_summary, run_simulation


class RunnerTests(unittest.TestCase):
    def test_summary_and_reset_from_another_working_directory(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                self.assertEqual(population_summary()['students'].tolist(), [1200, 400, 400])
                result = run_simulation(dry_run=True)
            finally:
                os.chdir(original)
        self.assertEqual(result.iloc[0].to_dict(), {
            'status': 'reset_validated', 'split': 'train', 'students': 1200,
            'steps_executed': 0})

    def test_config_selects_split_and_rejects_unknown_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.toml'
            relative = os.path.relpath(DATA_DIR, path.parent.resolve())
            content = f'[data]\ndirectory = "{relative}"\n[simulation]\nsplit = "validation"\n'
            path.write_text(content)
            self.assertEqual(run_simulation(path, dry_run=True).iloc[0]['students'], 400)
            path.write_text(content + 'unsupported = 1\n')
            with self.assertRaises(ValueError):
                run_simulation(path, dry_run=True)

    def test_full_simulation_is_explicitly_unimplemented(self):
        with self.assertRaises(NotImplementedError):
            run_simulation()
        with contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as error:
                main(['simulate'])
        self.assertEqual(error.exception.code, 2)
        self.assertIn('not implemented', output.getvalue())

    def test_cli_dry_run(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['simulate', '--dry-run']), 0)
        self.assertIn('reset_validated', output.getvalue())

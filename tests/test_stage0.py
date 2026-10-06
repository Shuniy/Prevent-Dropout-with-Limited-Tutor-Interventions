"""Failure and publication regression checks, using small local fixtures."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/data'))
from reproducibility import preflight, run_build, sha, write_json, make_package, check_artifacts, REQUIRED_SOURCE_PATHS


class Stage0Safety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base/'raw'
        self.root.mkdir()
        self.doc = self.base/'plan.md'
        self.doc.write_text('Research reference\n')
        self.cfg = self.base/'manifest.json'
        rows = []
        for rel in sorted(REQUIRED_SOURCE_PATHS):
            p = self.root/rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix == '.zip':
                with zipfile.ZipFile(p, 'w') as z:
                    z.writestr('readme.txt', 'fixture')
            else:
                p.write_text('a,b\n1,2\n')
            rows.append({'relative_path': rel, 'sha256': sha(p), 'bytes': p.stat().st_size})
        self.config = {'schema_version': 1, 'seed': 20261006, 'reference_date': '2026-10-06',
                       'research_plan_sha256': sha(self.doc), 'files': rows}
        write_json(self.cfg, self.config)
        self.out = self.base/'not_created'/'version1'

    def preflight(self):
        return preflight(self.root, self.doc, self.cfg, self.out)

    def test_missing_input_fails_before_writes(self):
        (self.root/self.config['files'][0]['relative_path']).unlink()
        called = []
        with self.assertRaises(ValueError):
            run_build(lambda *args: called.append(True), self.root, self.doc, self.cfg, self.out)
        self.assertEqual(called, [])
        self.assertFalse(self.out.parent.exists())

    def test_missing_document_fails_before_writes(self):
        self.doc.unlink()
        with self.assertRaises(FileNotFoundError):
            self.preflight()
        self.assertFalse(self.out.parent.exists())

    def test_modified_source_is_rejected(self):
        (self.root/self.config['files'][0]['relative_path']).write_text('a,b\n3,4\n')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.preflight()
        self.assertFalse(self.out.parent.exists())

    def test_modified_reference_is_rejected(self):
        self.doc.write_text('different')
        with self.assertRaisesRegex(ValueError, 'Research-plan identity mismatch'):
            self.preflight()

    def test_generated_directories_and_unlisted_files_are_ignored(self):
        for rel in ['results/old/data/test.csv', 'student_cmdp_study/data/test.csv',
                    'audit_student_cmdp/sources.csv', 'cache/bogus.csv', 'other.csv']:
            path = self.root/rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('deliberately malformed input')
        self.assertEqual(len(self.preflight()[-1]), 22)

    def test_generated_paths_cannot_be_manually_added(self):
        for rel in ['student_cmdp_study/data/student_dataset.csv', 'results/v1/data/test.csv',
                    'student+performance/outputs/test.csv', '../escape.csv', '/tmp/escape.csv']:
            with self.subTest(rel=rel):
                cfg = dict(self.config)
                cfg['files'] = [dict(self.config['files'][0], relative_path=rel), *self.config['files'][1:]]
                write_json(self.cfg, cfg)
                with self.assertRaises(ValueError):
                    self.preflight()

    def test_source_symlink_is_rejected(self):
        path = self.root/self.config['files'][0]['relative_path']
        path.unlink()
        path.symlink_to(self.doc)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.preflight()

    def test_existing_output_is_not_overwritten(self):
        self.out.mkdir(parents=True)
        marker = self.out/'precious.txt'
        marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.preflight()
        self.assertEqual(marker.read_text(), 'keep')

    def test_output_inside_raw_directory_is_rejected(self):
        self.out = self.root/'student+performance'/'new'
        with self.assertRaisesRegex(ValueError, 'Nested output'):
            self.preflight()

    def test_failed_build_is_not_published(self):
        def fail(*args):
            (args[2]/'partial.csv').write_text('partial')
            raise RuntimeError('injected build failure')
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            run_build(fail, self.root, self.doc, self.cfg, self.out)
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.out.parent.iterdir()), [])

    def package_fixture(self):
        result = self.base/'result'
        (result/'data').mkdir(parents=True)
        p = result/'data/table.csv'
        p.write_text('a\n1\n')
        write_json(result/'COMPLETED.json', {'schema_version': 1, 'stage': 0,
            'artifacts': [{'relative_path': 'data/table.csv', 'sha256': sha(p), 'bytes': p.stat().st_size}]})
        return result

    def test_package_ignores_nested_copies_archives_and_itself(self):
        import zipfile
        result = self.package_fixture()
        before = make_package(result, self.base/'first.zip')
        (result/'old/data').mkdir(parents=True)
        (result/'old/data/copy.csv').write_text('unrelated')
        (result/'old.zip').write_text('unrelated archive')
        (result/'verify_and_package.py').write_text('unlisted code')
        after = make_package(result, self.base/'second.zip')
        self.assertEqual(before, after)
        with zipfile.ZipFile(self.base/'second.zip') as z:
            self.assertEqual(z.namelist(), ['student_cmdp_stage0/COMPLETED.json', 'student_cmdp_stage0/data/table.csv'])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            make_package(result, self.base/'first.zip')

    def test_package_rejects_tampering_and_nested_manifest_entries(self):
        result = self.package_fixture()
        (result/'data/table.csv').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            make_package(result, self.base/'bad.zip')
        self.assertFalse((self.base/'bad.zip').exists())
        ledger = json.loads((result/'COMPLETED.json').read_text())
        ledger['artifacts'][0]['relative_path'] = 'old/data/table.csv'
        write_json(result/'COMPLETED.json', ledger)
        with self.assertRaisesRegex(ValueError, 'Not a package artifact'):
            check_artifacts(result)

    def test_validation_has_no_workbook_runtime_dependency(self):
        import verify_and_package
        self.assertNotIn('openpyxl', sys.modules)
        self.assertNotIn('artifact_tool', sys.modules)
        self.assertTrue(callable(verify_and_package.validate_data))


if __name__ == '__main__':
    unittest.main()

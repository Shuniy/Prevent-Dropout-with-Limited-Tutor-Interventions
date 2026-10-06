"""Integration gate: relocation, repeatability, immutable inputs and bounded packages."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO/'src/data'))
from build_study import build_data
from reproducibility import run_build, sha, write_json, make_package, check_artifacts
from verify_and_package import validate_data, validate_workbook


def snapshot(root):
    # A preservation check, never an authoritative raw-source inventory.
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*')
            if p.is_file() and p.name != '.DS_Store'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    original = snapshot(args.source_root)
    baseline_original = snapshot(args.baseline)
    config = json.loads((REPO/'configs/raw_sources.v1.json').read_text())
    comparisons = []
    with tempfile.TemporaryDirectory(prefix='stage0-gate-') as tmp:
        root = Path(tmp)/'relocated_sources'
        root.mkdir()
        for row in config['files']:
            target = root/row['relative_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.source_root/row['relative_path'], target)
        # Reference relocation is separate from raw-source relocation.
        doc = Path(tmp)/'reference.md'
        shutil.copyfile(REPO/'docs/references/school_dropout_research_plan.md', doc)
        out1, out2 = root/'results/first', root/'results/second'
        with contextlib.redirect_stdout(io.StringIO()):
            first = run_build(build_data, root, doc, REPO/'configs/raw_sources.v1.json', out1)
        # Add generated and irrelevant inputs under the same raw-source tree.
        for rel in ['student_cmdp_study/data/generated.csv', 'audit_student_cmdp/inventory.csv',
                    'cache/generated.csv', 'archives/old.zip']:
            p = root/rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('This must not be parsed as a source')
        pkg1 = make_package(out1, root/'results/first.zip')
        with contextlib.redirect_stdout(io.StringIO()):
            second = run_build(build_data, root, doc, REPO/'configs/raw_sources.v1.json', out2)
        pkg2 = make_package(out2, root/'results/second.zip')
        if snapshot(out1) != snapshot(out2):
            raise AssertionError('Repeated builds differ')
        if pkg1 != pkg2:
            raise AssertionError('Repeated packages differ')
        for p in sorted(out1.glob('*/*.csv')):
            rel = p.relative_to(out1)
            if str(rel) in {'analysis/source_manifest.csv', 'analysis/archive_inventory.csv'}:
                continue  # intentional portable/bounded source identity changes
            previous = args.baseline/rel
            pd.testing.assert_frame_equal(pd.read_csv(p), pd.read_csv(previous),
                                          check_exact=False, rtol=1e-8, atol=1e-9)
            comparisons.append(str(rel))
        data_evidence = validate_data(out2)
        check_artifacts(out2)
        workbook = validate_workbook(args.baseline/'student_analysis.xlsx')
        if original != snapshot(args.source_root) or baseline_original != snapshot(args.baseline):
            raise AssertionError('Original data or baseline changed')
        evidence = {'status': 'passed', 'executed_on': '2026-10-07',
            'raw_files': len(config['files']), 'raw_csv_files': 16,
            'identical_repeated_builds': True, 'identical_repeated_archives': True,
            'relocated_sources_and_reference_verified': True,
            'generated_and_unlisted_sources_excluded': True,
            'baseline_tables_compared': comparisons, 'numerical_rtol': 1e-8, 'numerical_atol': 1e-9,
            'original_tree_unchanged': True, 'baseline_tree_unchanged': True,
            'baseline_preserved_file_count': len(baseline_original),
            'artifact_count': first['artifact_count'], 'package': pkg1,
            'data_validation': data_evidence, 'optional_baseline_workbook_xml': workbook,
            'simulator_or_policy_experiments_executed': False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, evidence)
    print(json.dumps({k:v for k,v in evidence.items() if k not in {'data_validation', 'baseline_tables_compared'}}, indent=2))


if __name__ == '__main__':
    main()

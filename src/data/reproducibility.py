"""Stage 0: bounded inputs, preflight checks and atomic publication."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import platform
import shutil
import tempfile
import zipfile

FORBIDDEN = {'student_cmdp_study', 'results', 'outputs', 'output', 'audit',
             'audit_student_cmdp', 'archive', 'archives', 'cache', '__pycache__',
             'node_modules', '.git', '.venv', 'sources'}
SOURCE_TOP = {'student+performance', 'student+performance.zip',
              'Student_Dropout_rate.csv', 'predict+students+dropout+and+academic+success.zip',
              'student-dropout-prediction', 'abdullah0a_student-dropout-analysis-and-prediction-dataset',
              'Student-Dropout-Success-All-Academic-Levels'}


# Frozen audited layout; change only through a new source-manifest version.
REQUIRED_SOURCE_PATHS = frozenset({
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels.zip',
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/ieee_online_learning_behavior.csv',
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/massachusetts_school_district_aggregates.csv',
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/masters_students_research_focused.csv',
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/school_students_massachusetts_style.csv',
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/spanish_technological_university_raw.csv',
    'Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/university_students_comprehensive.csv',
    'Student_Dropout_rate.csv',
    'abdullah0a_student-dropout-analysis-and-prediction-dataset/student dropout.csv',
    'predict+students+dropout+and+academic+success.zip',
    'student+performance.zip',
    'student+performance/student.zip',
    'student+performance/student/student-mat.csv',
    'student+performance/student/student-merge.R',
    'student+performance/student/student-por.csv',
    'student+performance/student/student.txt',
    'student-dropout-prediction/X_test.csv',
    'student-dropout-prediction/X_train.csv',
    'student-dropout-prediction/student-mat.csv',
    'student-dropout-prediction/student-por.csv',
    'student-dropout-prediction/y_test.csv',
    'student-dropout-prediction/y_train.csv',
})


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def safe_relative(value):
    p = PurePosixPath(value)
    require(bool(value) and not p.is_absolute() and '..' not in p.parts
            and '\\' not in value and p.as_posix() == value,
            f'Not a normalized relative path: {value}')
    return p


def resolve_source(root, relative):
    p = safe_relative(relative)
    require(p.parts[0] in SOURCE_TOP and not any(part in FORBIDDEN or part.startswith('.') for part in p.parts),
            f'Generated or unrecognized source location: {relative}')
    target = root / p
    require(not any(parent.is_symlink() for parent in [target, *target.parents] if parent != root.parent),
            f'Symlink source is not allowed: {relative}')
    require(target.resolve().is_relative_to(root), f'Source escaped root: {relative}')
    require(target.is_file(), f'Missing input: {target}')
    return target


def preflight(source_root, research_plan, manifest, output_root=None):
    root = Path(source_root).resolve(strict=True)
    doc = Path(research_plan).resolve(strict=True)
    config_path = Path(manifest).resolve(strict=True)
    require(root.is_dir() and doc.is_file() and config_path.is_file(), 'Invalid input path')
    config = json.loads(config_path.read_text())
    require(config.get('schema_version') == 1, 'Unsupported source manifest version')
    require(config.get('seed') == 20261006, 'Stage 0 preserves the baseline seed')
    require(config.get('reference_date') == '2026-10-06', 'Unexpected baseline reference date')
    rows = config['files']
    require(bool(rows), 'Empty source manifest')
    require(len({r['relative_path'] for r in rows}) == len(rows), 'Duplicate source entry')
    require({r['relative_path'] for r in rows} == REQUIRED_SOURCE_PATHS, 'Source manifest does not match the audited v1 input set')
    paths = [resolve_source(root, row['relative_path']) for row in rows]
    require(sum(p.suffix == '.csv' for p in paths) == 16, 'Expected the 16 audited source CSVs')
    for row, path in zip(rows, paths):
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                f'Source identity mismatch: {row["relative_path"]}')
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as z:
                require(z.testzip() is None, f'Corrupt source archive: {path.name}')
    require(sha(doc) == config['research_plan_sha256'], 'Research-plan identity mismatch')
    if output_root is not None:
        out = Path(output_root).absolute()
        require(not out.exists() and not out.is_symlink(), f'Output already exists: {out}')
        resolved = out.resolve()
        for input_path in [*paths, doc, config_path]:
            require(not input_path.is_relative_to(resolved), 'Output overlaps an input')
        if resolved.is_relative_to(root):
            rel = resolved.relative_to(root)
            require(len(rel.parts) >= 2 and rel.parts[0] in {'results', 'outputs'},
                    'Nested output must be a new version under results/ or outputs/')
    return root, doc, config_path, config, paths


def verify_sources(root, doc, config):
    for row in config['files']:
        path = resolve_source(Path(root), row['relative_path'])
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                f'Source changed: {row["relative_path"]}')
    require(sha(doc) == config['research_plan_sha256'], 'Research plan changed')
    return {'raw_files': len(config['files']), 'raw_csv_files': sum(r['relative_path'].endswith('.csv') for r in config['files']),
            'research_plan_files': 1, 'all_hashes_match': True}


def collect_artifacts(root):
    """Only approved direct children, never a recursive package discovery."""
    entries = []
    for folder, suffixes in [('data', {'.csv'}), ('analysis', {'.csv', '.json'}),
                             ('configs', {'.csv', '.json'}), ('support', {'.json'})]:
        for path in sorted((root / folder).iterdir()):
            require(path.is_file() and not path.is_symlink() and path.suffix in suffixes,
                    f'Unexpected build output: {path}')
            entries.append({'relative_path': path.relative_to(root).as_posix(),
                            'sha256': sha(path), 'bytes': path.stat().st_size})
    return entries


def run_build(builder, source_root, research_plan, manifest, output_root):
    root, doc, cfg_path, cfg, paths = preflight(source_root, research_plan, manifest, output_root)
    # All input checks, including the document and archives, finish before any write.
    from verify_and_package import validate_data
    import numpy as np
    import pandas as pd
    out = Path(output_root).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + out.name + '.staging-', dir=out.parent))
    try:
        builder(root, doc, stage, paths, cfg['seed'])
        shutil.copyfile(cfg_path, stage / 'configs/raw_sources.v1.json')
        evidence = validate_data(stage)
        evidence['source_identity'] = verify_sources(root, doc, cfg)
        evidence['workbook_checks'] = {'status': 'not_requested', 'rendering': 'not_performed'}
        evidence['policy_experiments_executed'] = False
        write_json(stage / 'analysis/final_readback_checks.json', evidence)
        code_files = [Path(__file__), Path(__file__).with_name('build_study.py'), Path(__file__).with_name('verify_and_package.py')]
        write_json(stage / 'analysis/run_metadata.json', {
            'stage': 0, 'seed': cfg['seed'], 'reference_date': cfg['reference_date'],
            'source_manifest_sha256': sha(cfg_path), 'research_plan_sha256': sha(doc),
            'code_sha256': {p.name: sha(p) for p in code_files},
            'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__},
            'output_kind': 'data_preparation_and_descriptive_baselines',
            'scientific_transformations': 'unchanged_from_audited_baseline'})
        entries = collect_artifacts(stage)
        write_json(stage / 'COMPLETED.json', {'schema_version': 1, 'stage': 0, 'artifacts': entries})
        verify_sources(root, doc, cfg)
        require(not out.exists(), 'Output appeared during build; refusing to overwrite')
        stage.rename(out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'output': str(out), 'artifact_count': len(entries), 'sources': evidence['source_identity']}


def check_artifacts(root):
    root = Path(root).resolve(strict=True)
    completion = json.loads((root / 'COMPLETED.json').read_text())
    require(completion.get('schema_version') == 1 and completion.get('stage') == 0, 'Unsupported completion record')
    entries = completion['artifacts']
    require(bool(entries) and len({r['relative_path'] for r in entries}) == len(entries), 'Empty or duplicate artifact list')
    files = []
    allowed = {'data': {'.csv'}, 'analysis': {'.csv', '.json'}, 'configs': {'.csv', '.json'}, 'support': {'.json'}}
    for row in entries:
        rel = safe_relative(row['relative_path'])
        require(len(rel.parts) == 2 and rel.parts[0] in allowed and rel.suffix in allowed[rel.parts[0]],
                f'Not a package artifact: {rel}')
        path = root / rel
        require(not path.is_symlink() and not path.parent.is_symlink() and path.is_file(), f'Missing or linked artifact: {rel}')
        require(sha(path) == row['sha256'] and path.stat().st_size == row['bytes'], f'Artifact changed: {rel}')
        files.append(path)
    return files + [root / 'COMPLETED.json']


def make_package(root, archive):
    root = Path(root).resolve(strict=True)
    files = check_artifacts(root)
    dest = Path(archive).absolute()
    require(not dest.exists() and not dest.is_symlink(), f'Archive already exists: {dest}')
    require(not dest.resolve().is_relative_to(root), 'Archive must be outside the completed result')
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.package-', suffix='.zip', dir=dest.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for path in sorted(files):
                info = zipfile.ZipInfo('student_cmdp_stage0/' + path.relative_to(root).as_posix(), (2026, 10, 6, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, path.read_bytes())
        with zipfile.ZipFile(tmp) as z:
            require(z.testzip() is None and len(z.infolist()) == len(files), 'Archive readback failed')
        # Exclusive publication: a concurrent archive is never overwritten.
        os.link(tmp, dest)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return {'files': len(files), 'bytes': dest.stat().st_size, 'sha256': sha(dest)}


def build_cli(builder):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--research-plan', type=Path, required=True)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_build(builder, args.source_root, args.research_plan, args.source_manifest, args.output_root)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as e:
        parser.exit(1, f'Stage 0 failed: {e}\n')
    print(json.dumps(result, indent=2))

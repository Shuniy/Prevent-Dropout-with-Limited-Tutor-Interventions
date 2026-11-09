"""Bounded offline Phase 3 verification; synthetic fixtures, no model inference.

Uses a new destination, preserves complete logs, and never runs a research grid.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase2 import source_identity
from src.evaluation.provenance import active_directory, runtime_identity, verify_versions
from src.evaluation.research_experiments import aggregate, freeze, load_config, run_one
from src.evaluation.research_report import generate_report
from src.school import feedback_replay
from src.intervention.feedback_notes import NoteQuality
from src.intervention.observation_extractor import FixtureObservationExtractor
from src.school.allocation_policies import make_policy
from src.school.baseline_policy import BASELINES
from src.school.closed_loop_controller import ClosedLoopCMDPController, INFORMATION_MODES
from src.school.cmdp_scenarios import build_environment
from src.school.feedback_experiments import save_episode
from src.school.feedback_replay import replay_feedback_episode
from src.school.feedback_validation import validate_feedback_episode
from src.school.scenario_config import ScenarioConfig
from src.school.uncertainty_scenarios import UncertaintyScenarioConfig


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def historical_inventory(exclude):
    files = [ROOT/'docs/phase1_scientific_correctness.md', ROOT/'docs/phase2_scientific_correctness.md',
             ROOT/'docs/research_evaluation_protocol.md']
    for pattern in ('phase2_*', 'phase3_verification*', 'research_evaluation_v1'):
        for directory in (ROOT/'results').glob(pattern):
            files.extend(p for p in directory.rglob('*') if p.is_file() and not p.is_relative_to(exclude))
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}


def verify(output):
    output.mkdir(parents=True, exist_ok=False)
    identity = source_identity()
    historical_before = historical_inventory(output)
    commands = {}
    for name, command in {
        'focused': [sys.executable, '-m', 'unittest', 'tests.test_phase3_correctness',
                    'tests.test_phase3_final_repairs',
                    'tests.test_phase1_correctness', 'tests.test_phase2_correctness',
                    'tests.test_research_information', 'tests.test_simulation_comparison'],
        'offline': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
        'diff_check': ['git', 'diff', '--check'],
        'status': ['git', 'status', '--short'],
        'diff_stat': ['git', 'diff', '--stat'],
    }.items():
        print(f'Executing {shlex.join(command)}', flush=True)
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output/f'{name}.log').write_text(result.stdout)
        count = re.search(r'Ran (\d+) tests in ([\d.]+)s', result.stdout)
        commands[name] = {'command': shlex.join(command), 'exit_code': result.returncode,
            'tests': int(count[1]) if count else None, 'seconds': float(count[2]) if count else None}
        if result.returncode:
            write(output/'verification_failed.json', {'identity': identity, 'commands': commands})
            raise RuntimeError(f'{name} failed; see {output/name}.log')
    config = ScenarioConfig(num_students=6, num_mentors=2, horizon=3, monthly_admissions=1,
        monthly_appointments=5, budget=10, seed=73)
    names = (*BASELINES, 'resource', 'fairness', 'robust')
    rows, replays = [], {}
    with patch('src.intervention.ollama_client.OllamaClient.generate', side_effect=AssertionError('real model call')):
        for mode in INFORMATION_MODES:
            initial = None
            for name in names:
                policy = make_policy('terminal_value' if name == 'resource' else name, config)
                if name == 'robust':
                    policy.uncertainty_config = UncertaintyScenarioConfig(.43, 1.8, 5)
                c = ClosedLoopCMDPController(build_environment(config), policy, mode=mode,
                    extractor=FixtureObservationExtractor(), max_monitoring_notes_per_month=2,
                    note_quality_by_student={'SYN00001': NoteQuality(omission_probability=1)}).run_episode()
                validate_feedback_episode(c)
                if initial is not None:
                    assert initial == c.snapshots[0], 'unequal initial authorized information'
                initial = c.snapshots[0]
                rows.append({'policy': name, 'mode': mode, 'terminal_enrolled': c.environment.terminal_reward(),
                    'programmes': sum(len(d['admitted_ids']) for d in c.decisions),
                    'remaining_budget': c.environment.records[-1].remaining_budget,
                    'fairness_records': len(c.fairness_rows), 'real_llm_calls': 0})
                if mode == 'noisy_notes':
                    source = output/f'{name}_original'
                    save_episode(c, source)
                    a = replay_feedback_episode(source, output/f'{name}_replay_1')
                    b = replay_feedback_episode(source, output/f'{name}_replay_2')
                    assert a['deterministic_digest'] == b['deterministic_digest']
                    replays[name] = a['deterministic_digest']

    controls = {}
    for label, parameters in {
        'zero_effect': {'effect_strength': 0, 'budget': 10},
        'zero_budget_paid': {'budget': 0},
        'zero_budget_free': {'budget': 0, 'cost_per_appointment': 0},
        'zero_budget_free_no_capacity': {'budget': 0, 'cost_per_appointment': 0, 'monthly_appointments': 4},
    }.items():
        scenario = replace(config, **parameters)
        with patch('src.school.cmdp_environment.keyed_uniform', return_value=.975):
            runs = [ClosedLoopCMDPController(build_environment(scenario), make_policy(name, scenario)).run_episode()
                    for name in ('wait', 'need_priority')]
        for run in runs:
            validate_feedback_episode(run)
        equal = runs[0].evaluator_truth == runs[1].evaluator_truth
        assert equal == (label != 'zero_budget_free')
        controls[label] = {'truth_equal': equal, 'fixed_draw': .975,
            'programmes': [sum(len(d['admitted_ids']) for d in run.decisions) for run in runs],
            'remaining_budget': [run.environment.records[-1].remaining_budget for run in runs]}

    research = load_config()
    research['scenario'] = asdict(config)
    research['evaluation'].update(development_seeds=[73], evaluation_seeds=[10073, 10074],
                                 secondary_seeds=[10073], live_seeds=[10073])
    root = output/'immutable_records'
    first = freeze(root, configuration=research)
    for name in ('ResourceOnlyPoint', 'FairPoint', 'FairRobust'):
        run_one(root, research, first, 'development', name, 'b_matched', 73)
    aggregate(root)
    version = active_directory(root)
    no_primary = json.loads((version/'aggregation_status.json').read_text())
    assert no_primary['actual_primary_episodes'] == 0 and not no_primary['primary_complete']
    point = run_one(root, research, first, 'evaluation', 'FairPoint', 'd_matched', 10073)
    point_report = generate_report(root)
    assert 'INCOMPLETE / EXPLORATORY' in point_report.read_text()
    run_one(root, research, first, 'evaluation', 'FairRobust', 'd_matched', 10073)
    partial_report = generate_report(root)
    partial_status = json.loads((partial_report.parent/'aggregation_status.json').read_text())
    assert partial_status['actual_primary_episodes'] == 2 and not partial_status['primary_complete']
    partial_bytes = {str(p.relative_to(partial_report.parent)): p.read_bytes()
                     for p in partial_report.parent.rglob('*') if p.is_file()}
    for name in ('FairPoint', 'FairRobust'):
        run_one(root, research, first, 'evaluation', name, 'd_matched', 10074)
    complete_report = generate_report(root)
    completed_status = json.loads((complete_report.parent/'aggregation_status.json').read_text())
    assert completed_status['primary_complete'] and completed_status['actual_primary_episodes'] == 4
    assert 'COMPLETE PRIMARY EVALUATION' in complete_report.read_text()
    assert all((partial_report.parent/name).read_bytes() == value for name, value in partial_bytes.items())
    corrupt = output/'deliberately_corrupted_reports'
    shutil.copytree(root, corrupt, symlinks=True)
    corrupt_version = active_directory(corrupt)
    table = corrupt_version/'reports'/complete_report.parent.name/'primary_policy_comparison.csv'
    table.write_text(table.read_text().replace('0.8333333333333334', '0.123456789', 1)+'\n')
    try:
        verify_versions(corrupt)
    except ValueError as exc:
        corrupt_rejection = str(exc)
    else:
        raise AssertionError('corrupted report was accepted')
    replay_source = version/Path(point['trace_path']).parent/'replay'
    replay_target = output/'deliberately_failed_replay'
    original_read = feedback_replay.read_jsonl
    def late_mismatch(path):
        rows = original_read(path)
        return rows+[{'injected_late_mismatch': True}] if path.name == 'final_beliefs.jsonl' and replay_source not in path.parents else rows
    with patch.object(feedback_replay, 'read_jsonl', side_effect=late_mismatch):
        try:
            replay_feedback_episode(replay_source, replay_target)
        except ValueError as exc:
            replay_rejection = str(exc)
        else:
            raise AssertionError('failed replay was accepted')
    assert not replay_target.exists()
    report_lifecycle = {'zero_primary': no_primary, 'partial_primary': partial_status,
        'completed_tiny_primary': completed_status, 'first_report': str(point_report),
        'partial_report': str(partial_report), 'completed_report': str(complete_report),
        'previous_report_bytes_preserved': True, 'corrupted_report_rejected': corrupt_rejection,
        'late_replay_rejected': replay_rejection, 'failed_replay_not_published': True}
    old = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
           for p in active_directory(root).rglob('*') if p.is_file()}
    original_manifest = (root/'configuration_manifest.json').read_bytes()
    updated = deepcopy(research)
    updated['uncertainty']['radius'] = .44
    second = freeze(root, 'Offline verification amendment; no scientific outcome claim', configuration=updated)
    assert (root/'configuration_manifest.json').read_bytes() == original_manifest
    assert all(sha256((root/name).read_bytes()).hexdigest() == value for name, value in old.items())
    assert second['predecessor'] == first['input_digest']
    run_one(root, updated, second, 'development', 'FairRobust', 'b_matched', 73)
    aggregate(root)
    generate_report(root)
    versions = verify_versions(root)
    verify_command = [sys.executable, 'scripts/verify_experiment_records.py', str(root)]
    checked = subprocess.run(verify_command, cwd=ROOT, text=True, capture_output=True)
    (output/'immutable_verification.log').write_text(checked.stdout + checked.stderr)
    assert checked.returncode == 0
    commands['immutable_verification'] = {'command': shlex.join(verify_command), 'exit_code': checked.returncode}
    assert identity['source_sha256'] == source_identity()['source_sha256'], 'code changed during verification'
    assert historical_before == historical_inventory(output), 'historical evidence changed during verification'
    report = {'status': 'passed', 'identity': identity, 'runtime': runtime_identity(),
        'commands': commands, 'bounded_scenario': asdict(config), 'episodes': rows,
        'replay_digests': replays, 'controls': controls, 'immutable_versions': versions,
        'report_lifecycle': report_lifecycle,
        'historical_evidence_unchanged': True, 'historical_files_sha256': historical_before,
        'prior_manifest_and_episode_bytes_preserved': True, 'real_llm_calls': 0,
        'interpretation': 'Offline synthetic wiring and invariant tests; no empirical treatment-effect validation.'}
    write(output/'verification.json', report)
    print(json.dumps({'status': 'passed', 'episodes': len(rows), 'replayed_policies': len(replays),
        'tests': commands['offline']['tests'], 'source_sha256': identity['source_sha256'],
        'immutable_versions': versions['verified_versions'], 'real_llm_calls': 0}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verify(args.output.resolve())

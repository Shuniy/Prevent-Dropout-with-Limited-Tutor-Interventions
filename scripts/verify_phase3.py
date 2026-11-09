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
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase2 import source_identity
from src.evaluation.provenance import active_directory, runtime_identity, verify_versions
from src.evaluation.research_experiments import aggregate, freeze, load_config, run_one
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


def verify(output):
    output.mkdir(parents=True, exist_ok=False)
    identity = source_identity()
    commands = {}
    for name, command in {
        'focused': [sys.executable, '-m', 'unittest', 'tests.test_phase3_correctness',
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
    research['evaluation'].update(development_seeds=[73], evaluation_seeds=[10073],
                                 secondary_seeds=[10073], live_seeds=[10073])
    root = output/'immutable_records'
    first = freeze(root, configuration=research)
    for name in ('ResourceOnlyPoint', 'FairPoint', 'FairRobust'):
        run_one(root, research, first, 'development', name, 'b_matched', 73)
    aggregate(root)
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
    versions = verify_versions(root)
    verify_command = [sys.executable, 'scripts/verify_experiment_records.py', str(root)]
    checked = subprocess.run(verify_command, cwd=ROOT, text=True, capture_output=True)
    (output/'immutable_verification.log').write_text(checked.stdout + checked.stderr)
    assert checked.returncode == 0
    commands['immutable_verification'] = {'command': shlex.join(verify_command), 'exit_code': checked.returncode}
    assert identity['source_sha256'] == source_identity()['source_sha256'], 'code changed during verification'
    report = {'status': 'passed', 'identity': identity, 'runtime': runtime_identity(),
        'commands': commands, 'bounded_scenario': asdict(config), 'episodes': rows,
        'replay_digests': replays, 'controls': controls, 'immutable_versions': versions,
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

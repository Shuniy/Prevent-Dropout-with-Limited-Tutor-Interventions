"""Read validated completed cells and assess the frozen primary matrix offline."""
from hashlib import sha256
from copy import deepcopy
from pathlib import Path

from .provenance import digest, read_record, verify_directory, validate_extractor_identity

PRIMARY_POLICIES = ('FairPoint', 'FairRobust')


def primary_design(config):
    return {'phase': 'evaluation', 'setting': 'primary', 'mode': 'd_matched',
            'policies': list(PRIMARY_POLICIES), 'seeds': list(config['evaluation']['evaluation_seeds'])}


def execution_inputs(config, input_digest, phase, policy, mode, seed, *, setting='primary',
                     extractor_identity=None, **options):
    def effective(name, default):
        return default if options.get(name) is None else options[name]
    return {'policy': policy, 'mode': mode, 'seed': seed, 'phase': phase, 'setting': setting,
        'input_digest': input_digest,
        'budget': effective('budget', config['scenario']['budget']),
        'effect': effective('effect', config['scenario'].get('effect_strength', 1.0)),
        'radius': effective('radius', config['uncertainty']['radius']) if policy == 'FairRobust' else None,
        'missingness': options.get('missingness'), 'sparse': options.get('sparse', False),
        'extractor_identity': extractor_identity}


def validate_execution_configuration(manifest, summary, replay):
    """Cross-check declared settings against the actual saved reconstruction."""
    config = manifest['configuration']
    execution = summary['execution_inputs']
    frozen = manifest['execution_defaults']
    if frozen['programme_interpolation'] != 'wait_plus_alpha_times_programme_minus_wait_v1':
        raise ValueError('unsupported frozen execution configuration contract')
    scenario = {**frozen['scenario'], 'seed': summary['seed'],
                'budget': execution['budget'], 'effect_strength': execution['effect']}
    wait = frozen['wait_matrix']
    treated = frozen['programme_matrix_alpha1']
    matrix = [[a+execution['effect']*(b-a) for a, b in zip(left, right)]
              for left, right in zip(wait, treated)]
    expected_policy = deepcopy(manifest['effective_policies'][summary['policy']])
    expected_policy['parameters']['treatment_matrix'] = matrix
    if summary['policy'] == 'FairRobust':
        expected_policy['parameters']['uncertainty_config']['radius'] = execution['radius']
        expected_policy['effective_settings']['uncertainty_radius'] = execution['radius']
    estimator = deepcopy(manifest['estimator'])
    estimator['programme_matrix'] = matrix
    quality = dict(frozen['note_quality'])
    qualities = frozen['matched_note_quality_by_student'] if summary['mode'] in ('d_matched', 'noisy_notes') else {}
    if execution['missingness'] is not None:
        quality['omission_probability'] = execution['missingness']
        qualities = {sid: quality for sid in frozen['matched_note_quality_by_student']}
    expected_model = {'wait_matrix': wait, 'treatment_matrix': matrix}
    expected_records = {'observation_model': frozen['observation_model'], 'estimator': estimator,
        'controller_model': expected_model, 'environment_wait_matrix': wait,
        'environment_programme_matrix': matrix, 'note_quality': quality,
        'note_quality_by_student': qualities,
        'max_notes_per_month': config['evaluation']['llm_notes_per_month'] if execution['sparse'] else None,
        'max_monitoring_notes_per_month': config['evaluation'].get('monitoring_notes_per_month', 1),
        'extraction_contract': config['evaluation'].get('extraction_contract', 'actionable_monitoring')}
    if (replay['scenario'] != scenario
            or digest(replay['policy']) != digest(expected_policy)
            or replay['information_mode'] != ('b_matched' if summary['mode'] == 'd_matched' else summary['mode'])
            or replay['extractor'] != summary['extractor_identity']
            or any(digest(replay.get(k)) != digest(v) for k, v in expected_records.items())):
        raise ValueError('effective execution configuration differs from saved episode')
    if digest({k: v for k, v in replay.items() if k not in ('episode_identity', 'replay_provenance')}) != replay['episode_identity']:
        raise ValueError('saved reconstruction configuration identity mismatch')


def episode_directories(version):
    return sorted(p for p in (Path(version)/'episodes').glob('*')
                  if not p.name.startswith('.'))


def trace_directory(version, summary):
    relative = Path(summary['trace_path'])
    if (relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 3
            or relative.parts[0] != 'episodes' or relative.name != 'trace.json.gz'):
        raise ValueError('invalid completed episode trace reference')
    return version/relative.parent


def completed_records(version, manifest):
    version = Path(version)
    records = []
    seen = set()
    for episode in episode_directories(version):
        if not (episode/'summary.json').exists():
            continue
        summary = read_record(episode/'summary.json')
        if summary.get('input_digest') != manifest['input_digest']:
            raise ValueError(f'incompatible experiment identity: {episode}')
        verify_directory(episode)
        if manifest['manifest_version'] == 4:
            cell = tuple(summary[k] for k in ('phase', 'setting', 'mode', 'policy', 'seed'))
            if cell in seen:
                raise ValueError('duplicate evaluation cell')
            seen.add(cell)
            validate_extractor_identity(summary.get('extractor_identity'))
            identity = read_record(episode/'execution.json')
            if any(summary.get(k) != value for k, value in identity.items()):
                raise ValueError('completed execution identity mismatch')
            execution = summary.get('execution_inputs', {})
            if (summary.get('validation') != {'scientific_and_resource_invariants': True}
                    or digest(execution) != summary.get('execution_key')
                    or any(execution.get(k) != summary.get(k) for k in
                        ('phase', 'policy', 'mode', 'seed', 'setting', 'input_digest', 'extractor_identity'))):
                raise ValueError('missing or inconsistent validated execution provenance')
            source = trace_directory(version, summary)
            verify_directory(source)
            replay = read_record(source/'replay/experiment_config.json')
            validate_execution_configuration(manifest, summary, replay)
            if (replay['experiment_identity'] != manifest['input_digest']
                    or replay['episode_identity'] != summary.get('episode_identity')):
                raise ValueError('completed episode reconstruction identity mismatch')
        records.append((episode/'summary.json', summary))
    return records


def contributing_episodes(version, records):
    return [{'path': path.parent.relative_to(version).as_posix(),
             'summary_identity': digest(summary), 'episode_identity': summary['episode_identity'],
             'seal_sha256': sha256((path.parent/'artifact_integrity.json').read_bytes()).hexdigest()}
            for path, summary in records]


def primary_completion(version, manifest, records):
    """Only exact primary cells count; every partial statistic stays exploratory."""
    config = manifest['configuration']
    design = manifest['primary_evaluation']
    if design != primary_design(config):
        raise ValueError('frozen primary design/configuration mismatch')
    expected = {(p, s) for p in design['policies'] for s in design['seeds']}
    actual, excluded, invalid, failed = set(), [], [], []
    seen = set()
    for path, row in records:
        try:
            if (type(row['seed']) is not int or not all(isinstance(row[k], str)
                    for k in ('phase', 'setting', 'mode', 'policy'))):
                raise ValueError('malformed primary cell')
            cell = tuple(row[k] for k in ('phase', 'setting', 'mode', 'policy', 'seed'))
            if cell in seen:
                raise ValueError('duplicate evaluation cell')
            seen.add(cell)
            key = row['policy'], row['seed']
            if (row['phase'], row['setting'], row['mode']) != (design['phase'], design['setting'], design['mode']) or key not in expected:
                excluded.append(path.parent.relative_to(version).as_posix())
                continue
            # The primary extraction route is frozen note-supported exact facts.
            wanted = execution_inputs(config, manifest['input_digest'], design['phase'],
                row['policy'], design['mode'], row['seed'], setting=design['setting'],
                extractor_identity=manifest['extractor_contract'])
            if row['execution_inputs'] != wanted:
                invalid.append({'policy': row['policy'], 'seed': row['seed'],
                    'reason': 'incompatible effective primary execution settings'})
                continue
            actual.add(key)
        except (KeyError, TypeError) as exc:
            raise ValueError('malformed primary cell provenance') from exc
    incomplete = []
    for episode in episode_directories(version):
        if (episode/'summary.json').exists():
            continue
        incomplete.append(episode.relative_to(version).as_posix())
        identity = read_record(episode/'execution.json') if (episode/'execution.json').exists() else {}
        key = identity.get('policy'), identity.get('seed')
        if ((identity.get('phase'), identity.get('setting'), identity.get('mode')) ==
                (design['phase'], design['setting'], design['mode']) and key in expected):
            failed.append({'policy': key[0], 'seed': key[1],
                'status': 'failed' if (episode/'failure.json').exists() else 'interrupted'})
    complete = bool(expected) and expected == actual and not invalid and not failed
    return {'input_digest': manifest['input_digest'], 'primary_design': design,
        'primary_complete': complete,
        'evaluation_status': 'COMPLETE' if complete else 'FAILED / INCOMPLETE' if failed or invalid else 'INCOMPLETE / EXPLORATORY',
        'expected_primary_episodes': len(expected), 'actual_primary_episodes': len(actual),
        'completed_primary_cells': [list(cell) for cell in sorted(actual)],
        'expected_paired_seeds': len(design['seeds']),
        'completed_paired_seeds': sum(all((p, s) in actual for p in design['policies']) for s in design['seeds']),
        'missing_primary_cells': [list(cell) for cell in sorted(expected-actual)],
        'failed_primary_cells': failed, 'invalid_primary_cells': invalid,
        'complete_episodes': len(records), 'incomplete_or_failed': incomplete,
        'excluded_episodes': excluded,
        'statistics_scope': 'full_frozen_primary_matrix' if complete else 'conditional_on_completed_subset',
        'contributing_episodes': contributing_episodes(version, records)}

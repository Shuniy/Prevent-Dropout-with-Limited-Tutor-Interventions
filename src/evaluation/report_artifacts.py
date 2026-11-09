"""Append-only, sealed aggregate/report snapshots linked to immutable episodes."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from .provenance import (artifact_hashes, digest, read_record, seal_directory,
    staged_artifacts, verify_directory, verify_manifest, write_exclusive)


def _sources(version, sources):
    for source in sources:
        relative = Path(source['path'])
        if relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 2 or relative.parts[0] != 'episodes':
            raise ValueError('invalid report episode reference')
        episode = version/relative
        verify_directory(episode)
        summary = read_record(episode/'summary.json')
        if (summary['input_digest'] != version.name
                or digest(summary) != source['summary_identity']
                or sha256((episode/'artifact_integrity.json').read_bytes()).hexdigest() != source['seal_sha256']
                or summary.get('episode_identity') != source['episode_identity']):
            raise ValueError('report contributing episode identity mismatch')
    if len({source['path'] for source in sources}) != len(sources):
        raise ValueError('duplicate report contributing episode')


def report_index(version):
    path = version/'report_generations.json'
    index = read_record(path) if path.exists() else []
    if not isinstance(index, list):
        raise ValueError('invalid report generation registry')
    previous = None
    seen = set()
    for entry in index:
        if (entry['previous'] != previous or entry['generation'] in seen
                or digest({k: v for k, v in entry.items() if k != 'entry_digest'}) != entry['entry_digest']):
            raise ValueError('broken report generation registry')
        seen.add(entry['generation'])
        previous = entry['entry_digest']
    return index


def verify_reports(version):
    """Check every registered generation, its exact file inventory and inputs."""
    version = Path(version)
    index = report_index(version)
    actual = {p.name for p in (version/'reports').glob('*') if not p.name.startswith('.')}
    if actual != {entry['generation'] for entry in index}:
        raise ValueError('missing or unexpected finalized report generation')
    for entry in index:
        generation = version/'reports'/entry['generation']
        verify_directory(generation)
        manifest = read_record(generation/'report_manifest.json')
        payload = {k: v for k, v in manifest.items() if k != 'report_identity'}
        if (manifest.get('report_contract_version') != 1 or manifest['input_digest'] != version.name
                or manifest['generation'] != generation.name or digest(payload) != manifest['report_identity']
                or manifest['report_identity'] != entry['report_identity']):
            raise ValueError('report manifest identity mismatch')
        files = artifact_hashes(generation)
        files.pop('report_manifest.json')
        if files != manifest['artifacts']:
            raise ValueError('report artifact digest mismatch')
        status = read_record(generation/'aggregation_status.json')
        if status['contributing_episodes'] != manifest['contributing_episodes'] or status['input_digest'] != version.name:
            raise ValueError('report/aggregate source identity mismatch')
        _sources(version, manifest['contributing_episodes'])
        required = {'episode_results.csv', 'primary_policy_comparison.csv', 'all_policy_comparisons.csv'}
        if manifest['kind'] == 'report':
            required.add('research_results.md')
        elif manifest['kind'] != 'aggregate':
            raise ValueError('unknown finalized report kind')
        if not required <= files.keys():
            raise ValueError('incomplete finalized report')
    pointer = version/'current_report.json'
    if index:
        if read_record(pointer) != {k: index[-1][k] for k in ('generation', 'report_identity')}:
            raise ValueError('invalid current report pointer')
        current = version/'.current_report'
        if not current.is_symlink() or current.readlink().as_posix() != 'reports/'+index[-1]['generation']:
            raise ValueError('invalid current report alias')
        generation = version/'reports'/index[-1]['generation']
        auxiliary = {'snapshot_assignment_comparison.csv', 'extraction_snapshot_comparison.csv',
                     'live_runtime.json', 'development_gate.json', 'extraction'}
        for item in generation.iterdir():
            if item.name in {'attempt.json', 'artifact_integrity.json', 'report_manifest.json'} | auxiliary:
                continue
            alias = version/item.name
            if not alias.is_symlink() or alias.readlink() != Path('.current_report')/item.name:
                raise ValueError(f'substituted finalized artifact alias: {item.name}')
    elif pointer.exists():
        raise ValueError('report pointer without finalized generation')
    return len(index)


@contextmanager
def report_generation(version, kind):
    version = Path(version)
    manifest = verify_manifest(version)
    if manifest['manifest_version'] != 4:
        raise ValueError('historical experiment has no finalized report contract; create an amended version')
    # Serialize registry and current-alias updates, in addition to per-output locks.
    lock = version/'.report_lock'
    lock.mkdir(exist_ok=False)
    try:
        verify_reports(version)
        generation = uuid4().hex
        destination = version/'reports'/generation
        with staged_artifacts(destination, identity={'kind': kind, 'input_digest': manifest['input_digest']}) as stage:
            yield stage
            status = read_record(stage/'aggregation_status.json')
            sources = status['contributing_episodes']
            _sources(version, sources)
            auxiliary = {'snapshot_assignment_comparison.csv', 'extraction_snapshot_comparison.csv',
                         'live_runtime.json', 'development_gate.json', 'extraction'}
            for item in stage.iterdir():
                if item.name == 'attempt.json' or item.name in auxiliary:
                    continue
                target = version/item.name
                if target.is_symlink():
                    if target.readlink() != Path('.current_report')/item.name:
                        raise ValueError(f'substituted finalized artifact alias: {item.name}')
                elif target.exists():
                    raise ValueError(f'unmanaged report artifact exists: {target}')
            payload = {'report_contract_version': 1, 'generation': generation, 'kind': kind,
                'input_digest': manifest['input_digest'], 'contributing_episodes': sources,
                'primary_complete': status['primary_complete'],
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'artifacts': artifact_hashes(stage)}
            write_exclusive(stage/'report_manifest.json', {**payload, 'report_identity': digest(payload)})
            seal_directory(stage)
            verify_directory(stage)
        index = report_index(version)
        entry = {'generation': generation, 'report_identity': digest(payload),
                 'previous': index[-1]['entry_digest'] if index else None}
        entry['entry_digest'] = digest(entry)
        # A crash between publication and registration fails verification rather
        # than silently hiding an unregistered finalized generation.
        temporary = version/('report_generations.'+uuid4().hex+'.tmp')
        write_exclusive(temporary, index+[entry])
        temporary.replace(version/'report_generations.json')
        pointer = version/('current_report.'+uuid4().hex+'.tmp')
        write_exclusive(pointer, {k: entry[k] for k in ('generation', 'report_identity')})
        pointer.replace(version/'current_report.json')
        alias = version/('.current_report.'+uuid4().hex)
        alias.symlink_to(Path('reports')/generation, target_is_directory=True)
        alias.replace(version/'.current_report')
        # Convenience aliases always resolve into sealed generations. Producers
        # write staging paths, never through these links into finalized bytes.
        for item in destination.iterdir():
            if item.name in ('attempt.json', 'artifact_integrity.json', 'report_manifest.json'):
                continue
            target = version/item.name
            if target.is_symlink():
                continue
            if target.exists():
                # Optional diagnostic input files remain source inputs; their
                # captured bytes, rather than these mutable originals, are sealed.
                if item.name in ('snapshot_assignment_comparison.csv', 'extraction_snapshot_comparison.csv',
                                 'live_runtime.json', 'development_gate.json', 'extraction'):
                    continue
                raise ValueError(f'unmanaged report artifact exists: {target}')
            target.symlink_to(Path('.current_report')/item.name, target_is_directory=item.is_dir())
    finally:
        lock.rmdir()

"""Filesystem experiment identities and independently verifiable retained records.

Hashes detect accidental changes, not hostile rewriting of both data and hashes.
Only explicit metadata is recorded; environment variables and credentials are not.
"""
from hashlib import sha256
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess
import sys
from uuid import uuid4

from ..utils.constants import PROJECT_ROOT


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def runtime_identity():
    if sys.version_info[:2] not in ((3, 12), (3, 13)):
        raise ValueError('experiment provenance requires supported Python 3.12 or 3.13')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=PROJECT_ROOT, stderr=subprocess.PIPE)
    # Scope dirty identity to execution inputs, avoiding output/report recursion.
    paths = ('src', 'scripts', 'configs', 'data', 'requirements.txt', 'pyproject.toml',
             'docs/research_evaluation_protocol.md')
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
        'executable': sys.executable, 'platform': platform.platform(),
        'dependencies': sorted([d.metadata['Name'], d.version] for d in distributions()),
        'git_revision': git('rev-parse', 'HEAD').decode().strip(),
        'dirty_execution_paths': git('status', '--porcelain', '--', *paths).decode().splitlines(),
        'tracked_execution_diff_sha256': sha256(git('diff', '--binary', 'HEAD', '--', *paths)).hexdigest()}


def source_fingerprints():
    paths = [*(PROJECT_ROOT/'src').rglob('*.py'), *(PROJECT_ROOT/'scripts').rglob('*.py'),
             *(PROJECT_ROOT/'configs').rglob('*.toml'), PROJECT_ROOT/'requirements.txt',
             PROJECT_ROOT/'pyproject.toml', PROJECT_ROOT/'.python-version']
    return {str(p.relative_to(PROJECT_ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def extractor_identity(extractor):
    from ..intervention import observation_extractor, ollama_client
    from ..intervention.observation_extractor import SYSTEM_PROMPT, EXTRACTION_SCHEMA
    client = getattr(extractor, 'client', None)
    config = getattr(extractor, 'configuration', {})
    config = config if isinstance(config, dict) else {}
    metadata = config.get('model_metadata', {})
    metadata = metadata if isinstance(metadata, dict) else {}
    # Only execution fields of the supported client are serialized, never an
    # arbitrary client/configuration object, metadata response or environment.
    primitive = lambda v: v if type(v) in (str, int, float, bool, type(None)) else None
    known_client = type(client) is ollama_client.OllamaClient
    execution = client.execution_configuration if known_client else {}
    weights = primitive(execution.get('model_digest') or metadata.get('digest'))
    adapter_module = sys.modules.get(type(extractor).__module__)
    adapter_file = getattr(adapter_module, '__file__', None)
    client_module = sys.modules.get(type(client).__module__)
    client_file = getattr(client_module, '__file__', None)
    identity = {'identity_version': 2,
        'adapter': type(extractor).__module__ + '.' + type(extractor).__qualname__,
        'backend': execution.get('backend', 'recorded_outcomes' if isinstance(extractor,
            observation_extractor.RecordedOutcomeExtractor) else 'fixture_exact_grammar' if extractor is None or
            isinstance(extractor, observation_extractor.FixtureObservationExtractor) else 'unsupported_adapter'),
        'configuration_status': 'complete' if known_client or extractor is None or isinstance(extractor,
            (observation_extractor.FixtureObservationExtractor, observation_extractor.RecordedOutcomeExtractor)) else 'partial_unsupported_adapter',
        'model': primitive(execution.get('model')), 'model_digest': weights,
        'client_adapter': type(client).__module__ + '.' + type(client).__qualname__ if client is not None else None,
        'client_adapter_code_sha256': sha256(Path(client_file).read_bytes()).hexdigest() if client_file else None,
        'model_identity_limitation': 'mutable_tag_without_weight_digest' if client is not None and weights is None
            else 'not_applicable' if client is None else 'digest_available_not_independently_attested',
        'endpoint_sha256': execution.get('endpoint_sha256'),
        'num_ctx': primitive(execution.get('num_ctx')),
        'timeout_seconds': primitive(execution.get('timeout_seconds')),
        'temperature': primitive(execution.get('temperature')), 'think': execution.get('think'), 'stream': execution.get('stream'),
        'system_prompt_sha256': sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        'schema_sha256': digest(EXTRACTION_SCHEMA), 'evidence_contract': 3,
        'validation_code_sha256': sha256(Path(observation_extractor.__file__).read_bytes()).hexdigest(),
        'client_code_sha256': sha256(Path(ollama_client.__file__).read_bytes()).hexdigest(),
        'adapter_code_sha256': sha256(Path(adapter_file).read_bytes()).hexdigest() if adapter_file else None}
    if isinstance(extractor, observation_extractor.FixtureObservationExtractor):
        identity['fixture_payload_sha256'] = digest(extractor.fixtures)
    if isinstance(extractor, observation_extractor.RecordedOutcomeExtractor):
        identity['recorded_outcomes_sha256'] = digest(list(extractor.outcomes.values()))
    return identity


def validate_extractor_identity(identity):
    required = {'identity_version', 'adapter', 'backend', 'endpoint_sha256', 'model', 'model_digest',
        'model_identity_limitation', 'configuration_status', 'num_ctx', 'timeout_seconds', 'temperature',
        'think', 'stream', 'system_prompt_sha256', 'schema_sha256', 'validation_code_sha256',
        'client_code_sha256', 'adapter_code_sha256', 'evidence_contract'}
    required |= {'client_adapter', 'client_adapter_code_sha256'}
    if (not isinstance(identity, dict) or not required <= identity.keys()
            or identity['identity_version'] != 2 or identity['configuration_status'] != 'complete'):
        raise ValueError('historical or partially specified extractor execution identity')
    return identity


def write_exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def read_record(path):
    """Reject ambiguous JSON objects, including duplicate inventory entries."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON field: {key}')
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'missing or corrupted provenance: {path}') from exc


def artifact_hashes(path, filename='artifact_integrity.json'):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('sealed directory cannot be a symbolic link')
    hashes = {}
    for item in sorted(path.rglob('*')):
        if item.is_symlink():
            raise ValueError(f'symbolic link in sealed inventory: {item}')
        if item.is_file() and item != path/filename:
            hashes[item.relative_to(path).as_posix()] = sha256(item.read_bytes()).hexdigest()
    return hashes


def seal_directory(path, filename='artifact_integrity.json'):
    path = Path(path)
    write_exclusive(path/filename, artifact_hashes(path, filename))


def verify_directory(path, filename='artifact_integrity.json'):
    path = Path(path)
    try:
        if (path/filename).is_symlink():
            raise ValueError('symbolic link integrity seal')
        hashes = read_record(path/filename)
        actual = artifact_hashes(path, filename)
        if not isinstance(hashes, dict) or not hashes or set(hashes) != set(actual):
            raise ValueError('incomplete artifact inventory')
        for name, expected in hashes.items():
            if actual[name] != expected:
                raise ValueError(f'corrupted artifact: {name}')
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f'missing or corrupted provenance: {path}') from exc
    return hashes


def publish_directory(staging, destination):
    """One-filesystem publication; never replace even an incomplete destination."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'artifact destination already exists: {destination}')
    staging.rename(destination)


@contextmanager
def staged_artifacts(destination, *, identity=None, failure_marker=False):
    """Keep all writes private until the caller validates and seals the inventory.

    A killed writer leaves an explicit lock/staging area. Failed attempts are not
    retried under the same research identity; replay diagnostics are kept outside
    its requested destination. Locks serialize cooperating filesystem writers.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    locks = destination.parent/'.locks'
    locks.mkdir(exist_ok=True)
    lock = locks/destination.name
    lock.mkdir(exist_ok=False)
    stage = None
    try:
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f'existing artifact destination; preserve it and use a new identity: {destination}')
        stage = destination.parent/'.staging'/uuid4().hex
        stage.mkdir(parents=True)
        write_exclusive(stage/'attempt.json', {'identity': identity, 'destination': destination.name,
            'started_at_utc': datetime.now(timezone.utc).isoformat()})
        yield stage
        # The attempt record belongs to the sealed inventory too.
        publish_directory(stage, destination)
    except BaseException as exc:
        if stage is not None and stage.exists():
            failure = {'status': 'failed', 'identity': identity, 'destination': destination.name,
                'error_type': type(exc).__name__, 'error': str(exc),
                'failed_at_utc': datetime.now(timezone.utc).isoformat()}
            # A late serialization/sealing/publication error must not retain a
            # successful summary marker, even in the quarantined attempt.
            for name in ('summary.json', 'replay_result.json', 'artifact_integrity.json', 'record_integrity.json'):
                if (stage/name).exists():
                    (stage/name).rename(stage/(name+'.unpublished'))
            failed = destination.parent/'.failed'/stage.name
            failed.parent.mkdir(exist_ok=True)
            try:
                write_exclusive(stage/'failure.json', failure)
                stage.rename(failed)
                if failure_marker and not destination.exists():
                    destination.mkdir()
                    write_exclusive(destination/'execution.json', identity)
                    write_exclusive(destination/'failure.json', {**failure,
                        'diagnostic_path': str(failed.relative_to(destination.parent))})
            except OSError as diagnostic_error:
                exc.add_note(f'Failure diagnostics remain at {stage}: {diagnostic_error}')
        raise
    finally:
        lock.rmdir()


def active_directory(output):
    output = Path(output)
    pointer = output/'current_version.json'
    if not pointer.exists():
        if (output/'versions').exists():
            raise ValueError('missing active experiment identity pointer')
        return output
    identity = json.loads(pointer.read_text())['input_digest']
    if len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
        raise ValueError('invalid experiment identity pointer')
    return output/'versions'/identity


def verify_manifest(directory):
    directory = Path(directory)
    try:
        manifest = read_record(directory/'configuration_manifest.json')
        if manifest.get('manifest_version') not in (3, 4):
            raise ValueError('historical manifest lacks exact provenance; use a new experiment directory')
        payload = {k: v for k, v in manifest.items() if k not in ('input_digest', 'frozen_at_utc')}
        if digest(payload) != manifest['input_digest']:
            raise ValueError('corrupted manifest identity')
        protocol = (directory/'research_evaluation_protocol_frozen.md').read_text()
        if protocol != manifest['protocol_text']:
            raise ValueError('corrupted frozen protocol')
        record = read_record(directory/'protocol.json')
        if record != {'protocol_text': protocol, 'configuration': manifest['configuration'],
                      'protocol_sha256': sha256(protocol.encode()).hexdigest()}:
            raise ValueError('corrupted protocol metadata')
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError('missing or corrupted immutable manifest provenance') from exc
    return manifest


def verify_versions(output):
    """Verify retained identities without requiring the current checkout to match."""
    output = Path(output)
    versions = sorted(p/'configuration_manifest.json' for p in (output/'versions').glob('*') if p.is_dir())
    if not versions:
        raise ValueError('no immutable experiment versions found')
    records = {p.parent.name: verify_manifest(p.parent) for p in versions}
    verified_reports = 0
    historical = []
    incomplete_episodes = []
    unpublished_attempts = []
    for identity, record in records.items():
        if record['input_digest'] != identity:
            raise ValueError('version directory identity mismatch')
        visited = {identity}
        parent = record['predecessor']
        while parent is not None:
            if parent not in records or parent in visited:
                raise ValueError('broken predecessor chain')
            visited.add(parent)
            parent = records[parent]['predecessor']
        version = output/'versions'/identity
        from .research_records import completed_records, episode_directories
        completed_records(version, record)
        incomplete_episodes.extend(str(p.relative_to(output)) for p in episode_directories(version)
                                   if not (p/'summary.json').exists())
        unpublished_attempts.extend(str(p.relative_to(output)) for area in ('episodes', 'reports')
            for p in (version/area/'.staging').glob('*'))
        if record['manifest_version'] == 3:
            historical.append(identity)
        else:
            from .report_artifacts import verify_reports
            verified_reports += verify_reports(version)
    if active_directory(output).name not in records:
        raise ValueError('active version is missing')
    # Compatibility copies are the first immutable version, never the pointer.
    first = verify_manifest(output)
    if records.get(first['input_digest']) != first or first['predecessor'] is not None:
        raise ValueError('original manifest copy differs from retained first version')
    return {'status': 'historical_partial' if historical else 'verified',
            'fully_verified': not historical,
            'verification_scope': 'immutable manifests/protocols, completed episodes, all finalized report generations',
            'historical_unverified_derived_artifacts': historical,
            'incomplete_episodes': incomplete_episodes,
            'unpublished_attempts_excluded_from_completed_scope': unpublished_attempts,
            'verified_report_generations': verified_reports,
            'verified_versions': len(records), 'identities': sorted(records),
            'active_identity': active_directory(output).name}

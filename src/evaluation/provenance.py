"""Filesystem experiment identities and independently verifiable retained records.

Hashes detect accidental changes, not hostile rewriting of both data and hashes.
Only explicit metadata is recorded; environment variables and credentials are not.
"""
from hashlib import sha256
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess
import sys

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
    from ..intervention.observation_extractor import SYSTEM_PROMPT, EXTRACTION_SCHEMA
    client = getattr(extractor, 'client', None)
    config = getattr(extractor, 'configuration', {})
    config = config if isinstance(config, dict) else {}
    metadata = config.get('model_metadata', {})
    # Allowlist fields, never serialize an arbitrary client/configuration object.
    primitive = lambda v: v if type(v) in (str, int, float, bool, type(None)) else None
    return {'adapter': type(extractor).__module__ + '.' + type(extractor).__qualname__,
        'model': primitive(getattr(client, 'model', None)),
        'model_digest': primitive(metadata.get('digest')),
        'num_ctx': primitive(getattr(client, 'num_ctx', None)),
        'timeout_seconds': primitive(getattr(client, 'timeout', None)),
        'temperature': 0, 'think': False, 'stream': False,
        'system_prompt_sha256': sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        'schema_sha256': digest(EXTRACTION_SCHEMA), 'evidence_contract': 3}


def write_exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def seal_directory(path, filename='artifact_integrity.json'):
    path = Path(path)
    hashes = {str(p.relative_to(path)): sha256(p.read_bytes()).hexdigest()
              for p in sorted(path.rglob('*')) if p.is_file() and p.name != filename}
    write_exclusive(path/filename, hashes)


def verify_directory(path, filename='artifact_integrity.json'):
    path = Path(path)
    try:
        hashes = json.loads((path/filename).read_text())
        actual = {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p.name != filename}
        if set(hashes) != actual:
            raise ValueError('incomplete artifact inventory')
        for name, expected in hashes.items():
            if sha256((path/name).read_bytes()).hexdigest() != expected:
                raise ValueError(f'corrupted artifact: {name}')
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f'missing or corrupted provenance: {path}') from exc
    return hashes


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
        manifest = json.loads((directory/'configuration_manifest.json').read_text())
        if manifest.get('manifest_version') != 3:
            raise ValueError('historical manifest lacks exact provenance; use a new experiment directory')
        payload = {k: v for k, v in manifest.items() if k not in ('input_digest', 'frozen_at_utc')}
        if digest(payload) != manifest['input_digest']:
            raise ValueError('corrupted manifest identity')
        protocol = (directory/'research_evaluation_protocol_frozen.md').read_text()
        if protocol != manifest['protocol_text']:
            raise ValueError('corrupted frozen protocol')
        record = json.loads((directory/'protocol.json').read_text())
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
        for episode in (output/'versions'/identity/'episodes').glob('*'):
            if (episode/'summary.json').exists():
                verify_directory(episode)
                summary = json.loads((episode/'summary.json').read_text())
                if summary['input_digest'] != identity:
                    raise ValueError('incompatible retained episode')
    if active_directory(output).name not in records:
        raise ValueError('active version is missing')
    # Compatibility copies are the first immutable version, never the pointer.
    first = verify_manifest(output)
    if records.get(first['input_digest']) != first or first['predecessor'] is not None:
        raise ValueError('original manifest copy differs from retained first version')
    return {'verified_versions': len(records), 'identities': sorted(records),
            'active_identity': active_directory(output).name}

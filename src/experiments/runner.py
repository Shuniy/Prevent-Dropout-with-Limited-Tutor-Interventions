"""Notebook-friendly orchestration; simulation transitions are a future stage."""
from pathlib import Path
import tomllib

import pandas as pd

from ..data.access import EnvironmentStore, PolicyStore
from ..data.dataset import DATA_DIR, population_table

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / 'configs/default.toml'


def population_summary(directory=DATA_DIR):
    """Return split sizes and distinct anchor counts as a DataFrame."""
    rows = []
    for split in ('train', 'validation', 'test'):
        students = population_table(split, directory=directory)
        rows.append({'split': split, 'students': len(students),
                     'source_anchors': students['source_anchor_student_id'].nunique()})
    return pd.DataFrame(rows).set_index('split')


def run_simulation(config_path=DEFAULT_CONFIG, *, dry_run=False):
    """Validate reset inputs, or refuse an unimplemented full episode.

    Relative data paths resolve against the configuration file. A dry run returns
    aggregate readiness information only, never hidden environment records.
    """
    config_path = Path(config_path).resolve()
    with config_path.open('rb') as stream:
        config = tomllib.load(stream)
    if set(config) != {'data', 'simulation'}:
        raise ValueError('Config requires exactly data and simulation sections')
    if set(config['data']) != {'directory'} or set(config['simulation']) != {'split'}:
        raise ValueError('Config requires data.directory and simulation.split only')
    directory = config['data']['directory']
    split = config['simulation']['split']
    if not isinstance(directory, str) or not directory.strip():
        raise ValueError('data.directory must be a nonempty path')
    if split not in ('train', 'validation', 'test'):
        raise ValueError('simulation.split must be train, validation or test')
    directory = (config_path.parent / directory).resolve()
    states = EnvironmentStore(directory).load_fixture(split)
    observations = PolicyStore(directory).load_reset(split)
    if {s.student_id for s in states} != {s.student_id for s in observations}:
        raise ValueError('Environment and policy reset IDs differ')
    if not dry_run:
        raise NotImplementedError(
            'Simulation transitions are not implemented. Use --dry-run to validate reset inputs.'
        )
    return pd.DataFrame([{'status': 'reset_validated', 'split': split,
                          'students': len(states), 'steps_executed': 0}])

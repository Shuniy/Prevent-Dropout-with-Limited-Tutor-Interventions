"""Read the existing generated CSVs directly; never create or rewrite datasets."""
import csv
import pandas as pd
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints, get_origin, Literal

from .contracts import (StudentContext, Lineage, VerifiedContext, AuditGroups,
                        UnknownFields, EnvironmentState)

DATA_DIR = Path(__file__).resolve().parents[2] / 'data'
TABLE_PATHS = {
    'student_dataset': 'processed/students/student_dataset.csv',
    'split_manifest': 'processed/splits/split_manifest.csv',
    'subject_records_reference': 'external/subject_records_reference.csv',
    'student_outcomes_reference': 'external/student_outcomes_reference.csv',
    'synthetic_student_population': 'synthetic/populations/synthetic_student_population.csv',
    'simulator_hidden_truth': 'synthetic/simulator_states/simulator_hidden_truth.csv',
}
TABLES = {'student_dataset', 'synthetic_student_population', 'split_manifest',
          'subject_records_reference', 'student_outcomes_reference', 'simulator_hidden_truth'}


def read_table(table, directory=DATA_DIR):
    """Return a DataFrame of source strings; preserve blanks and identifiers.

    Convert specific numeric columns with pd.to_numeric in analysis code.
    This raw research table is not an allowlisted policy feature table.
    """
    if table not in TABLES:
        raise ValueError('Unknown dataset table')
    directory = Path(directory)
    path = directory / TABLE_PATHS[table]
    # Keep supporting callers supplying a flat directory of CSVs.
    if not path.exists():
        path = directory / f'{table}.csv'
    with path.open(newline='', encoding='utf-8-sig') as stream:
        # Check structure first: pandas otherwise renames duplicate headers and
        # fills short rows. csv handles quoted commas and multiline cells.
        reader = csv.reader(stream)
        columns = next(reader, [])
        if not columns or any(not name for name in columns) or len(columns) != len(set(columns)):
            raise ValueError('Missing or duplicate CSV columns')
        for row in reader:
            if row and len(row) != len(columns):
                raise ValueError('Malformed CSV row')
        stream.seek(0)
        data = pd.read_csv(stream, dtype=str, keep_default_na=False)
    key = 'record_id' if table == 'subject_records_reference' else 'student_id'
    if key not in data or data[key].eq('').any() or data[key].duplicated().any():
        raise ValueError('Missing or duplicate record ID')
    return data


def read_rows(table, directory=DATA_DIR):
    """Compatibility adapter for the validated records; no JSON conversion."""
    return read_table(table, directory).to_dict(orient='records')


def binary(value):
    if value not in ('0', '1'):
        raise ValueError('Expected 0 or 1')
    return value == '1'


def integer(value):
    number = float(value)
    if not number.is_integer():
        raise ValueError('Expected an integer')
    return int(number)


def _record(record_type, row):
    values = {}
    for name, hint in get_type_hints(record_type).items():
        value = row[name]
        if value == '':
            values[name] = None
        elif hint is bool:
            values[name] = binary(value)
        elif hint is str or get_origin(hint) is Literal:
            values[name] = value
        else:
            values[name] = integer(value)
    return record_type(**values)


def context_record(row):
    if any(row.get(f.name, '') != '' for f in fields(UnknownFields)):
        raise ValueError('Unknown income/dropout fields must remain blank')
    lineage = Lineage(row['student_id'], row.get('source_anchor_student_id', row['student_id']),
        row['source_dataset'], integer(row['source_row']), row['linkage_group_id'],
        row['split'], row['anchor_subject'], row['link_status'], row['record_provenance'])
    return StudentContext(lineage, row['population'], _record(VerifiedContext, row),
                          _record(AuditGroups, row), UnknownFields(None, None, None, None, None))


def population_table(split, cohort='fixture', directory=DATA_DIR):
    """Select a split/cohort using readable pandas filters; return a copy."""
    if split not in ('train', 'validation', 'test'):
        raise ValueError('Unknown split')
    if cohort not in ('primary', 'sensitivity', 'fixture'):
        raise ValueError('Unknown cohort')
    table = 'synthetic_student_population' if cohort == 'fixture' else 'student_dataset'
    data = read_table(table, directory)
    if not data['split'].isin(['train', 'validation', 'test']).all():
        raise ValueError('Invalid dataset split')
    if data.groupby('linkage_group_id')['split'].nunique().gt(1).any():
        raise ValueError('Linkage group crosses splits')
    selected = data['split'] == split
    if cohort == 'primary':
        selected = selected & (data['anchor_subject'] == 'portuguese')
    return data.loc[selected].copy()


def population_rows(split, cohort='fixture', directory=DATA_DIR):
    """Bridge a selected DataFrame to existing consumer records."""
    return population_table(split, cohort, directory).to_dict(orient='records')


def environment_record(row, hidden):
    return EnvironmentState(row['student_id'], 0, binary(row['enrolled_initial_assumed']),
        float(row['initial_attendance_fraction_assumed']), float(row['initial_engagement_assumed']),
        float(row['learning_gap_initial_assumed']), float(hidden['response_tendency_assumed']),
        binary(hidden['financial_barrier_latent_assumed']), (), integer(row['weeks_since_offer']),
        integer(row['support_sessions_completed']))

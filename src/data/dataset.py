"""Read the existing generated CSVs directly; never create or rewrite datasets."""
import csv
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints, get_origin, Literal

from .contracts import (StudentContext, Lineage, VerifiedContext, AuditGroups,
                        UnknownFields, EnvironmentState)

DATA_DIR = Path(__file__).resolve().parents[2] / 'data/generated'
TABLES = {'student_dataset', 'synthetic_student_population', 'split_manifest',
          'subject_records_reference', 'student_outcomes_reference', 'simulator_hidden_truth'}


def read_rows(table, directory=DATA_DIR):
    if table not in TABLES:
        raise ValueError('Unknown dataset table')
    with (Path(directory) / f'{table}.csv').open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('Missing or duplicate CSV columns')
        rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError('Malformed CSV row')
    key = 'record_id' if table == 'subject_records_reference' else 'student_id'
    if any(not row.get(key) for row in rows) or len({row[key] for row in rows}) != len(rows):
        raise ValueError('Missing or duplicate record ID')
    return rows


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


def population_rows(split, cohort='fixture', directory=DATA_DIR):
    if split not in ('train', 'validation', 'test'):
        raise ValueError('Unknown split')
    if cohort not in ('primary', 'sensitivity', 'fixture'):
        raise ValueError('Unknown cohort')
    table = 'synthetic_student_population' if cohort == 'fixture' else 'student_dataset'
    rows = read_rows(table, directory)
    groups = {}
    for row in rows:
        if row['split'] not in ('train', 'validation', 'test'):
            raise ValueError('Invalid dataset split')
        group = row['linkage_group_id']
        if groups.setdefault(group, row['split']) != row['split']:
            raise ValueError('Linkage group crosses splits')
    return [row for row in rows if row['split'] == split and
            (cohort != 'primary' or row['anchor_subject'] == 'portuguese')]


def environment_record(row, hidden):
    return EnvironmentState(row['student_id'], 0, binary(row['enrolled_initial_assumed']),
        float(row['initial_attendance_fraction_assumed']), float(row['initial_engagement_assumed']),
        float(row['learning_gap_initial_assumed']), float(hidden['response_tendency_assumed']),
        binary(hidden['financial_barrier_latent_assumed']), (), integer(row['weeks_since_offer']),
        integer(row['support_sessions_completed']))

"""Separate consumer interfaces; ordinary callers receive detached allowlisted facts.

This is an API/data-flow boundary, not an OS sandbox against hostile Python code.
PolicyStore reads the population CSV only; it projects allowed facts into records.
"""
from pathlib import Path
from types import MappingProxyType

from .dataset import DATA_DIR, read_rows, population_rows, context_record, environment_record

from .contracts import (StudentContext, EnvironmentState, Observation, PolicyReset,
                        RESET_FIELDS, DYNAMIC_FIELDS, UNITS)
DEFAULT_FEATURES = ('anchor_grade1_0_20', 'past_failures_count', 'study_time_category')


def reset_observations(context, selected=DEFAULT_FEATURES):
    """Project context only. This function has no environment/hidden-table argument."""
    if type(context) is not StudentContext:
        raise TypeError('StudentContext required')
    if not set(selected) <= set(RESET_FIELDS) or len(selected) != len(set(selected)):
        raise ValueError('Reset field not allowlisted')
    sid = context.lineage.student_id
    facts = [Observation(f'{sid}:reset:{name}', sid, name, getattr(context.context,name),
        None, 0, 'observed', 'uci_school_hypothetical_first_period_reset',
        'unknown_source_time', UNITS[name]) for name in selected]
    for name in ('attendance','engagement','learning_need','enrolled'):
        facts.append(Observation(f'{sid}:reset:{name}',sid,name,None,None,0,'withheld',
            'observation_mechanism_required','withheld',UNITS[name]))
    return PolicyReset(sid,tuple(facts))


def model_features(record, selected=DEFAULT_FEATURES):
    """Explicit feature extraction; join identifiers and audit categories never score."""
    if type(record) is not PolicyReset or not set(selected) <= set(RESET_FIELDS) or len(selected) != len(set(selected)):
        raise ValueError('Invalid model feature request')
    known = {o.field:o.value for o in record.observations if o.status in ('observed','reported')}
    if not set(selected) <= set(known):
        raise ValueError('Requested feature not observed')
    return MappingProxyType({name:known[name] for name in selected})


def authorized_measurement(student_id, name, value, source_time, available_at, source, observation_id):
    """Structured adapter for explicitly supplied measurements, not latent-state copying.

    The future environment's observation mechanism owns authorization/noise/missingness.
    Data preparation does not manufacture measurements from the fixture.
    """
    if name not in DYNAMIC_FIELDS:
        raise ValueError('Unsupported dynamic observable')
    return Observation(observation_id,student_id,name,value,source_time,available_at,
        'observed',source,'none',UNITS[name])


class PolicyStore:
    """Read population facts only; hidden truth and outcomes are never opened."""
    def __init__(self, directory=DATA_DIR):
        self.directory = Path(directory)

    def load_reset(self, split, cohort='fixture'):
        return tuple(reset_observations(context_record(row))
                     for row in population_rows(split, cohort, self.directory))


class ContextStore:
    """Full context for initialization and auditing."""
    def __init__(self, directory=DATA_DIR):
        self.directory = Path(directory)

    def load(self, split, cohort='fixture'):
        return tuple(context_record(row) for row in population_rows(split, cohort, self.directory))


class EnvironmentStore:
    def __init__(self, directory=DATA_DIR):
        self.directory = Path(directory)

    def load_fixture(self, split):
        population = read_rows('synthetic_student_population', self.directory)
        hidden = {row['student_id']: row for row in read_rows('simulator_hidden_truth', self.directory)}
        if {row['student_id'] for row in population} != set(hidden):
            raise ValueError('Population and hidden truth IDs differ')
        return tuple(environment_record(row, hidden[row['student_id']])
                     for row in population_rows(split, 'fixture', self.directory))


class EvaluatorStore:
    def __init__(self, directory=DATA_DIR):
        self.directory = Path(directory)

    def load_subject_references(self):
        return tuple(read_rows('subject_records_reference', self.directory))

    def load_historical_outcomes(self):
        return tuple(read_rows('student_outcomes_reference', self.directory))

    def load_static_fixture_diagnostics(self):
        return tuple(read_rows('simulator_hidden_truth', self.directory))

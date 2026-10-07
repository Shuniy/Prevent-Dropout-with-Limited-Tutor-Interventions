"""Separate consumer interfaces; ordinary callers receive detached allowlisted facts.

This is an API/data-flow boundary, not an OS sandbox against hostile Python code.
PolicyStore never opens context, evaluator or environment files, even for checksums.
"""
import json
from pathlib import Path
from types import MappingProxyType

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
    Stage 1 does not manufacture measurements from the fixture.
    """
    if name not in DYNAMIC_FIELDS:
        raise ValueError('Unsupported dynamic observable')
    return Observation(observation_id,student_id,name,value,source_time,available_at,
        'observed',source,'none',UNITS[name])


def _read(root, role, filename):
    root=Path(root).resolve(strict=True)
    target=root/'data'/role/filename
    if any(p.is_symlink() for p in (root/'data',root/'data'/role,target)):
        raise ValueError('Symlink consumer data is forbidden')
    if not target.resolve().is_relative_to(root):
        raise ValueError('Consumer data escaped its root')
    with target.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _split(split):
    if split not in ('train','validation','test'):
        raise ValueError('Unknown source split')
    return split


def _cohort(cohort):
    if cohort not in ('primary','sensitivity','fixture'):
        raise ValueError('Unknown school cohort')
    return cohort


class PolicyStore:
    __slots__ = ('_root',)

    def __init__(self, root):
        self._root=Path(root)

    def load_reset(self, split, cohort='primary'):
        rows=_read(self._root,'policy',f'{_cohort(cohort)}_{_split(split)}.jsonl')
        result=tuple(PolicyReset.from_dict(row) for row in rows)
        if len({r.student_id for r in result}) != len(result):
            raise ValueError('Duplicate policy IDs')
        return result


class ContextStore:
    """Initializer/audit access only; never hand this object to ordinary policies."""
    def __init__(self, root):
        self._root=Path(root)

    def load(self, split, cohort='primary'):
        rows=_read(self._root,'context',f'{_cohort(cohort)}_{_split(split)}.jsonl')
        result=tuple(StudentContext.from_dict(r) for r in rows)
        if any(c.lineage.split != split for c in result):
            raise ValueError('Context split mismatch')
        return result


class EnvironmentStore:
    def __init__(self, root):
        self._root=Path(root)

    def load_fixture(self, split):
        return tuple(EnvironmentState.from_dict(r) for r in
                     _read(self._root,'environment',f'fixture_{_split(split)}.jsonl'))


class EvaluatorStore:
    def __init__(self, root):
        self._root=Path(root)

    def load_subject_references(self):
        return tuple(_read(self._root,'evaluator','subject_records_reference.jsonl'))

    def load_historical_outcomes(self):
        return tuple(_read(self._root,'evaluator','student_outcomes_reference.jsonl'))

    def load_static_fixture_diagnostics(self):
        # Static future draw is historical diagnostic data only, not an episode outcome.
        return tuple(_read(self._root,'evaluator','static_fixture_diagnostics.jsonl'))


CONSUMER_ALLOWLISTS = {
    'policy': {'files':['data/policy/{primary,sensitivity,fixture}_{train,validation,test}.jsonl'],
        'reset_fields':list(RESET_FIELDS), 'default_features':list(DEFAULT_FEATURES),
        'metadata_join_only':['student_id'], 'dynamic_initial_visibility':'withheld'},
    'initializer_auditor':{'files':['data/context/{primary,sensitivity,fixture}_{train,validation,test}.jsonl']},
    'environment':{'files':['data/environment/fixture_{train,validation,test}.jsonl'],
                   'forbidden':['static future draw','historical outcomes']},
    'evaluator':{'files':['data/evaluator/subject_records_reference.jsonl',
                         'data/evaluator/student_outcomes_reference.jsonl',
                         'data/evaluator/static_fixture_diagnostics.jsonl']},
    'extractor':{'input':'authorized notes only', 'output':'ExtractedObservationBatch'},
    'estimator':{'input':['Observation','ExtractedObservationBatch','authorized intervention events'],
                 'output':'EstimatedStudentState', 'implementation':'later stage'},
    'risk_model':{'input':['EstimatedStudentState','authorized commitments','time/horizon'],
                  'output':'RiskEstimate', 'implementation':'later stage'},
    'allocator':{'input':'DecisionInput', 'implementation':'later stage'}}

"""Version 2 immutable contracts. Times are simulation weeks, never invented dates.

These interfaces do not implement transitions, extraction, estimation or prediction.
All nested containers are tuples/frozen records; validation rejects coercion, extras,
NaN, infinities, unsupported fields and inconsistent versions at construction.
"""
from dataclasses import dataclass, fields, field, is_dataclass
import json
import math
import types
from functools import lru_cache
import re
from typing import Literal, get_args, get_origin, get_type_hints, Union

VERSION = '2.0.0'
Split = Literal['train', 'validation', 'test']
Status = Literal['observed', 'reported', 'unknown', 'missing', 'withheld', 'conflicting']
ResetField = Literal['school_id', 'age_years', 'anchor_grade1_0_20',
    'past_failures_count', 'study_time_category', 'mother_education_code',
    'father_education_code', 'internet_at_home', 'travel_time_category',
    'school_support_existing', 'family_support_existing', 'paid_classes_existing']
DynamicField = Literal['attendance', 'engagement', 'learning_need', 'enrolled',
    'reported_transport_barrier', 'support_status']
AllowedField = Union[ResetField, DynamicField]
Scalar = str | int | float | bool | None
RESET_FIELDS = get_args(ResetField)
DYNAMIC_FIELDS = get_args(DynamicField)
get_type_hints = lru_cache(maxsize=None)(get_type_hints)
UNITS = {'school_id':'source_category', 'age_years':'years', 'anchor_grade1_0_20':'grade_0_20',
    'past_failures_count':'source_code', 'study_time_category':'source_category',
    'mother_education_code':'source_category', 'father_education_code':'source_category',
    'internet_at_home':'boolean', 'travel_time_category':'source_category',
    'school_support_existing':'boolean', 'family_support_existing':'boolean',
    'paid_classes_existing':'boolean', 'attendance':'fraction', 'engagement':'fraction',
    'learning_need':'fraction', 'enrolled':'boolean', 'reported_transport_barrier':'boolean',
    'support_status':'workflow_category'}


def bound(low=0, high=None, description=''):
    return field(metadata={'minimum': low, **({'maximum': high} if high is not None else {}),
                           'description': description})


def check_type(value, annotation, path):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (types.UnionType, Union):
        for option in args:
            try:
                check_type(value, option, path)
                return
            except (TypeError, ValueError):
                pass
        raise TypeError(f'{path}: invalid union value {value!r}')
    if origin is Literal:
        if not any(type(value) is type(a) and value == a for a in args):
            raise ValueError(f'{path}: unsupported category {value!r}')
    elif origin is tuple:
        if type(value) is not tuple:
            raise TypeError(f'{path}: immutable tuple required')
        for i, item in enumerate(value):
            check_type(item, args[0], f'{path}[{i}]')
    elif annotation is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise TypeError(f'{path}: finite number required')
    elif annotation is type(None):
        if value is not None:
            raise TypeError(f'{path}: must remain unknown (null)')
    elif type(value) is not annotation:
        raise TypeError(f'{path}: expected {annotation.__name__}')
    if isinstance(value, str) and not value.strip():
        raise ValueError(f'{path}: empty string')


class Contract:
    def __post_init__(self):
        hints = get_type_hints(type(self))
        for f in fields(self):
            value = getattr(self, f.name)
            check_type(value, hints[f.name], f'{type(self).__name__}.{f.name}')
            if value is not None:
                for limit, op in [('minimum', lambda a,b: a < b), ('maximum', lambda a,b: a > b)]:
                    if limit in f.metadata and op(value, f.metadata[limit]):
                        raise ValueError(f'{f.name}: outside {dict(f.metadata)}')
        self.validate()

    def validate(self):
        pass

    def to_dict(self):
        def convert(v):
            if is_dataclass(v):
                return {f.name: convert(getattr(v, f.name)) for f in fields(v)}
            if isinstance(v, tuple):
                return [convert(x) for x in v]
            return v
        return convert(self)

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False)

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict or set(data) != {f.name for f in fields(cls)}:
            raise ValueError(f'{cls.__name__}: missing or extra fields')
        def convert(value, typ):
            origin, args = get_origin(typ), get_args(typ)
            if origin in (types.UnionType, Union):
                for t in args:
                    try:
                        v = convert(value, t)
                        check_type(v, t, cls.__name__)
                        return v
                    except (TypeError, ValueError):
                        pass
                raise ValueError('Invalid union')
            if origin is tuple:
                if type(value) is not list:
                    raise TypeError('JSON array required')
                return tuple(convert(v, args[0]) for v in value)
            if isinstance(typ, type) and issubclass(typ, Contract):
                return typ.from_dict(value)
            return value
        hints = get_type_hints(cls)
        return cls(**{k: convert(v, hints[k]) for k,v in data.items()})


@dataclass(frozen=True, slots=True)
class Lineage(Contract):
    student_id: str
    source_anchor_student_id: str
    source_dataset: Literal['uci_student_performance']
    source_row: int = bound(1, description='One-based original subject row; metadata only')
    linkage_group_id: str
    split: Split
    anchor_subject: Literal['portuguese', 'math']
    link_status: Literal['one_to_one', 'ambiguous_shared', 'single_subject']
    record_provenance: Literal['observed_source_with_derived_features', 'bootstrap_observed_profile_with_assumed_initial_dynamics']

    def validate(self):
        prefix='POR' if self.anchor_subject=='portuguese' else 'MAT'
        if self.source_anchor_student_id != prefix+f'{self.source_row:04d}':
            raise ValueError('Anchor identity must match source row/subject')
        if not re.fullmatch(r'[0-9a-f]{20}',self.linkage_group_id):
            raise ValueError('Invalid linkage identifier')
        expected = r'SYN\d{5}' if self.record_provenance.startswith('bootstrap') else prefix+r'\d{4}'
        if not re.fullmatch(expected,self.student_id):
            raise ValueError('Invalid student identifier')


@dataclass(frozen=True, slots=True)
class VerifiedContext(Contract):
    school_id: Literal['GP', 'MS']
    age_years: int = bound(15, 22, 'Source sample range; includes adults')
    rural_residence: bool
    family_size_gt3: bool
    parents_apart: bool
    mother_education_code: int = bound(0, 4, '0 none; 1 primary; 2 grades 5-9; 3 secondary; 4 higher')
    father_education_code: int = bound(0, 4, 'Same UCI school scale; not university qualification codes')
    mother_job: Literal['teacher', 'health', 'services', 'at_home', 'other']
    father_job: Literal['teacher', 'health', 'services', 'at_home', 'other']
    guardian: Literal['mother', 'father', 'other']
    travel_time_category: int = bound(1, 4, '1 <15m; 2 15-30m; 3 30-60m; 4 >60m')
    study_time_category: int = bound(1, 4, '1 <2h; 2 2-5h; 3 5-10h; 4 >10h weekly')
    past_failures_count: int = bound(0, 3, 'Preserved observed code 0-3; source codebook wording conflicts; no extrapolation')
    school_support_existing: bool
    family_support_existing: bool
    paid_classes_existing: bool
    extracurricular: bool
    nursery_attended: bool
    higher_education_aspiration: bool
    internet_at_home: bool
    family_relationship_rating: int = bound(1, 5)
    health_self_rating: int = bound(1, 5)
    anchor_grade1_0_20: int = bound(0, 20, 'First-period source grade; historical, not current need')
    math_grade1_0_20: int | None = bound(0, 20, 'Not observable without synchronized timing; missing enrichment remains null')


@dataclass(frozen=True, slots=True)
class AuditGroups(Contract):
    sex_source: Literal['F', 'M']
    both_parents_education_at_most_2: bool
    no_home_internet: bool
    travel_over_30min: bool
    disadvantage_proxy_count: int = bound(0, 3)
    disadvantage_proxy_group: bool


@dataclass(frozen=True, slots=True)
class UnknownFields(Contract):
    income_amount: None
    income_currency: None
    verified_economic_disadvantage: None
    observed_school_dropout: None
    financial_need_verified: None


@dataclass(frozen=True, slots=True)
class StudentContext(Contract):
    lineage: Lineage
    population: Literal['portugal_secondary_school']
    context: VerifiedContext
    audit: AuditGroups
    unknown: UnknownFields


@dataclass(frozen=True, slots=True)
class ProgrammeTimer(Contract):
    programme_id: str
    mentor_id: str
    starts_at: float = bound()
    remaining_sessions: int = bound()
    continuing_effect_until: float = bound()


@dataclass(frozen=True, slots=True)
class EnvironmentState(Contract):
    student_id: str
    as_of_time: float = bound()
    enrolled: bool
    attendance: float = bound(0, 1)
    engagement: float = bound(0, 1)
    learning_need: float = bound(0, 1)
    response_tendency: float = bound(0, 1)
    financial_barrier: bool
    programme_timers: tuple[ProgrammeTimer, ...]
    weeks_since_offer: int = bound()
    support_sessions_completed: int = bound()


@dataclass(frozen=True, slots=True)
class Observation(Contract):
    observation_id: str
    student_id: str
    field: AllowedField
    value: Scalar
    source_time: float | None = bound()
    available_at: float = bound()
    status: Status
    source: str
    missingness: Literal['none', 'not_measured', 'withheld', 'unknown_source_time', 'conflict']
    units: str

    def validate(self):
        if self.units != UNITS[self.field]:
            raise ValueError('Observation unit mismatch')
        if self.source_time is not None and self.source_time > self.available_at:
            raise ValueError('Observation cannot arrive before its event')
        if self.status in ('unknown', 'missing', 'withheld'):
            if self.value is not None or self.missingness == 'none':
                raise ValueError('Missing/withheld observations must have null values and a reason')
        elif self.value is None:
            raise ValueError('Available observation requires a value')
        if self.value is not None:
            validate_observed_value(self.field, self.value, self.units)


@dataclass(frozen=True, slots=True)
class PolicyReset(Contract):
    student_id: str
    observations: tuple[Observation, ...]

    def validate(self):
        if any(o.student_id != self.student_id for o in self.observations):
            raise ValueError('Observation identity mismatch')
        names = [o.field for o in self.observations]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate reset field')
        if any(o.available_at != 0 for o in self.observations):
            raise ValueError('Reset cannot contain future observations')
        if any(o.field in DYNAMIC_FIELDS and (o.value is not None or o.status != 'withheld') for o in self.observations):
            raise ValueError('Reset cannot automatically reveal generated dynamics')


def validate_observed_value(name, value, units):
    if units != UNITS[name]:
        raise ValueError('Field unit mismatch')
    if name in RESET_FIELDS:
        f = next(f for f in fields(VerifiedContext) if f.name == name)
        check_type(value, get_type_hints(VerifiedContext)[name], name)
        if 'minimum' in f.metadata and not f.metadata['minimum'] <= value <= f.metadata['maximum']:
            raise ValueError(f'{name}: out of range')
    elif name in ('attendance', 'engagement', 'learning_need'):
        check_type(value, float, name)
        if not 0 <= value <= 1 or units != 'fraction':
            raise ValueError('Dynamic numeric measurements require fractions in [0,1]')
    elif name in ('enrolled', 'reported_transport_barrier'):
        check_type(value, bool, name)
    elif name == 'support_status' and value not in ('none', 'pending', 'approved', 'delivered', 'partially_resolved', 'resolved', 'unknown'):
        raise ValueError('Invalid support status')


@dataclass(frozen=True, slots=True)
class EvidenceAssertion(Contract):
    assertion_id: str
    observation: Observation
    evidence_start: int = bound()
    evidence_end: int = bound(1)
    evidence_text: str
    kind: Literal['quantitative', 'qualitative']
    trend: Literal['improving', 'worsening', 'stable', 'unknown'] | None
    numerator: int | None = bound()
    denominator: int | None = bound(1)

    def validate(self):
        if self.evidence_end - self.evidence_start != len(self.evidence_text):
            raise ValueError('Evidence span length mismatch')
        if self.kind == 'qualitative' and (type(self.observation.value) in (int,float) or self.trend is None):
            raise ValueError('Qualitative evidence cannot invent a measured number')
        if self.kind == 'quantitative' and type(self.observation.value) not in (int,float):
            raise ValueError('Quantitative evidence requires a measured number')
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError('Ratio requires both counts')
        if self.numerator is not None:
            if self.numerator > self.denominator or self.observation.value != self.numerator / self.denominator:
                raise ValueError('Invalid attendance ratio')


@dataclass(frozen=True, slots=True)
class ExtractedObservationBatch(Contract):
    note_id: str
    student_id: str
    note_text: str
    event_time: float | None = bound()
    available_at: float = bound()
    extractor_version: str
    assertions: tuple[EvidenceAssertion, ...]

    def validate(self):
        if self.event_time is not None and self.event_time > self.available_at:
            raise ValueError('Batch cannot arrive before its event')
        ids = [a.assertion_id for a in self.assertions]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate assertion')
        for a in self.assertions:
            if (a.observation.student_id != self.student_id or a.observation.available_at != self.available_at
                    or a.observation.source_time != self.event_time):
                raise ValueError('Evidence identity/time mismatch')
            if self.note_text[a.evidence_start:a.evidence_end] != a.evidence_text:
                raise ValueError('Evidence is not in the note')


@dataclass(frozen=True, slots=True)
class EstimateField(Contract):
    field: AllowedField
    value: Scalar
    lower: float | None
    upper: float | None
    last_observed_at: float | None = bound()
    conflict: bool
    trend: Literal['improving', 'worsening', 'stable', 'unknown']
    evidence_ids: tuple[str, ...]
    units: str

    def validate(self):
        if self.units != UNITS[self.field]:
            raise ValueError('Estimated field unit mismatch')
        if self.value is not None:
            validate_observed_value(self.field, self.value, self.units)
        if (self.lower is None) != (self.upper is None):
            raise ValueError('Uncertainty bounds must be paired')
        if self.lower is not None:
            if self.field in ('attendance','engagement','learning_need') and not 0 <= self.lower <= self.upper <= 1:
                raise ValueError('Fraction uncertainty interval out of range')
            if self.lower > self.upper or (type(self.value) in (int, float) and not self.lower <= self.value <= self.upper):
                raise ValueError('Invalid estimate interval')


@dataclass(frozen=True, slots=True)
class UpdateProvenance(Contract):
    previous_version: str | None
    updater_version: str
    rule_version: str
    accepted_evidence_ids: tuple[str, ...]
    rejected_evidence_reasons: tuple[str, ...]
    prediction_description: str
    correction_description: str
    intervention_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EstimatedStudentState(Contract):
    student_id: str
    estimate_version: str
    as_of_time: float = bound()
    fields: tuple[EstimateField, ...]
    provenance: UpdateProvenance

    def validate(self):
        names = [f.field for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate estimated field')
        if any(f.last_observed_at is not None and f.last_observed_at > self.as_of_time for f in self.fields):
            raise ValueError('Future estimate evidence')


@dataclass(frozen=True, slots=True)
class RiskEstimate(Contract):
    student_id: str
    estimate_version: str
    as_of_time: float = bound()
    predicted_simulated_withdrawal_risk: float | None = bound(0, 1)
    status: Literal['available', 'unavailable', 'not_applicable']
    target: Literal['any_simulated_withdrawal_while_currently_enrolled']
    horizon_steps: int = bound()
    reference_support_regime: Literal['existing_commitments_no_new_scarce_offers']
    model_version: str
    calibration_version: str
    feature_snapshot_hash: str
    missingness_status: str
    out_of_distribution: bool
    lower: float | None = bound(0, 1)
    upper: float | None = bound(0, 1)
    uncertainty_method: str | None

    def validate(self):
        if (self.status == 'available') != (self.predicted_simulated_withdrawal_risk is not None):
            raise ValueError('Risk availability/probability mismatch')
        if self.status == 'available' and self.horizon_steps == 0:
            raise ValueError('No risk forecast at terminal time')
        if (self.lower is None) != (self.upper is None) or (self.lower is None) != (self.uncertainty_method is None):
            raise ValueError('Risk uncertainty requires bounds and a declared method')
        if self.lower is not None and (self.predicted_simulated_withdrawal_risk is None or not self.lower <= self.predicted_simulated_withdrawal_risk <= self.upper):
            raise ValueError('Invalid risk interval')


@dataclass(frozen=True, slots=True)
class ResourceAmount(Contract):
    staff_hours: float = bound()
    concurrent_caseload: int = bound()
    money: float = bound()
    administration_hours: float = bound()


@dataclass(frozen=True, slots=True)
class SupportOffer(Contract):
    event_id: str
    student_id: str
    programme_id: str
    mentor_id: str
    time: float = bound()
    available_at: float = bound()
    resources: ResourceAmount

    def validate(self):
        if self.available_at < self.time:
            raise ValueError('Event cannot be known before it occurs')


@dataclass(frozen=True, slots=True)
class Acceptance(SupportOffer):
    offer_id: str
    accepted: bool


@dataclass(frozen=True, slots=True)
class Delivery(SupportOffer):
    acceptance_id: str
    session_number: int = bound(1)
    delivered: bool


@dataclass(frozen=True, slots=True)
class Completion(SupportOffer):
    offer_id: str
    completed_sessions: int = bound()
    status: Literal['completed', 'cancelled', 'incomplete']


InterventionEvent = Union[SupportOffer, Acceptance, Delivery, Completion]


@dataclass(frozen=True, slots=True)
class Outcome(SupportOffer):
    endpoint: Literal['simulated_withdrawal', 'simulated_reentry', 'simulated_terminal_enrollment']
    value: bool
    evaluator_only: Literal[True]


@dataclass(frozen=True, slots=True)
class ResourceCommitment(Contract):
    commitment_id: str
    student_id: str
    programme_id: str
    mentor_id: str
    week: int = bound()
    remaining_sessions: int = bound()
    status: Literal['reserved', 'delivered', 'cancelled']
    resources: ResourceAmount


@dataclass(frozen=True, slots=True)
class ResourceLedger(Contract):
    week: int = bound()
    currency: str
    capacity: ResourceAmount
    used: ResourceAmount
    commitments: tuple[ResourceCommitment, ...]
    cancellations: tuple[str, ...]
    waste: ResourceAmount


@dataclass(frozen=True, slots=True)
class DecisionStudent(Contract):
    student_id: str
    estimated_state: EstimatedStudentState
    risk: RiskEstimate
    intervention_history: tuple[InterventionEvent, ...]
    waiting_weeks: int = bound()
    eligibility: Literal['eligible', 'ineligible', 'unknown']
    eligibility_evidence_ids: tuple[str, ...]

    def validate(self):
        if self.student_id != self.estimated_state.student_id or self.student_id != self.risk.student_id:
            raise ValueError('Decision identity mismatch')
        if self.estimated_state.estimate_version != self.risk.estimate_version or self.estimated_state.as_of_time != self.risk.as_of_time:
            raise ValueError('Risk does not match the current estimate')
        if any(e.student_id != self.student_id or e.available_at > self.risk.as_of_time for e in self.intervention_history):
            raise ValueError('Unauthorized event history')
        if any(f.field=='enrolled' and f.value is False for f in self.estimated_state.fields) and self.risk.status != 'not_applicable':
            raise ValueError('Enrolled withdrawal risk is not applicable while withdrawn')


@dataclass(frozen=True, slots=True)
class DecisionInput(Contract):
    schema_version: Literal['2.0.0']
    as_of_time: float = bound()
    students: tuple[DecisionStudent, ...]
    resources: ResourceLedger

    def validate(self):
        if len({s.student_id for s in self.students}) != len(self.students):
            raise ValueError('Duplicate decision student')
        if any(s.estimated_state.as_of_time != self.as_of_time for s in self.students):
            raise ValueError('Mixed decision times')


@dataclass(frozen=True, slots=True)
class SeedStream(Contract):
    name: Literal['population', 'shared_shock', 'individual_transition', 'uptake', 'dropout', 'observation', 'tie_breaking']
    seed: int = bound()


@dataclass(frozen=True, slots=True)
class EpisodeRecord(Contract):
    episode_id: str
    initial_cohort: tuple[Lineage, ...]
    scenario: str
    source_split: Split
    seed_streams: tuple[SeedStream, ...]
    configuration_hash: str
    policy_version: str
    evaluator_only_outcomes: tuple[Outcome, ...]

    def validate(self):
        if any(s.split != self.source_split for s in self.initial_cohort):
            raise ValueError('Episode crosses source splits')
        names = [s.name for s in self.seed_streams]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate random stream')


def json_schemas():
    """Export interoperable structural schemas; Python also enforces cross-field rules."""
    definitions = {}
    def schema(typ):
        origin, args = get_origin(typ), get_args(typ)
        if origin in (types.UnionType, Union):
            return {'anyOf': [schema(t) for t in args]}
        if origin is Literal:
            return {'enum': list(args)}
        if origin is tuple:
            return {'type': 'array', 'items': schema(args[0])}
        if isinstance(typ, type) and issubclass(typ, Contract):
            if typ.__name__ not in definitions:
                definitions[typ.__name__] = {}
                hints = get_type_hints(typ)
                definitions[typ.__name__] = {'type': 'object', 'additionalProperties': False,
                    'required': [f.name for f in fields(typ)],
                    'properties': {f.name: {**schema(hints[f.name]), **dict(f.metadata)} for f in fields(typ)}}
            return {'$ref': '#/$defs/' + typ.__name__}
        return {'type': {str:'string', int:'integer', float:'number', bool:'boolean', type(None):'null'}[typ],
                **({'minLength': 1} if typ is str else {})}
    for typ in list(globals().values()):
        if isinstance(typ, type) and typ is not Contract and issubclass(typ, Contract):
            schema(typ)
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            '$id': 'urn:student-support:contracts:2.0.0', 'title': 'Stage 1 canonical contracts v2',
            '$defs': definitions}

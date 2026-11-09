"""Weekly v1 public records. Latent conditions and future draws have no fields here."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

from .belief_state import validate_belief
from .money import amount
from .delivery_forecasts import WeeklyCommittedRisk


@dataclass(frozen=True)
class StudentProfile:
    student_id: str
    support_type: str
    need_score: float
    disadvantage_proxy: bool | None
    sex_source: str | None

    def __post_init__(self):
        from ..utils.constants import ALL_SUPPORT_TYPES
        if (not self.student_id or self.support_type not in ALL_SUPPORT_TYPES
                or not math.isfinite(self.need_score) or not 0 <= self.need_score <= 1
                or (self.disadvantage_proxy is not None and type(self.disadvantage_proxy) is not bool)):
            raise ValueError('invalid authorized student profile')


@dataclass(frozen=True)
class SupportOffer:
    student_id: str
    mentor_id: str
    start_week: int


@dataclass(frozen=True)
class DeliveryAction:
    offers: tuple[SupportOffer, ...] = ()
    cancel_programme_ids: tuple[str, ...] = ()
    status: str = 'feasible'
    objective: float = 0.
    projected_offers: tuple[SupportOffer, ...] = ()
    projected_normalized_shortfall: float = 0.
    lexicographic_complete: bool = False
    solver_message: str = ''
    continuation_reviews: tuple = ()
    uncertainty_sets: tuple = ()


EVENT_KINDS = ('support_offered', 'offer_accepted', 'offer_refused', 'session_reserved',
    'session_scheduled', 'session_delivered', 'session_missed', 'reservation_released',
    'administration_charged', 'programme_active', 'programme_completed', 'programme_cancelled',
    'programme_incomplete', 'programme_outcome_observed')


@dataclass(frozen=True)
class DeliveryEvent:
    event_id: str
    kind: str
    source_week: int
    available_week: int
    student_id: str
    mentor_id: str
    programme_id: str
    session_id: str | None = None
    scheduled_week: int | None = None
    money: str = '0'
    reason: str = ''
    random_stream: str | None = None
    provenance: str = 'scheduled_weekly/v1'

    def __post_init__(self):
        if (self.kind not in EVENT_KINDS or not all((self.event_id, self.student_id,
                self.mentor_id, self.programme_id)) or type(self.source_week) is not int
                or self.source_week < 1 or self.available_week != self.source_week + 1
                or self.provenance != 'scheduled_weekly/v1'):
            raise ValueError('invalid delivery event identity, kind or cutoff')
        amount(self.money)
        session_kinds = ('session_reserved', 'session_scheduled', 'session_delivered',
                         'session_missed', 'reservation_released')
        if self.kind in session_kinds and (not self.session_id or type(self.scheduled_week) is not int):
            raise ValueError('session event requires session identity and scheduled week')
        if self.kind not in session_kinds and (self.session_id is not None or self.scheduled_week is not None):
            raise ValueError('programme event cannot reference a session slot')
        monetary = ('session_reserved', 'session_delivered', 'session_missed',
                    'reservation_released', 'administration_charged')
        if self.kind not in monetary and amount(self.money):
            raise ValueError('non-monetary event cannot charge money')


@dataclass(frozen=True)
class ScheduledSession:
    session_id: str
    week: int
    status: str = 'RESERVED'


@dataclass(frozen=True)
class Programme:
    programme_id: str
    student_id: str
    mentor_id: str
    offer_week: int
    offer_window_start: int
    status: str
    sessions: tuple[ScheduledSession, ...]

    @property
    def delivered_sessions(self):
        return sum(s.status == 'DELIVERED' for s in self.sessions)


@dataclass(frozen=True)
class WeeklyEstimate:
    student_id: str
    as_of_week: int
    condition_probabilities: tuple[float, ...]
    estimate_id: str
    evidence_ids: tuple[str, ...]
    last_observation_week: int | None
    uncertainty: tuple

    def __post_init__(self):
        validate_belief(self.condition_probabilities)
        if not self.estimate_id or type(self.as_of_week) is not int or self.as_of_week < 1:
            raise ValueError('weekly estimate requires current identity and cutoff')


@dataclass(frozen=True)
class WeeklyRisk:
    student_id: str
    as_of_week: int
    weeks_remaining: int
    input_estimate_id: str
    probability: float
    reference_policy: str = 'weekly_WAIT_no_additional_support'

    def __post_init__(self):
        if (not self.input_estimate_id or not math.isfinite(self.probability)
                or not 0 <= self.probability <= 1 or type(self.weeks_remaining) is not int
                or self.weeks_remaining < 0):
            raise ValueError('invalid weekly risk probability, identity or horizon')


@dataclass(frozen=True)
class WeeklyStudent:
    profile: StudentProfile
    enrolled: bool
    estimate: WeeklyEstimate
    risk: WeeklyRisk
    eligible: bool
    waiting_weeks: int
    offers: tuple[str, ...]
    programmes: tuple[Programme, ...]
    committed_risk: WeeklyCommittedRisk | None = None

    @property
    def student_id(self):
        return self.profile.student_id


@dataclass(frozen=True)
class WeeklyMentor:
    mentor_id: str
    support_types: tuple[str, ...]
    max_concurrent_students: int
    cost_per_session: str
    # week, hours, session slots: preannounced immutable calendar
    calendar: tuple[tuple[int, str, int], ...]


@dataclass(frozen=True)
class ResourceCell:
    mentor_id: str
    week: int
    available_hours: str
    reserved_hours: str
    delivered_hours: str
    available_slots: int
    reserved_slots: int
    delivered_sessions: int
    wasted_slots: int
    active_students: tuple[str, ...]
    maximum_caseload: int
    reserved_money: str
    spent_money: str
    released_money: str
    administrative_cost: str
    unused_hours: str


@dataclass(frozen=True)
class LedgerSnapshot:
    budget: str
    reserved: str
    spent: str
    spendable: str
    released: str
    administrative_cost: str
    cells: tuple[ResourceCell, ...]


@dataclass(frozen=True)
class OfferCohort:
    group: str
    stratum: str
    student_ids: tuple[str, ...]


@dataclass(frozen=True)
class OfferWindow:
    start_week: int
    end_week: int
    cohorts: tuple[OfferCohort, ...]
    offered_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeeklyDecisionState:
    week: int
    weeks_remaining: int
    students: tuple[WeeklyStudent, ...]
    mentors: tuple[WeeklyMentor, ...]
    ledger: LedgerSnapshot
    fairness_window: OfferWindow
    authorized_event_ids: tuple[str, ...]
    contract: str = 'scheduled_weekly/decision/v3'
    decision_prepared: bool = False

    def validate_estimates(self):
        for s in self.students:
            if (s.estimate.student_id != s.student_id or s.risk.student_id != s.student_id
                    or s.estimate.as_of_week != self.week or s.risk.as_of_week != self.week
                    or s.risk.weeks_remaining != self.weeks_remaining
                    or s.risk.input_estimate_id != s.estimate.estimate_id):
                raise ValueError('stale or mismatched weekly estimate/risk identity')
            r = s.committed_risk
            if r is not None and (r.student_id != s.student_id or r.as_of_week != self.week
                    or r.weeks_remaining != self.weeks_remaining
                    or r.input_estimate_id != s.estimate.estimate_id):
                raise ValueError('stale or mismatched committed-support estimate/risk identity')


@dataclass(frozen=True)
class WeeklyNote:
    """Weekly dates with explicit period-index adapters for the existing extractor.

    The extraction schema's historical *_month fields encode week indices ONLY
    inside this named adapter. No legacy Note or replay artifact is relabeled.
    """
    note_id: str
    student_id: str
    source_week: int
    available_week: int
    text: str
    source_event_ids: tuple[str, ...]
    mentor_id: str | None = None
    programme_id: str | None = None
    session_id: str | None = None
    delivery_event_id: str | None = None
    observation_contract: str | None = None

    def __post_init__(self):
        if (not self.note_id or not self.student_id or len(self.source_event_ids) != 1
                or type(self.source_week) is not int or self.source_week < 0
                or type(self.available_week) is not int or self.available_week <= self.source_week
                or (self.mentor_id is None) != (self.programme_id is None)
                or (self.session_id is not None and not all((self.mentor_id,
                    self.programme_id, self.delivery_event_id, self.observation_contract)))):
            raise ValueError('weekly note requires source provenance and future availability')

    @property
    def event_month(self):
        return self.source_week

    @property
    def available_from_month(self):
        return self.available_week

    @property
    def extraction_period_adapter(self):
        return 'week_indices_in_legacy_schema/v1'

    @property
    def creation_time(self):
        return (datetime(2026, 1, 1, tzinfo=timezone.utc)
                + timedelta(weeks=self.source_week, hours=23)).isoformat()

"""Public-information expected-delivery forecasts (not realized outcomes)."""
from dataclasses import dataclass
import math
import numpy as np


def terminal_operator(config, cutoff, session_weeks=(), *, offer_week=None, accepted=True):
    """Joint active/inactive mass preserves programme-level cancellation survival.

    Already accepted programmes start with active probability one. Cancellation
    precedes every later service week, including the present cutoff; it is never
    sampled here. Withdrawn is absorbing, so early termination is equivalent for
    terminal retention. Past delivered effects belong only in the input belief.
    """
    wait, treatment = np.asarray(config.weekly_wait_matrix), config.treatment_matrix
    uptake = 1. if accepted else config.acceptance_probability
    active, inactive = np.eye(4)*uptake, np.eye(4)*(1-uptake)
    schedule = tuple(w for w in session_weeks if w >= cutoff)
    last = max(schedule, default=cutoff-1)
    q = config.attendance_probability * config.delivery_probability
    for week in range(cutoff, config.horizon_weeks+1):
        if offer_week is not None and offer_week < week <= last:
            cancelled = active * config.cancellation_probability
            active, inactive = active-cancelled, inactive+cancelled
        matrix = q*treatment + (1-q)*wait if week in schedule else wait
        active, inactive = active @ matrix, inactive @ wait
    return active+inactive


def remaining_marginals(config, cutoff, programme):
    weeks = tuple(s.week for s in programme.sessions if s.status == 'RESERVED' and s.week >= cutoff)
    retained = np.array([1., 1., 1., 0.])
    return (terminal_operator(config, cutoff, weeks, offer_week=programme.offer_week)
            - terminal_operator(config, cutoff)) @ retained


@dataclass(frozen=True)
class WeeklyCommittedRisk:
    student_id: str
    as_of_week: int
    weeks_remaining: int
    input_estimate_id: str
    probability: float
    programme_ids: tuple[str, ...]
    forecast_regime: str = 'continue_accepted_no_new_offers'
    target: str = 'synthetic_terminal_non_enrollment'
    approximation: str = 'joint_active_inactive_expected_weekly_delivery/v1'
    version: int = 1

    def __post_init__(self):
        if (not self.input_estimate_id or not math.isfinite(self.probability)
                or not 0 <= self.probability <= 1 or self.weeks_remaining < 0):
            raise ValueError('invalid committed-support forecast')


def committed_support_risk(config, estimate, programmes):
    active = tuple(p for p in programmes if p.status in ('SCHEDULED', 'ACTIVE'))
    if len(active) > 1:
        raise ValueError('forecast contract permits one accepted programme per student')
    weeks = tuple(s.week for p in active for s in p.sessions
                  if s.status == 'RESERVED' and s.week >= estimate.as_of_week)
    operator = terminal_operator(config, estimate.as_of_week, weeks,
        offer_week=active[0].offer_week if active else None)
    risk = float(np.clip(np.asarray(estimate.condition_probabilities) @ operator[:, 3], 0, 1))
    return WeeklyCommittedRisk(estimate.student_id, estimate.as_of_week,
        max(0, config.horizon_weeks-estimate.as_of_week+1), estimate.estimate_id,
        risk, tuple(p.programme_id for p in active))

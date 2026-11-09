"""Conservative, evidence-gated reassessment of accepted tutoring programmes."""
from dataclasses import dataclass, replace
import numpy as np

from .delivery_contracts import DeliveryAction
from .delivery_forecasts import remaining_marginals
from .delivery_resources import feasible_offers, validate_offers
from .delivery_uncertainty import weekly_scenario_values
from .fairness_planner import feasible_vector
from .money import amount
from .optimization import solve_milp


@dataclass(frozen=True)
class ContinuationReview:
    programme_id: str
    student_id: str
    cutoff_week: int
    estimate_id: str
    remaining_session_weeks: tuple
    scenario_continuation_gains: tuple
    continuation_value: float
    opportunity_value: float | None
    stability_margin: float
    fresh_evidence: bool
    decision: str
    reason: str
    released_liability_if_cancelled: str
    opportunity_solver_status: str
    units: str = 'expected_terminal_retained_students'
    rule: str = 'evidence_gated_capacity_opportunity/v1'


def released_view(state, programme, config):
    """Hypothetical planning view ONLY. Never used to validate executable offers."""
    weeks = {s.week for s in programme.sessions if s.status == 'RESERVED' and s.week >= state.week}
    liability = len(weeks)*amount(config.cost_per_session)
    cells = []
    for c in state.ledger.cells:
        if c.mentor_id != programme.mentor_id or c.week < state.week:
            cells.append(c)
            continue
        session = c.week in weeks
        cells.append(replace(c,
            reserved_slots=c.reserved_slots-int(session),
            reserved_hours=str(amount(c.reserved_hours)-int(session)*amount(config.session_duration_hours)),
            reserved_money=str(amount(c.reserved_money)-int(session)*amount(config.cost_per_session)),
            active_students=tuple(sid for sid in c.active_students if sid != programme.student_id)))
    ledger = replace(state.ledger, cells=tuple(cells),
        reserved=str(amount(state.ledger.reserved)-liability),
        spendable=str(amount(state.ledger.spendable)+liability))
    return replace(state, ledger=ledger)


def portfolio_value(state, config, scenarios):
    """Max-min incremental benefit of new offers from the NEXT feasible cutoff.

    Existing commitments are fixed. No speculative release enters real actions.
    Future eligibility/beliefs remain frozen; refusal releases are not assumed.
    """
    from .delivery_policy import weekly_resource_rows
    candidates = tuple(a for a in feasible_offers(state, config, end_week=config.horizon_weeks)
                       if a.start_week > state.week)
    if not candidates:
        return 0., 'optimal_empty'
    values = weekly_scenario_values(config, state, candidates, scenarios)
    n = len(candidates)
    resource, bounds, _ = weekly_resource_rows(state, candidates, config)
    rows = np.pad(resource, ((0, 0), (0, 1)))
    lower, upper = np.full(len(rows), -np.inf), bounds
    for v in values:
        rows = np.vstack([rows, np.r_[-v, 1.]])
        lower, upper = np.append(lower, -np.inf), np.append(upper, 0.)
    objective = np.r_[np.zeros(n), -1.]
    variable_lower = np.r_[np.zeros(n), -np.abs(values).sum()]
    result = solve_milp(objective, rows, lower, upper, binary_count=n,
        integer_count=n, variable_lower=variable_lower, time_limit=config.planner_time_limit)
    if result.status != 0 or not feasible_vector(result, rows, lower, upper,
            integer_count=n, variable_lower=variable_lower):
        return None, 'nonoptimal_'+str(result.status)
    bits = np.rint(result.x[:n])
    selected = tuple(a for a,b in zip(candidates,bits) if b)
    validate_offers(state, DeliveryAction(selected), config, projected=True)
    return float(np.min(values @ bits)), 'optimal'


def reassess_programmes(state, config, scenarios, *, stability_margin=.001, minimum_age_weeks=1):
    reviews, cancelled = [], []
    shadow = state
    for student in sorted(state.students, key=lambda s:s.student_id):
        for p in sorted(student.programmes, key=lambda p:p.programme_id):
            if p.status not in ('SCHEDULED', 'ACTIVE'):
                continue
            weeks = tuple(s.week for s in p.sessions if s.status == 'RESERVED' and s.week >= state.week)
            gain = remaining_marginals(config, state.week, p)
            values = tuple(float(np.asarray(dict(s.beliefs)[student.student_id]) @ gain) for s in scenarios)
            # Robust continuity protection: cancellation must beat even the
            # largest remaining benefit among the declared coherent scenarios.
            continuation = max(values)
            quality = dict(student.estimate.uncertainty)
            fresh = bool(quality.get('new_condition_evidence_ids')) and not (
                quality.get('condition_conflict') or quality.get('rejected_condition_observation'))
            opportunity, status, reason = None, 'not_required', 'no_new_usable_condition_evidence'
            decision = 'continue'
            if fresh and state.week-p.offer_week >= minimum_age_weeks and weeks:
                before, bstatus = portfolio_value(shadow, config, scenarios)
                after_state = released_view(shadow, p, config)
                after, astatus = portfolio_value(after_state, config, scenarios)
                status = bstatus+'/'+astatus
                if before is not None and after is not None:
                    opportunity = max(0., after-before)
                    reason = 'continuity_margin_protects_support'
                    if opportunity > continuation+stability_margin:
                        decision, reason = 'cancel', 'released_capacity_opportunity_exceeds_remaining_benefit_and_margin'
                        cancelled.append(p.programme_id)
                        shadow = after_state
                else:
                    reason = 'nonoptimal_opportunity_solve_preserves_support'
            elif fresh:
                reason = 'minimum_programme_age_or_no_remaining_sessions'
            reviews.append(ContinuationReview(p.programme_id, p.student_id, state.week,
                student.estimate.estimate_id, weeks, values, continuation, opportunity,
                stability_margin, fresh, decision, reason,
                str(len(weeks)*amount(config.cost_per_session)), status))
    return tuple(reviews), tuple(cancelled)

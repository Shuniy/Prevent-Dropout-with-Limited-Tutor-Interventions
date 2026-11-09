"""Frozen four-week unique OFFER coverage, distinct from monthly admissions."""
from dataclasses import asdict, replace

from .delivery_contracts import OfferCohort, OfferWindow
from .fairness_audit import required_access
from .student_condition import STATES


def offer_feasibility_diagnostics(state, config, events=()):
    """Exact joint reservation-model bound at a frozen window snapshot.

    Fixed commitments, unchanged enrollment, no future releases/refusals and full
    worst-case offer liabilities. This is conditional physical feasibility, not
    guaranteed realized coverage. Cohort counts come from ONE shared witness;
    independent per-cell maxima are never summed.
    """
    import numpy as np
    from .delivery_contracts import DeliveryAction
    from .delivery_resources import feasible_offers, validate_offers
    from .delivery_policy import weekly_resource_rows
    from .fairness_planner import feasible_vector
    from .optimization import solve_milp
    window = state.fairness_window
    cohorts = tuple(c for c in window.cohorts if c.student_ids)
    frozen = set(sid for c in cohorts for sid in c.student_ids)
    prior = set(window.offered_ids)
    candidates = tuple(a for a in feasible_offers(state, config, end_week=window.end_week)
                       if a.student_id in frozen-prior)
    required = [required_access(config.fairness_target, len(c.student_ids)) for c in cohorts]
    selected, status, minimum, maximum = (), 'optimal_empty', None, 0
    if candidates:
        n, k = len(candidates), len(cohorts)
        resource, bounds, _ = weekly_resource_rows(state, candidates, config)
        cardinality = solve_milp(-np.ones(n), resource, np.full(len(resource), -np.inf), bounds,
            binary_count=n, time_limit=config.planner_time_limit)
        maximum = None
        if cardinality.status == 0 and feasible_vector(cardinality, resource,
                np.full(len(resource), -np.inf), bounds):
            witness_max = tuple(a for a,b in zip(candidates,np.rint(cardinality.x)) if b)
            validate_offers(state,DeliveryAction(witness_max),config,projected=True)
            maximum = len({a.student_id for a in witness_max})
        rows = np.pad(resource, ((0,0), (0,k)))
        lower, upper = np.full(len(rows), -np.inf), bounds
        for i,c in enumerate(cohorts):
            row = np.zeros(n+k)
            row[:n] = [int(a.student_id in c.student_ids) for a in candidates]
            row[n+i] = 1
            rows = np.vstack([rows,row])
            lower = np.append(lower, required[i]-len(set(c.student_ids)&prior))
            upper = np.append(upper, np.inf)
        objective = np.r_[np.zeros(n),np.ones(k)]
        result = solve_milp(objective, rows, lower, upper, binary_count=n,
            integer_count=n+k, time_limit=config.planner_time_limit)
        if result.status != 0 or not feasible_vector(result, rows, lower, upper, integer_count=n+k):
            status = 'nonoptimal_bound_unavailable_'+str(result.status)
        else:
            minimum = int(round(objective @ result.x))
            rows = np.vstack([rows,objective])
            lower, upper = np.append(lower,-np.inf), np.append(upper,minimum)
            result = solve_milp(np.r_[-np.ones(n),np.zeros(k)], rows, lower, upper,
                binary_count=n, integer_count=n+k, time_limit=config.planner_time_limit)
            if result.status == 0 and feasible_vector(result, rows, lower, upper, integer_count=n+k):
                selected = tuple(a for a,b in zip(candidates,np.rint(result.x[:n])) if b)
                validate_offers(state,DeliveryAction(selected),config,projected=True)
                status = 'optimal'
            else:
                status, minimum = 'nonoptimal_bound_unavailable_'+str(result.status), None
    else:
        minimum = sum(max(0,r-len(set(c.student_ids)&prior)) for c,r in zip(cohorts,required))
    actual = {e.student_id for e in events if e.kind == 'support_offered'
              and window.start_week <= e.source_week <= window.end_week}
    actual |= prior
    witness = prior | {a.student_id for a in selected}
    shortfall = sum(max(0,r-len(set(c.student_ids)&actual)) for c,r in zip(cohorts,required))
    return dict(window_start_week=window.start_week, window_end_week=window.end_week,
        snapshot_cutoff_week=state.week, frozen_eligible_students=len(frozen),
        required_unique_offers=sum(required), actual_unique_offers=len(actual&frozen),
        actual_coverage_shortfall=shortfall,
        feasible_candidate_starts=len(candidates),
        feasible_new_start_weeks=sorted({a.start_week for a in candidates}),
        maximum_attainable_unique_offers=maximum+len(prior&frozen) if maximum is not None else None,
        maximum_attainable_coverage_at_minimum_shortfall=len(witness&frozen) if minimum is not None else None,
        unavoidable_shortfall_under_frozen_model=minimum,
        additional_shortfall_beyond_frozen_model=max(0,shortfall-minimum) if minimum is not None else None,
        terminal_no_carryover_infeasibility=config.schedule(state.week)[-1] > config.horizon_weeks,
        solver_status=status, jointly_feasible_witness=tuple(asdict(a) for a in selected),
        cohort_witness=tuple(dict(group=c.group,stratum=c.stratum,
            frozen_eligible_students=len(c.student_ids),required_unique_offers=r,
            actual_unique_offers=len(set(c.student_ids)&actual),
            attainable_unique_offers_in_joint_witness=len(set(c.student_ids)&witness))
            for c,r in zip(cohorts,required)),
        model='frozen_snapshot_fixed_commitments_no_future_releases_or_withdrawals/v1',
        bound_scope='min_total_count_shortfall_then_max_unique_coverage_joint_reservation_model',
        guaranteed_realized_coverage=False)


def freeze_offer_window(state, config):
    if (state.week - 1) % 4:
        raise ValueError('offer cohort must freeze at the start of four actual weeks')
    groups = ('False', 'True', 'unknown') if config.fairness_grouping_attribute == 'disadvantage_proxy' else ('F', 'M', 'unknown')
    cells = {(g, k): [] for g in groups for k in ('stable', 'vulnerable', 'disengaged', 'uncertain')}
    for s in state.students:
        if not s.eligible or s.profile.support_type != 'tutoring':
            continue
        # Eligibility is authorized, not conditional on the shared budget or on
        # successful uptake. Lack of resources must remain visible as shortfall.
        value = getattr(s.profile, config.fairness_grouping_attribute)
        group = str(value) if type(value) is bool else value if value in groups else 'unknown'
        probabilities = s.estimate.condition_probabilities
        best = max(range(4), key=probabilities.__getitem__)
        stratum = STATES[best].value if best < 3 and probabilities[best] >= .6 else 'uncertain'
        cells[(group, stratum)].append(s.student_id)
    return OfferWindow(state.week, min(state.week + 3, config.horizon_weeks),
        tuple(OfferCohort(g, k, tuple(sorted(ids))) for (g, k), ids in sorted(cells.items())))


def update_offer_window(window, events):
    ids = {e.student_id for e in events if e.kind == 'support_offered'
           and window.start_week <= e.source_week <= window.end_week}
    return replace(window, offered_ids=tuple(sorted(ids)))


def offer_fairness_rows(window, events, config):
    """Acceptance/completion follow original offer cohorts, even across windows."""
    offers = {e.programme_id: e for e in events if e.kind == 'support_offered'
              and window.start_week <= e.source_week <= window.end_week}
    offered = {e.student_id for e in offers.values()}
    accepted = {e.student_id for e in events if e.kind == 'offer_accepted' and e.programme_id in offers}
    completed = {e.student_id for e in events if e.kind == 'programme_completed' and e.programme_id in offers}
    completed_in_window = {e.student_id for e in events if e.kind == 'programme_completed'
                           and e.programme_id in offers and e.source_week <= window.end_week}
    rows = []
    for cohort in window.cohorts:
        ids, size = set(cohort.student_ids), len(cohort.student_ids)
        required = required_access(config.fairness_target, size)
        count = len(ids & offered)
        first = {sid: min(e.source_week for e in offers.values() if e.student_id == sid)
                 for sid in ids & offered}
        waits = [first.get(sid, window.end_week + 1) - window.start_week for sid in ids]
        rows.append(dict(metric='four_week_unique_support_offers', group=cohort.group,
            stratum=cohort.stratum, window_start_week=window.start_week, window_end_week=window.end_week,
            truncated_at_horizon=window.end_week - window.start_week < 3,
            frozen_eligible_students=size, required_access=required, unique_offers=count,
            offer_coverage=count / size if size else None,
            accepted_students=len(ids & accepted),
            acceptance_rate=len(ids & accepted) / count if count else None,
            acceptance_coverage=len(ids & accepted) / size if size else None,
            completed_students=len(ids & completed),
            completion_coverage=len(ids & completed) / size if size else None,
            completion_rate=len(ids & completed) / len(ids & accepted) if ids & accepted else None,
            completed_within_offer_window=len(ids & completed_in_window),
            shortfall=max(0, required - count),
            normalized_shortfall=max(0, required - count) / size if size else None,
            small_group=0 < size < config.fairness_small_group_threshold,
            mean_waiting_weeks=sum(waits) / size if size else None,
            max_waiting_weeks=max(waits,default=None),
            waiting_rule='unoffered_censored_at_window_end_frozen_denominator'))
    for row in rows:
        for metric in ('offer_coverage', 'completion_coverage', 'mean_waiting_weeks'):
            values = [r[metric] for r in rows if r['stratum'] == row['stratum'] and r[metric] is not None]
            row[metric + '_group_disparity'] = max(values) - min(values) if len(values) > 1 else None
    return rows

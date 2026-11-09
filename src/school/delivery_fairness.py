"""Frozen four-week unique OFFER coverage, distinct from monthly admissions."""
from dataclasses import replace

from .delivery_contracts import OfferCohort, OfferWindow
from .fairness_audit import required_access
from .student_condition import STATES


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

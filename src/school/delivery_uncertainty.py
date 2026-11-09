"""Weekly adaptation of uncertainty_scenarios.py's documentation subset model."""
from dataclasses import dataclass
import numpy as np
from .uncertainty_scenarios import BeliefScenario, UncertaintyScenarioConfig


@dataclass(frozen=True)
class WeeklyUncertaintySet:
    student_id: str
    cutoff_week: int
    estimate_id: str
    radius: float
    latest_assimilated_source_week: int | None
    signal_age_weeks: int
    missing_previous_interval: bool
    newly_assimilated_evidence_ids: tuple
    conflict: bool
    rejected_condition_observation: bool
    belief_entropy_nats: float | None
    documentation_subset: str
    clipping_applied: bool
    fallback: str | None
    rule: str = 'monthly_freshness_mixture_adapted_to_weeks/v1'
    freshness_weeks: int = 12
    source: str = 'declared_synthetic_assumption_not_empirically_calibrated'


def weekly_uncertainty_sets(state, base_radius=.25):
    # Reuse monthly validation and assumptions; one protocol month = four weeks.
    config = UncertaintyScenarioConfig(radius=base_radius)
    freshness = 4*config.freshness_months
    result = []
    for s in sorted(state.students, key=lambda s: s.student_id):
        e, last = s.estimate, s.estimate.last_observation_week
        if last is not None and (type(last) is not int or not 0 <= last < state.week):
            raise ValueError('assimilated source week must precede cutoff')
        info = dict(e.uncertainty)
        age = state.week-1-last if last is not None else freshness
        missing = bool(info.get('missing_current_signal', last is None or age > 0))
        conflict = bool(info.get('condition_conflict', False))
        rejected = bool(info.get('rejected_condition_observation', False))
        # A rejected new measurement never refreshes the last assimilated source.
        missing = missing or conflict or rejected
        raw = base_radius*(config.missingness_multiplier if missing else 1)*(1+min(age,freshness)/freshness)
        result.append(WeeklyUncertaintySet(s.student_id, state.week, e.estimate_id,
            min(1., raw), last, age, missing, tuple(info.get('new_condition_evidence_ids', ())),
            conflict, rejected, info.get('entropy_nats'),
            'missing_or_stale' if missing or age else 'fresh_documented', raw > 1,
            'no_assimilated_condition_signal' if last is None else None,
            freshness_weeks=freshness))
    return tuple(result)


def weekly_belief_scenarios(state, sets, reference_gain):
    nominal = tuple((s.student_id, s.estimate.condition_probabilities)
                    for s in sorted(state.students, key=lambda s: s.student_id))
    result = [BeliefScenario('nominal', nominal)]
    for subset in ('fresh_documented', 'missing_or_stale'):
        radii = {u.student_id:u.radius for u in sets if u.documentation_subset == subset}
        if not any(radii.values()):
            continue
        for direction, index in (('low', int(np.argmin(reference_gain[:3]))),
                                 ('high', int(np.argmax(reference_gain[:3])))):
            beliefs = []
            for sid, belief in nominal:
                rho = radii.get(sid, 0.)
                extreme = np.zeros(4)
                extreme[index], extreme[3] = 1-belief[3], belief[3]
                beliefs.append((sid, tuple((1-rho)*np.asarray(belief)+rho*extreme)))
            result.append(BeliefScenario(subset+'_'+direction, tuple(beliefs)))
    return tuple(result)


def weekly_scenario_values(config, state, candidates, scenarios):
    from .delivery_policy import delivery_rollout_marginals
    marginal = {w:delivery_rollout_marginals(config, state.week, w)
                for w in {a.start_week for a in candidates}}
    return np.asarray([[float(np.asarray(dict(s.beliefs)[a.student_id]) @ marginal[a.start_week])
                        for a in candidates] for s in scenarios])

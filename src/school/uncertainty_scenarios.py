"""Finite belief perturbations based exclusively on the current decision input.

These bounded mixtures are declared synthetic sensitivity assumptions, not
confidence regions learned from data. A scenario shifts one documentation
subset simultaneously; it never combines both subsets' adverse shifts.
"""

from dataclasses import dataclass
import math

import numpy as np

from .belief_state import validate_belief
from .retention_value import estimate_incremental_benefit
from .student_condition import STATES


SCENARIO_SOURCE = "declared_synthetic_assumption_not_empirically_calibrated"


@dataclass(frozen=True)
class UncertaintyScenarioConfig:
    radius: float = .25
    missingness_multiplier: float = 1.5
    freshness_months: int = 3

    def __post_init__(self):
        if not math.isfinite(self.radius) or not 0 <= self.radius <= 1:
            raise ValueError("uncertainty radius must lie within [0, 1]")
        if not math.isfinite(self.missingness_multiplier) or self.missingness_multiplier < 1:
            raise ValueError("missingness multiplier must be finite and at least one")
        if type(self.freshness_months) is not int or self.freshness_months < 1:
            raise ValueError("freshness_months must be a positive integer")


@dataclass(frozen=True)
class BeliefScenario:
    name: str
    beliefs: tuple
    source: str = SCENARIO_SOURCE
    parameters: tuple = ()

    def __post_init__(self):
        if not self.name or not self.source:
            raise ValueError("scenario requires a name and provenance source")
        ids = [sid for sid, _ in self.beliefs]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario student identifiers must be unique")
        object.__setattr__(self, "beliefs", tuple(
            (sid, validate_belief(probabilities)) for sid, probabilities in self.beliefs))


def build_belief_scenarios(state, config, wait_matrix, programme_matrix):
    """Nominal plus optimistic/pessimistic shifts of each documentation subset.

    For each eligible estimated student, rho_i is bounded by one and equals
    radius * missingness_multiplier**missing * (1 + min(age,F)/F).
    Age is the successfully assimilated condition signal source age relative to cutoff minus one; unknown age
    defaults to F. The two disjoint subsets are current/fresh versus missing or
    stale. Each scenario mixes a subset's beliefs toward the live condition
    with largest/smallest current-horizon benefit. Oracle labels remain exact.
    """
    state.validate_estimates()
    estimates = {s.student_id: s for s in state.estimated_student_states}
    nominal, uncertainty = [], []
    subsets = {"fresh_documented": [], "missing_or_stale": []}
    oracle = state.observation_mode == "fully_observed_benchmark"
    for student in sorted(state.students, key=lambda s: s.student_id):
        if oracle:
            if student.condition is None:
                raise ValueError("oracle scenarios require an explicitly observed condition")
            belief = tuple(float(condition == student.condition) for condition in STATES)
        else:
            belief = validate_belief(student.condition_probabilities)
        nominal.append((student.student_id, belief))
        if oracle or not student.eligible:
            uncertainty.append((student.student_id, (("mixture_radius", 0.0),
                ("source", "explicit_oracle_label" if oracle else "ineligible_no_perturbation"))))
            continue
        estimate = estimates.get(student.student_id)
        observed = dict(estimate.observation_uncertainty) if estimate else {}
        last = estimate.last_observation_month if estimate else None
        if last is not None and (type(last) is not int or last >= state.month or last < 0):
            raise ValueError("signal freshness must precede the decision cutoff")
        age = max(0, state.month - 1 - last) if last is not None else config.freshness_months
        missing = bool(observed.get("missing_current_signal", last is None or age > 0))
        radius = min(1.0, config.radius * (config.missingness_multiplier if missing else 1)
                     * (1 + min(age, config.freshness_months) / config.freshness_months))
        subset = "missing_or_stale" if missing or age > 0 else "fresh_documented"
        subsets[subset].append((student.student_id, radius))
        uncertainty.append((student.student_id, (("mixture_radius", radius),
            ("missing_current_signal", missing), ("signal_age_months", age),
            ("last_observation_month", last), ("documentation_subset", subset),
            ("estimate_id", student.estimate_id), ("source", "decision_state_estimate"))))
    parameters = (("radius", config.radius),
        ("missingness_multiplier", config.missingness_multiplier),
        ("freshness_months", config.freshness_months),
        ("student_uncertainty", tuple(uncertainty)),
        ("scope", "one_documentation_subset_shift_at_a_time"))
    scenarios = [BeliefScenario("nominal", tuple(nominal), parameters=parameters)]
    if oracle or config.radius == 0 or not any(subsets.values()):
        return tuple(scenarios)
    # Administrative enrollment is known: endpoints are the three live states.
    benefits = [estimate_incremental_benefit(condition, state.months_remaining,
                wait_matrix, programme_matrix) for condition in STATES[:3]]
    endpoints = (("optimistic", max(range(3), key=benefits.__getitem__)),
                 ("pessimistic", min(range(3), key=benefits.__getitem__)))
    for subset, members in subsets.items():
        if not members:
            continue
        radii = dict(members)
        for direction, index in endpoints:
            endpoint = np.eye(4)[index]
            changed = tuple((sid, tuple((1 - radii[sid]) * np.asarray(belief) + radii[sid] * endpoint)
                             if sid in radii else belief) for sid, belief in nominal)
            scenarios.append(BeliefScenario(f"{subset}_{direction}", changed,
                parameters=(*parameters, ("shifted_subset", subset),
                            ("endpoint", STATES[index].value))))
    return tuple(scenarios)


def scenario_candidate_values(state, candidates, scenarios, wait_matrix, programme_matrix):
    """Scenario-by-assignment rollout values, using only WAIT forecasts."""
    if not scenarios or len({s.name for s in scenarios}) != len(scenarios):
        raise ValueError("scenario family must be nonempty with unique names")
    ids = {student.student_id for student in state.students}
    if any(set(dict(scenario.beliefs)) != ids for scenario in scenarios):
        raise ValueError("every scenario must contain exactly the decision students")
    coefficients = {}
    for item in candidates:
        if item.month not in coefficients:
            elapsed = item.month - state.month
            remaining = state.months_remaining - elapsed
            if elapsed < 0 or remaining < 1:
                raise ValueError("scenario candidate lies outside the decision horizon")
            immediate = np.asarray([estimate_incremental_benefit(condition, remaining,
                wait_matrix, programme_matrix) for condition in STATES])
            coefficients[item.month] = np.linalg.matrix_power(wait_matrix, elapsed) @ immediate
    result = []
    for scenario in scenarios:
        beliefs = dict(scenario.beliefs)
        result.append([float(np.asarray(beliefs[item.student_id]) @ coefficients[item.month])
                       for item in candidates])
    return np.asarray(result)

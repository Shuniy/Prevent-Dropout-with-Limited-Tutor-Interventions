"""Versioned weekly synthetic world; never reinterpret monthly scenario fields."""
from dataclasses import dataclass
import math
from pathlib import Path
import tomllib

from .money import amount
from .transition_model import validate_matrix

# Directly assumed weekly probabilities, NOT monthly matrices applied weekly or
# empirically calibrated rates. Withdrawal remains absorbing in both worlds.
WEEKLY_WAIT_V1 = ((.97, .025, .004, .001), (.04, .90, .05, .01),
                  (.01, .04, .91, .04), (0., 0., 0., 1.))
WEEKLY_TUTORING_V1 = ((.98, .017, .002, .001), (.08, .88, .035, .005),
                     (.02, .08, .88, .02), (0., 0., 0., 1.))


@dataclass(frozen=True)
class DeliveryConfig:
    world_mode: str = 'scheduled_weekly'
    contract_version: int = 1
    time_unit: str = 'week'
    transition_version: str = 'synthetic_weekly_v1'
    num_students: int = 12
    num_mentors: int = 2
    horizon_weeks: int = 12
    sessions_required: int = 5
    session_duration_hours: float = 1.
    session_cadence_weeks: int = 1
    acceptance_probability: float = .8
    attendance_probability: float = .85
    delivery_probability: float = .95
    cancellation_probability: float = .02
    terminate_on_withdrawal: bool = True
    rescheduling_policy: str = 'none'
    charging_rule: str = 'per_delivered_session'
    administrative_offer_cost: float = .1
    cost_per_session: float = 1.
    missed_session_cost: float = 0.
    budget: float = 40.
    weekly_mentor_hours: float = 2.
    weekly_session_capacity: int = 2
    max_concurrent_students: int = 2
    fairness_window_weeks: int = 4
    fairness_target: float = .3
    fairness_grouping_attribute: str = 'disadvantage_proxy'
    fairness_allow_shortfall: bool = True
    fairness_small_group_threshold: int = 30
    seed: int = 41
    effect_strength: float = 1.
    weekly_wait_matrix: tuple = WEEKLY_WAIT_V1
    weekly_tutoring_matrix: tuple = WEEKLY_TUTORING_V1
    planner_time_limit: float = 10.

    def __post_init__(self):
        if (self.world_mode != 'scheduled_weekly' or self.time_unit != 'week'
                or self.contract_version != 1 or self.transition_version != 'synthetic_weekly_v1'):
            raise ValueError('weekly delivery requires its versioned weekly world and transitions')
        for name in ('horizon_weeks', 'sessions_required', 'session_cadence_weeks',
                     'weekly_session_capacity', 'max_concurrent_students', 'fairness_small_group_threshold'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f'{name} must be a positive integer')
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError('seed must be a nonnegative integer')
        for name in ('num_students', 'num_mentors'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        if self.fairness_window_weeks != 4:
            raise ValueError('offer fairness requires four actual weeks')
        for name in ('session_duration_hours', 'weekly_mentor_hours', 'planner_time_limit'):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        for name in ('acceptance_probability', 'attendance_probability', 'delivery_probability',
                     'cancellation_probability', 'fairness_target', 'effect_strength'):
            if not math.isfinite(getattr(self, name)) or not 0 <= getattr(self, name) <= 1:
                raise ValueError(f'{name} must be within [0,1]')
        for name in ('administrative_offer_cost', 'cost_per_session', 'missed_session_cost', 'budget'):
            amount(getattr(self, name))
        if self.missed_session_cost > self.cost_per_session:
            raise ValueError('missed charge cannot exceed worst-case session liability')
        if self.rescheduling_policy != 'none' or self.charging_rule != 'per_delivered_session':
            raise ValueError('unsupported rescheduling or charging rule')
        if type(self.terminate_on_withdrawal) is not bool or type(self.fairness_allow_shortfall) is not bool:
            raise ValueError('delivery flags must be boolean')
        if self.fairness_grouping_attribute not in ('disadvantage_proxy', 'sex_source'):
            raise ValueError('unsupported authorized fairness grouping')
        for name in ('weekly_wait_matrix', 'weekly_tutoring_matrix'):
            matrix = validate_matrix(getattr(self, name))
            object.__setattr__(self, name, tuple(tuple(float(v) for v in row) for row in matrix))

    @property
    def treatment_matrix(self):
        import numpy as np
        wait, treatment = map(np.asarray, (self.weekly_wait_matrix, self.weekly_tutoring_matrix))
        return validate_matrix(wait + self.effect_strength * (treatment - wait))

    def schedule(self, start_week):
        return tuple(start_week + n * self.session_cadence_weeks for n in range(self.sessions_required))

    @classmethod
    def load(cls, path):
        with Path(path).open('rb') as stream:
            data = tomllib.load(stream)
        if set(data) != {'delivery'}:
            raise ValueError('weekly configuration must contain only [delivery], without monthly settings')
        return cls(**data['delivery'])


def load_world_config(path):
    with Path(path).open('rb') as stream:
        data = tomllib.load(stream)
    if 'delivery' in data:
        return DeliveryConfig.load(path)
    from .scenario_config import ScenarioConfig
    return ScenarioConfig.load(path)

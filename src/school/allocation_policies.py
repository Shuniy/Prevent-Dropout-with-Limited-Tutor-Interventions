"""Construct a selected policy; orchestration depends only on AllocationPolicy."""

from .allocation_policy import AllocationPolicy
from .baseline_policy import BASELINES, BaselinePolicy
from .constrained_planner import ConstrainedAllocationPlanner
from .fairness_planner import FairnessPlanner
from .transition_model import programme_matrix


DEFAULT_POLICIES = BASELINES
POLICY_NAMES = (*DEFAULT_POLICIES, "terminal_value", "fairness")


def make_policy(name, config) -> AllocationPolicy:
    if name == "terminal_value":
        return ConstrainedAllocationPlanner(
            treatment_matrix=programme_matrix(config.effect_strength),
            time_limit=config.planner_time_limit, failure_mode=config.planner_failure_mode,
        )
    if name == "fairness":
        return FairnessPlanner(
            minimum_access=config.fairness_min_access,
            window_months=config.fairness_window,
            grouping_attribute=config.fairness_grouping_attribute,
            allow_shortfall=config.fairness_allow_shortfall,
            enabled=config.fairness_enabled,
            treatment_matrix=programme_matrix(config.effect_strength),
            time_limit=config.planner_time_limit, failure_mode=config.planner_failure_mode,
        )
    return BaselinePolicy(name, seed=config.seed)

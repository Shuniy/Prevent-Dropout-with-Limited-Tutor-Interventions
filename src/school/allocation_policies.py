"""Construct a selected policy; orchestration depends only on AllocationPolicy."""

from .allocation_policy import AllocationPolicy
from .baseline_policy import BASELINES, BaselinePolicy
from .constrained_planner import ConstrainedAllocationPlanner
from .fairness_planner import FairnessPlanner
from .transition_model import programme_matrix


DEFAULT_POLICIES = (*BASELINES, "terminal_value")
POLICY_NAMES = (*DEFAULT_POLICIES, "fairness")


def make_policy(name, config) -> AllocationPolicy:
    if name == "terminal_value":
        return ConstrainedAllocationPlanner(
            treatment_matrix=programme_matrix(config.effect_strength)
        )
    if name == "fairness":
        return FairnessPlanner(
            minimum_access=config.fairness_min_access,
            window_months=config.fairness_window,
            treatment_matrix=programme_matrix(config.effect_strength),
        )
    return BaselinePolicy(name, seed=config.seed)

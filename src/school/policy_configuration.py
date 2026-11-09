"""Explicit versioned policy reconstruction; never infer a type from its name."""
from dataclasses import asdict

from .baseline_policy import BaselinePolicy
from .constrained_planner import ConstrainedAllocationPlanner
from .fairness_planner import FairnessPlanner
from .robust_fair_planner import FairRobustPlanner
from .uncertainty_scenarios import UncertaintyScenarioConfig


POLICY_TYPES = {BaselinePolicy: 'baseline', ConstrainedAllocationPlanner: 'resource',
                FairnessPlanner: 'fair_point', FairRobustPlanner: 'fair_robust'}


def serialize_policy(policy):
    if type(policy) not in POLICY_TYPES:
        raise ValueError('unsupported policy implementation for exact reconstruction')
    if type(policy) is BaselinePolicy:
        parameters = {'name': policy.name, 'seed': policy.seed}
    else:
        parameters = {'wait_matrix': policy.wait_matrix.tolist(),
            'treatment_matrix': policy.programme_matrix.tolist(),
            'time_limit': policy.time_limit, 'failure_mode': policy.failure_mode}
        if isinstance(policy, FairnessPlanner):
            parameters.update({k: getattr(policy, k) for k in
                ('minimum_access', 'window_months', 'grouping_attribute', 'allow_shortfall', 'enabled')})
        if type(policy) is FairRobustPlanner:
            parameters['uncertainty_config'] = asdict(policy.uncertainty_config)
    return {'version': 1, 'type': POLICY_TYPES[type(policy)], 'parameters': parameters,
            'effective_settings': dict(getattr(policy, 'settings', ()))}


def reconstruct_policy(record):
    if record.get('version') != 1 or record.get('type') not in POLICY_TYPES.values():
        raise ValueError('unsupported policy reconstruction version/type')
    cls = next(cls for cls, name in POLICY_TYPES.items() if name == record['type'])
    parameters = dict(record['parameters'])
    if cls is FairRobustPlanner:
        parameters['uncertainty_config'] = UncertaintyScenarioConfig(**parameters['uncertainty_config'])
    policy = cls(**parameters)
    if serialize_policy(policy) != record:
        raise ValueError('incomplete or inconsistent policy configuration')
    return policy

"""School's monthly CMDP cycle, independent of how a policy plans assignments."""

from .allocation_policy import AllocationPolicy
from .cmdp_environment import CMDPEnvironment
from .fairness_audit import freeze_cohorts


class CMDPSimulation:
    """Coordinate one synthetic episode and retain frozen audit cohorts."""

    def __init__(self, environment: CMDPEnvironment, policy: AllocationPolicy):
        self.environment = environment
        self.policy = policy
        self.initial_state = environment.observe()
        self.initial_cohorts = freeze_cohorts(self.initial_state)
        self.window_cohorts = []

    def run(self):
        if self.environment.records:
            raise ValueError("CMDPSimulation requires a fresh environment")
        window_months = self.environment.config.fairness_window
        while not self.environment.done:
            state = self.environment.observe()
            if (state.month - 1) % window_months == 0:
                self.window_cohorts.append((state.month, freeze_cohorts(state)))
            # The policy receives a snapshot, never the environment or future draws.
            allocation = self.policy.plan(state)
            self.environment.step(allocation)
        return self

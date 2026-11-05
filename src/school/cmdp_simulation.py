"""School's monthly CMDP cycle, independent of how a policy plans assignments."""

from .allocation_policy import AllocationPolicy
from .cmdp_environment import CMDPEnvironment
from .fairness_audit import freeze_cohorts
from .fairness_window import FairnessWindow


class CMDPSimulation:
    """Coordinate one synthetic episode and retain frozen audit cohorts."""

    def __init__(self, environment: CMDPEnvironment, policy: AllocationPolicy):
        self.environment = environment
        self.policy = policy
        self.initial_state = environment.observe()
        self.initial_cohorts = freeze_cohorts(
            self.initial_state, environment.config.fairness_grouping_attribute,
            end_month=environment.config.horizon)
        self.window_cohorts = []
        self.fairness_monthly = []
        self.fairness_windows = []

    def run(self):
        if self.environment.records:
            raise ValueError("CMDPSimulation requires a fresh environment")
        window_months = self.environment.config.fairness_window
        while not self.environment.done:
            state = self.environment.observe()
            if (state.month - 1) % window_months == 0:
                window = FairnessWindow.initialize(
                    state, window_months=window_months,
                    target=self.environment.config.fairness_min_access,
                    attribute=self.environment.config.fairness_grouping_attribute)
                self.fairness_windows.append(window)
                self.window_cohorts.append((state.month, window.cohorts))
            window.update(state)
            before = window.rows()
            # The policy receives a snapshot, never the environment or future draws.
            allocation = self.policy.plan(state)
            self.environment.step(allocation)
            window.update(self.environment.observe())
            projected = {a.student_id for a in allocation.tentative_assignments}
            for previous, after in zip(before, window.rows(projected)):
                self.fairness_monthly.append({
                    **after, "month": state.month,
                    "covered_before": previous["covered_before"],
                    "actionable_count": previous["actionable_count"],
                    "outstanding_before": previous["outstanding_before"],
                    "newly_covered": after["covered_before"] - previous["covered_before"],
                    "actual_covered": after["covered_before"],
                    "actual_shortfall": after["outstanding_before"],
                    "excluded_no_compatible_count": len(window.excluded_no_compatible_ids),
                })
        return self

"""Optional eager coverage heuristic with frozen, multi-month window accounting.

This planner minimizes residual window shortfall using current feasible offers,
then maximizes retention benefit at that shortfall. It does not forecast future
withdrawals or solve an optimal stochastic multi-month fairness schedule.
"""

from dataclasses import replace
import time

import numpy as np

from .allocation_result import AllocationResult
from .constrained_planner import ConstrainedAllocationPlanner, checked_solution
from .constraints import candidate_assignments, validate_allocation
from .fairness_audit import coverage_shortfall, freeze_cohorts
from .optimization import resource_constraints, solve_milp
from .retention_value import estimate_all_student_benefits


def feasible_vector(result, rows, lower, upper):
    vector = getattr(result, "x", None)
    if result.status not in (0, 1) or vector is None:
        return False
    vector = np.asarray(vector)
    # HiGHS may return sub-micro-unit residuals in continuous shortfall rows.
    # Resource feasibility and realized coverage are separately checked after
    # rounding binary assignments; this tolerance never relaxes those checks.
    tolerance = 1e-6
    if len(vector) != rows.shape[1] or not np.isfinite(vector).all() or np.any(vector < -tolerance):
        return False
    values = rows @ vector
    return bool(np.all(values >= lower - tolerance) and np.all(values <= upper + tolerance))


class FairnessPlanner(ConstrainedAllocationPlanner):
    """Each nonempty group has weight 1/N; overlapping audit axes both count.

    At window start, freeze eligible (enrolled, unused) students by current
    available condition, fixed support need, source sex and disadvantage proxy.
    Later withdrawals remain in the denominator. Prior offers remain covered.
    Eager coverage can spend the episode budget before the window ends.
    """

    def __init__(self, *, minimum_access=0.2, window_months=4, **kwargs):
        super().__init__(**kwargs)
        if not np.isfinite(minimum_access) or not 0 <= minimum_access <= 1:
            raise ValueError("minimum_access must be within [0, 1]")
        if type(window_months) is not int or window_months < 1:
            raise ValueError("window_months must be a positive integer")
        self.minimum_access = minimum_access
        self.window_months = window_months
        self._start = None
        self._cohorts = ()

    def plan(self, state):
        started = time.perf_counter()
        start = ((state.month - 1) // self.window_months) * self.window_months + 1
        if self._start != start:
            if state.month != start:
                raise ValueError(
                    "fairness planner must observe the start of each assessment window"
                )
            self._start = start
            self._cohorts = freeze_cohorts(state)
        prior_offers = {
            student.student_id
            for student in state.students
            if any(start <= month <= state.month for month in student.programme_months)
        }
        candidates = candidate_assignments(state)
        if not candidates or not self._cohorts:
            return AllocationResult(
                status="fairness_no_candidates",
                runtime_seconds=time.perf_counter() - started,
                fairness_shortfall=coverage_shortfall(
                    self._cohorts, prior_offers, self.minimum_access
                ),
            )
        benefits = estimate_all_student_benefits(state, self.wait_matrix, self.programme_matrix)
        resources, resource_upper = resource_constraints(state, candidates)
        binary_count = len(candidates)
        group_count = len(self._cohorts)
        rows = np.zeros((len(resources) + group_count, binary_count + group_count))
        rows[: len(resources), :binary_count] = resources
        lower = np.full(len(rows), -np.inf)
        upper = np.full(len(rows), np.inf)
        upper[: len(resources)] = resource_upper
        weights = np.zeros(binary_count + group_count)
        for index, cohort in enumerate(self._cohorts):
            members = set(cohort.student_ids)
            row = len(resources) + index
            rows[row, :binary_count] = [int(item.student_id in members) for item in candidates]
            rows[row, binary_count + index] = 1
            # offers_so_far_g + sum_(i in E_g,m) x[i,m] + xi_g >= q * |E_g|.
            lower[row] = self.minimum_access * len(members) - len(members & prior_offers)
            weights[binary_count + index] = 1 / len(members)
        # Stage 1: minimize sum_g xi_g / |E_g| with hard resources unchanged.
        first = solve_milp(
            weights, rows, lower, upper, binary_count=binary_count, time_limit=self.time_limit
        )
        if not feasible_vector(first, rows, lower, upper):
            return AllocationResult(
                status="fairness_solver_wait_fallback",
                runtime_seconds=time.perf_counter() - started,
                message=str(first.message),
                fairness_shortfall=coverage_shortfall(
                    self._cohorts, prior_offers, self.minimum_access
                ),
            )
        first_allocation = checked_solution(
            state, candidates, benefits, first, time.perf_counter() - started
        )
        if "fallback" in first_allocation.status:
            return replace(
                first_allocation,
                fairness_shortfall=coverage_shortfall(
                    self._cohorts, prior_offers, self.minimum_access
                ),
            )
        best_shortfall = coverage_shortfall(
            self._cohorts,
            prior_offers | {item.student_id for item in first_allocation.assignments},
            self.minimum_access,
        )
        if first.status != 0:
            # A time-limited incumbent does not prove minimum fairness shortfall.
            return replace(
                first_allocation,
                status="fairness_feasible_limit",
                fairness_shortfall=best_shortfall,
                optimality_gap=None,
                objective_bound=None,
                message="Fairness-stage time limit: minimum shortfall not proven. "
                + str(first.message),
            )
        # Stage 2: fix minimum normalized shortfall, maximize sum Delta_i * x[i,m].
        rows = np.vstack([rows, weights])
        lower = np.append(lower, -np.inf)
        upper = np.append(upper, best_shortfall + 1e-8)
        objective = np.zeros(binary_count + group_count)
        objective[:binary_count] = [-benefits[item.student_id] for item in candidates]
        second = solve_milp(
            objective, rows, lower, upper, binary_count=binary_count, time_limit=self.time_limit
        )
        allocation = checked_solution(
            state, candidates, benefits, second, time.perf_counter() - started
        )
        offered = prior_offers | {item.student_id for item in allocation.assignments}
        shortfall = coverage_shortfall(self._cohorts, offered, self.minimum_access)
        if (
            not feasible_vector(second, rows, lower, upper)
            or "fallback" in allocation.status
            or shortfall > best_shortfall + 1e-7
        ):
            return replace(
                first_allocation,
                status="fairness_retention_fallback",
                fairness_shortfall=best_shortfall,
                runtime_seconds=time.perf_counter() - started,
                optimality_gap=None,
                objective_bound=None,
                message="Retention stage failed; retained validated fairness-stage incumbent. "
                + str(second.message),
            )
        validate_allocation(state, allocation.assignments)
        return replace(
            allocation, fairness_shortfall=shortfall, status="fairness_" + allocation.status
        )

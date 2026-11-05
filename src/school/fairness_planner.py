"""Approximate rolling-window coverage MILP; future programmes are never committed."""

from dataclasses import replace
import time

import numpy as np
import scipy

from .allocation_result import AllocationResult
from .constrained_planner import ConstrainedAllocationPlanner
from .constraints import validate_allocation
from .fairness_audit import ATTRIBUTES, coverage_shortfall, required_access
from .fairness_window import FairnessWindow
from .optimization import solve_milp
from .retention_value import BENEFIT_ESTIMATOR_VERSION, estimate_all_student_benefits
from .window_optimization import validate_schedule, window_model


def feasible_vector(result, rows, lower, upper, *, integer_count=None, variable_lower=None):
    vector = getattr(result, "x", None)
    if result.status not in (0, 1) or vector is None:
        return False
    vector = np.asarray(vector)
    tolerance = 1e-6
    integer_count = len(vector) if integer_count is None else integer_count
    bounds_lower = np.zeros(len(vector)) if variable_lower is None else variable_lower
    if (len(vector) != rows.shape[1] or not np.isfinite(vector).all()
            or np.any(vector < bounds_lower - tolerance)
            or np.any(abs(vector[:integer_count] - np.rint(vector[:integer_count])) > tolerance)):
        return False
    checked = vector.copy()
    checked[:integer_count] = np.rint(checked[:integer_count])
    values = rows @ checked
    return bool(np.all(values >= lower - tolerance) and np.all(values <= upper + tolerance))


class FairnessPlanner(ConstrainedAllocationPlanner):
    """Minimize sum xi/N (equal cell weights), retention, cost, canonical bits.

    Forecasts use currently eligible potential candidates and announced mentor
    calendars. WAIT projections value future treatments without observing future
    student states. Coverage forecasts optimistically assume continued enrollment;
    realized admissions alone enter the persistent ledger.
    """

    VERSION = "fairness_window_milp_v1"
    FAIRNESS_TOLERANCE = 1e-8

    def __init__(self, *, minimum_access=0.3, window_months=4,
                 grouping_attribute="disadvantage_proxy", allow_shortfall=True,
                 enabled=True, **kwargs):
        super().__init__(**kwargs)
        if not np.isfinite(minimum_access) or not 0 <= minimum_access <= 1:
            raise ValueError("minimum_access must be within [0, 1]")
        if type(window_months) is not int or window_months < 1:
            raise ValueError("window_months must be a positive integer")
        if grouping_attribute not in ATTRIBUTES:
            raise ValueError("select one authorized audit attribute")
        if type(allow_shortfall) is not bool or type(enabled) is not bool:
            raise ValueError("fairness mode flags must be boolean")
        self.minimum_access = minimum_access
        self.window_months = window_months
        self.grouping_attribute = grouping_attribute
        self.allow_shortfall = allow_shortfall
        self.enabled = enabled
        self.window = None
        self.windows = []

    @property
    def settings(self):
        return (*super().settings, ("fairness_tolerance", self.FAIRNESS_TOLERANCE),
                ("grouping_attribute", self.grouping_attribute),
                ("allow_shortfall", self.allow_shortfall),
                ("projection", "announced_calendar_current_candidates_wait_values"))

    def plan(self, state):
        state.validate_estimates()
        started = time.perf_counter()
        start = ((state.month - 1) // self.window_months) * self.window_months + 1
        if self.window is None or self.window.start != start:
            self.window = FairnessWindow.initialize(
                state, window_months=self.window_months, target=self.minimum_access,
                attribute=self.grouping_attribute)
            self.windows.append(self.window)
        self.window.update(state)
        window = self.window
        prior = window.recipients

        def finish(allocation, schedule=(), complete=False, status=None):
            admitted = {a.student_id for a in allocation.assignments}
            planned = {a.student_id for a in schedule}
            projected = coverage_shortfall(window.cohorts, prior | planned, self.minimum_access)
            realized = coverage_shortfall(window.cohorts, prior | admitted, self.minimum_access)
            if "fallback" in (status or allocation.status) and self.failure_mode == "raise":
                raise RuntimeError((status or allocation.status) + ": " + allocation.message)
            return replace(allocation, status=status or allocation.status,
                           runtime_seconds=time.perf_counter() - started,
                           fairness_shortfall=projected,
                           projected_fairness_shortfall=projected,
                           realized_fairness_shortfall=realized,
                           tentative_assignments=tuple(schedule),
                           projected_coverage=tuple(tuple(row.items()) for row in window.rows(planned)),
                           fairness_window_start=window.start, fairness_window_end=window.end,
                           fairness_mode=("disabled" if not self.enabled or self.minimum_access == 0
                                          else "shortfall_aware" if self.allow_shortfall else "strict"),
                           projected_fairness_feasible=projected <= self.FAIRNESS_TOLERANCE,
                           lexicographic_complete=complete,
                           eligible_student_count=sum(s.eligible for s in state.students),
                           current_month=state.month, remaining_budget=state.remaining_budget,
                           months_remaining=state.months_remaining,
                           benefit_estimator_version=BENEFIT_ESTIMATOR_VERSION,
                           planner_version=self.VERSION, solver_version=scipy.__version__,
                           solver_settings=self.settings)

        # Exact Step 3 objective and tie-breaking at q=0; no future pressure.
        if not self.enabled or self.minimum_access == 0:
            allocation = super().plan(state)
            return finish(allocation, allocation.assignments, allocation.lexicographic_complete)

        candidates, resources, resource_upper, values, costs, states = window_model(
            state, window.end, self.wait_matrix, self.programme_matrix)
        count = len(candidates)
        cohorts = tuple(c for c in window.cohorts if c.student_ids)
        if not count:
            shortfall = coverage_shortfall(cohorts, prior, self.minimum_access)
            status = "fairness_infeasible" if shortfall and not self.allow_shortfall else "fairness_no_candidates"
            return finish(AllocationResult(status=status, message="No actionable compatible, affordable slots remain."),
                          complete=True)
        slack_count = len(cohorts) if self.allow_shortfall else 0
        size = count + slack_count
        rows = np.zeros((len(resources) + len(cohorts), size))
        rows[:len(resources), :count] = resources
        lower = np.full(len(rows), -np.inf)
        upper = np.full(len(rows), np.inf)
        upper[:len(resources)] = resource_upper
        weights = np.zeros(size)
        for index, cohort in enumerate(cohorts):
            ids = set(cohort.student_ids)
            row = len(resources) + index
            rows[row, :count] = [int(a.student_id in ids) for a in candidates]
            lower[row] = required_access(self.minimum_access, len(ids)) - len(ids & prior)
            if self.allow_shortfall:
                rows[row, count + index] = 1
                weights[count + index] = 1 / len(ids)

        def solve(objective):
            remaining = self.time_limit - (time.perf_counter() - started)
            if remaining <= 0:
                raise TimeoutError("total monthly solve time limit reached")
            result = solve_milp(objective, rows, lower, upper, binary_count=count,
                                integer_count=size, time_limit=remaining)
            if not feasible_vector(result, rows, lower, upper):
                return result, None
            vector = np.rint(result.x)
            if np.any(vector[:count] > 1):
                return result, None
            selected = tuple(a for a, bit in zip(candidates, vector[:count]) if bit)
            validate_schedule(state, states, selected)
            return result, vector

        try:
            first, vector = solve(weights)
        except Exception as error:
            return finish(AllocationResult(status="fairness_solver_wait_fallback", message=repr(error)))
        if vector is None:
            status = "fairness_infeasible" if first.status == 2 and not self.allow_shortfall else "fairness_solver_wait_fallback"
            return finish(AllocationResult(status=status, message=str(first.message)))
        best = vector
        best_shortfall = float(weights @ best)
        if self.allow_shortfall:
            rows = np.vstack([rows, weights])
            lower = np.append(lower, -np.inf)
            upper = np.append(upper, best_shortfall + self.FAIRNESS_TOLERANCE)
        complete = first.status == 0
        message = str(first.message)
        status = "fairness_optimal" if complete else "fairness_feasible_limit"
        benefit_row = np.pad(values, (0, slack_count))
        cost_row = np.pad(costs, (0, slack_count))
        objectives = [("retention", -benefit_row), ("cost", cost_row)]
        # Canonical month, student, mentor bits: unique without epsilon bonuses.
        for offset in range(0, count, self.TIE_BLOCK_SIZE):
            bit_row = np.zeros(size)
            block = min(count - offset, self.TIE_BLOCK_SIZE)
            bit_row[offset:offset + block] = [2 ** p for p in reversed(range(block))]
            objectives.append(("tie", -bit_row))
        if complete:
            for stage, objective in objectives:
                try:
                    result, proposed = solve(objective)
                    if (proposed is None or result.status != 0
                            or float(weights @ proposed) > best_shortfall + self.FAIRNESS_TOLERANCE
                            or np.any(rows @ proposed < lower - self.OBJECTIVE_TOLERANCE)
                            or np.any(rows @ proposed > upper + self.OBJECTIVE_TOLERANCE)):
                        complete = False
                        status = "fairness_" + stage + "_incomplete"
                        message = str(result.message)
                        break
                    best = proposed
                except Exception as error:
                    complete = False
                    status = "fairness_" + stage + "_limit_or_error"
                    message = repr(error)
                    break
                achieved = float(objective @ best)
                rows = np.vstack([rows, objective])
                lower = np.append(lower, -np.inf)
                upper = np.append(upper, achieved + (self.OBJECTIVE_TOLERANCE if stage == "retention" else 0))
        schedule = tuple(a for a, bit in zip(candidates, best[:count]) if bit)
        current = tuple(a for a in schedule if a.month == state.month)
        validate_allocation(state, current)
        immediate = estimate_all_student_benefits(state, self.wait_matrix, self.programme_matrix)
        allocation = AllocationResult(current, status=status,
                                      objective=sum(immediate[a.student_id] for a in current),
                                      message=message, candidate_pair_count=count,
                                      decision_variable_count=size,
                                      projected_total_benefit=float(values @ best[:count]))
        return finish(allocation, schedule, complete)

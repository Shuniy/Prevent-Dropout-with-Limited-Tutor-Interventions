"""Receding-horizon terminal-value allocation heuristic; not full CMDP optimality."""

import time
from dataclasses import replace

import numpy as np
import scipy

from .allocation_result import AllocationResult
from .constraints import candidate_assignments, validate_allocation
from .optimization import resource_constraints, solve_milp
from .retention_value import BENEFIT_ESTIMATOR_VERSION, estimate_all_student_benefits
from .money import budget_amount, integer_costs, programme_cost
from .transition_model import P_WAIT, programme_matrix, validate_matrix


def checked_solution(state, candidates, benefits, result, runtime):
    """Accept only a finite integral incumbent that independently passes checks."""
    statuses = {0: "optimal", 1: "limit", 2: "infeasible", 3: "unbounded", 4: "numerical_failure"}
    status = statuses.get(result.status, "solver_error")
    vector = getattr(result, "x", None)
    if result.status not in (0, 1) or vector is None:
        return AllocationResult(
            status=status + "_wait_fallback", runtime_seconds=runtime, message=str(result.message)
        )
    vector = np.asarray(vector[: len(candidates)])
    if (
        len(vector) != len(candidates)
        or not np.isfinite(vector).all()
        or np.any(np.abs(vector - np.rint(vector)) > 1e-6)
        or np.any(vector < -1e-6)
        or np.any(vector > 1 + 1e-6)
    ):
        return AllocationResult(
            status="invalid_incumbent_wait_fallback",
            runtime_seconds=runtime,
            message="solver returned non-binary assignments",
        )
    selected = tuple(item for item, value in zip(candidates, vector) if value > 0.5)
    try:
        validate_allocation(state, selected)
    except ValueError as error:
        return AllocationResult(
            status="invalid_incumbent_wait_fallback", runtime_seconds=runtime, message=str(error)
        )
    objective = sum(benefits[item.student_id] for item in selected)
    gap = getattr(result, "mip_gap", None)
    bound = getattr(result, "mip_dual_bound", None)
    return AllocationResult(
        selected,
        "optimal" if result.status == 0 else "feasible_limit",
        objective,
        runtime,
        float(gap) if gap is not None else None,
        -float(bound) if bound is not None else None,
        str(result.message),
    )


class ConstrainedAllocationPlanner:
    """Retention, then exact expenditure, then lexicographic sorted pair bits.

    Twenty-bit blocks provide a unique canonical assignment without exponential
    floating-point weights across the entire cohort. Nonpositive benefits are
    excluded. A primary-optimal incumbent is retained if refinement times out;
    lexicographic_complete then remains false and status records the limitation.
    """

    VERSION = "terminal_retention_milp_v2"
    OBJECTIVE_TOLERANCE = 1e-10
    TIE_BLOCK_SIZE = 20

    def __init__(self, *, wait_matrix=P_WAIT, treatment_matrix=None, time_limit=10.0,
                 failure_mode="wait"):
        if not np.isfinite(time_limit) or time_limit <= 0:
            raise ValueError("solver time_limit must be positive and finite")
        self.wait_matrix = validate_matrix(wait_matrix)
        self.programme_matrix = validate_matrix(
            programme_matrix() if treatment_matrix is None else treatment_matrix
        )
        self.time_limit = time_limit
        if failure_mode not in ("wait", "raise"):
            raise ValueError("failure_mode must be wait or raise")
        self.failure_mode = failure_mode

    @property
    def settings(self):
        return (("solver", "scipy.optimize.milp/HiGHS"), ("time_limit", self.time_limit),
                ("mip_rel_gap", 0.0), ("objective_tolerance", self.OBJECTIVE_TOLERANCE),
                ("tie_block_size", self.TIE_BLOCK_SIZE), ("failure_mode", self.failure_mode))

    def plan(self, state):
        state.validate_estimates()
        started = time.perf_counter()
        candidates = candidate_assignments(state)

        def finish(allocation, variable_count=0):
            if "fallback" in allocation.status and self.failure_mode == "raise":
                raise RuntimeError(allocation.status + ": " + allocation.message)
            return replace(
                allocation, runtime_seconds=time.perf_counter() - started,
                eligible_student_count=sum(student.eligible for student in state.students),
                candidate_pair_count=len(candidates), decision_variable_count=variable_count,
                available_mentor_count=sum(m.admissions > 0 and m.appointments >= 5
                                           for m in state.mentors),
                remaining_budget=state.remaining_budget, current_month=state.month,
                months_remaining=state.months_remaining,
                benefit_estimator_version=BENEFIT_ESTIMATOR_VERSION,
                planner_version=self.VERSION, solver_version=scipy.__version__,
                solver_settings=self.settings,
                validation_failures=int("invalid_incumbent" in allocation.status),
            )

        if not candidates:
            return finish(AllocationResult(status="no_candidates", lexicographic_complete=True))
        benefits = estimate_all_student_benefits(state, self.wait_matrix, self.programme_matrix)
        positive = tuple(item for item in candidates if benefits[item.student_id] > 0)
        if not positive:
            return finish(AllocationResult(status="zero_benefit", lexicographic_complete=True))
        rows, upper = resource_constraints(state, positive)
        lower = np.full(len(upper), -np.inf)
        count = len(positive)

        def solve(objective):
            remaining = self.time_limit - (time.perf_counter() - started)
            if remaining <= 0:
                raise TimeoutError("total monthly solve time limit reached")
            result = solve_milp(objective, rows, lower, upper, binary_count=count,
                                time_limit=remaining)
            return checked_solution(state, positive, benefits, result,
                                    time.perf_counter() - started)

        # SciPy minimizes: c[i,m] = -Delta_i maximizes sum_(i,m) Delta_i * x[i,m].
        values = np.array([benefits[item.student_id] for item in positive])
        try:
            primary = solve(-values)
        except Exception as error:
            return finish(AllocationResult(status="unexpected_error_wait_fallback",
                                          message=repr(error)), count)
        if primary.status != "optimal":
            return finish(primary, count)
        allocation = primary
        # Constrain benefit directly; there are no epsilon selection bonuses.
        rows = np.vstack([rows, values])
        lower = np.append(lower, primary.objective - self.OBJECTIVE_TOLERANCE)
        upper = np.append(upper, np.inf)

        def refine(objective, stage):
            nonlocal allocation
            try:
                proposed = solve(objective)
            except Exception as error:
                return replace(allocation, status=stage + "_limit_or_error",
                               message=repr(error), lexicographic_complete=False)
            vector = np.array([int(item in proposed.assignments) for item in positive])
            if (proposed.status != "optimal"
                    or proposed.objective < primary.objective - self.OBJECTIVE_TOLERANCE
                    or np.any(rows @ vector < lower - self.OBJECTIVE_TOLERANCE)
                    or np.any(rows @ vector > upper + self.OBJECTIVE_TOLERANCE)):
                return replace(allocation, status=stage + "_incomplete",
                               message=proposed.status + ": " + proposed.message)
            allocation = replace(proposed, optimality_gap=primary.optimality_gap,
                                 objective_bound=primary.objective_bound)
            return None

        prices = {mentor.mentor_id: mentor.cost_per_appointment for mentor in state.mentors}
        costs, _ = integer_costs([programme_cost(prices[item.mentor_id]) for item in positive],
                                 budget_amount(state))
        incomplete = refine(costs, "cost_refinement")
        if incomplete is not None:
            return finish(incomplete, count)
        best_cost = sum(cost for item, cost in zip(positive, costs)
                        if item in allocation.assignments)
        rows = np.vstack([rows, costs])
        lower = np.append(lower, best_cost)
        upper = np.append(upper, best_cost)
        for start in range(0, count, self.TIE_BLOCK_SIZE):
            size = min(self.TIE_BLOCK_SIZE, count - start)
            weights = np.zeros(count)
            weights[start:start + size] = [2 ** power for power in reversed(range(size))]
            incomplete = refine(-weights, "tie_refinement")
            if incomplete is not None:
                return finish(incomplete, count)
            selected = np.array([int(item in allocation.assignments) for item in positive])
            best_bits = float(weights @ selected)
            rows = np.vstack([rows, weights])
            lower = np.append(lower, best_bits)
            upper = np.append(upper, best_bits)
        validate_allocation(state, allocation.assignments)
        return finish(replace(allocation, lexicographic_complete=True), count)

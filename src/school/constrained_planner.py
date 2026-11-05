"""Receding-horizon terminal-value allocation heuristic; not full CMDP optimality."""

import time

import numpy as np

from .allocation_result import AllocationResult
from .constraints import candidate_assignments, validate_allocation
from .optimization import resource_constraints, solve_milp
from .retention_value import estimate_all_student_benefits
from .transition_model import P_WAIT, programme_matrix, validate_matrix


def checked_solution(state, candidates, benefits, result, runtime):
    """Accept only a finite integral incumbent that independently passes checks."""
    statuses = {0: "optimal", 1: "limit", 2: "infeasible", 3: "unbounded", 4: "solver_error"}
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
    def __init__(self, *, wait_matrix=P_WAIT, treatment_matrix=None, time_limit=10.0):
        if not np.isfinite(time_limit) or time_limit <= 0:
            raise ValueError("solver time_limit must be positive and finite")
        self.wait_matrix = validate_matrix(wait_matrix)
        self.programme_matrix = validate_matrix(
            programme_matrix() if treatment_matrix is None else treatment_matrix
        )
        self.time_limit = time_limit

    def plan(self, state):
        started = time.perf_counter()
        candidates = candidate_assignments(state)
        if not candidates:
            return AllocationResult(status="no_candidates")
        benefits = estimate_all_student_benefits(state, self.wait_matrix, self.programme_matrix)
        if max(benefits.values(), default=0) <= 1e-12:
            return AllocationResult(status="zero_benefit")
        rows, upper = resource_constraints(state, candidates)
        # SciPy minimizes: c[i,m] = -Delta_i maximizes sum_(i,m) Delta_i * x[i,m].
        objective = [-benefits[item.student_id] for item in candidates]
        result = solve_milp(
            objective,
            rows,
            np.full(len(upper), -np.inf),
            upper,
            binary_count=len(candidates),
            time_limit=self.time_limit,
        )
        allocation = checked_solution(
            state, candidates, benefits, result, time.perf_counter() - started
        )
        validate_allocation(state, allocation.assignments)
        return allocation

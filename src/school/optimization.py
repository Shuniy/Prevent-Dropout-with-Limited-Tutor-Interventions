"""Small transparent SciPy MILP helpers. Constraints apply to realized admissions."""

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix
from .money import budget_amount, integer_costs, programme_cost


def resource_constraints(state, candidates):
    """Return A, upper with A @ x <= upper for binary assignment variables."""
    rows = []
    upper = []
    for student in sorted(state.students, key=lambda item: item.student_id):
        row = [int(item.student_id == student.student_id) for item in candidates]
        if any(row):
            # sum_m x[i,m,t] <= 1.
            rows.append(row)
            upper.append(1)
    for mentor in sorted(state.mentors, key=lambda item: item.mentor_id):
        row = [int(item.mentor_id == mentor.mentor_id) for item in candidates]
        if any(row):
            # sum_i x[i,m,t] <= C[m,t]; 5 * sum_i x[i,m,t] <= A[m,t].
            rows.extend([row, [5 * value for value in row]])
            upper.extend([mentor.admissions, mentor.appointments])
    # sum_(i,m) 5 * c[m] * x[i,m,t] <= remaining episode budget.
    prices = {mentor.mentor_id: mentor.cost_per_appointment for mentor in state.mentors}
    costs, budget = integer_costs(
        [programme_cost(prices[item.mentor_id]) for item in candidates], budget_amount(state))
    rows.append(costs)
    upper.append(budget)
    return np.array(rows, dtype=float), np.array(upper, dtype=float)


def solve_milp(objective, rows, lower, upper, *, binary_count, time_limit):
    count = len(objective)
    bounds_upper = np.full(count, np.inf)
    bounds_upper[:binary_count] = 1
    integrality = np.zeros(count)
    integrality[:binary_count] = 1
    return milp(
        np.asarray(objective, dtype=float),
        integrality=integrality,
        bounds=Bounds(np.zeros(count), bounds_upper),
        constraints=LinearConstraint(csc_matrix(rows), lower, upper),
        options={"time_limit": time_limit, "mip_rel_gap": 0.0},
    )

"""Time-indexed extension of the same candidate, resource and validation rules."""

from dataclasses import replace

import numpy as np

from .constraints import candidate_assignments, validate_allocation
from .money import amount, budget_amount, integer_costs, programme_cost
from .optimization import resource_constraints
from .retention_value import estimate_all_student_benefits, estimate_incremental_benefit
from .student_condition import STATES


def projected_states(state, end):
    calendar = dict(state.known_mentor_schedule)
    return tuple(replace(state, month=month, months_remaining=state.months_remaining - month + state.month,
                         mentors=state.mentors if month == state.month else calendar.get(month, ()))
                 for month in range(state.month, end + 1))


def window_model(state, end, wait, programme):
    states = projected_states(state, end)
    candidates = tuple(item for snapshot in states for item in candidate_assignments(snapshot))
    count = len(candidates)
    rows, upper = [], []
    offset = 0
    for snapshot in states:
        selected = tuple(item for item in candidates if item.month == snapshot.month)
        if not selected:
            continue
        local_rows, local_upper = resource_constraints(snapshot, selected)
        # Per-month rows share the Step 3 model. Replace only its monthly budget
        # row with a single remaining-episode budget across all tentative months.
        for local, limit in zip(local_rows[:-1], local_upper[:-1]):
            row = np.zeros(count)
            row[offset:offset + len(selected)] = local
            rows.append(row)
            upper.append(limit)
        offset += len(selected)
    for student in state.students:
        row = np.array([int(item.student_id == student.student_id) for item in candidates])
        if row.any():
            rows.append(row)
            upper.append(1)
    prices = {(snapshot.month, mentor.mentor_id): mentor.cost_per_appointment
              for snapshot in states for mentor in snapshot.mentors}
    costs, budget = integer_costs(
        [programme_cost(prices[(item.month, item.mentor_id)]) for item in candidates],
        budget_amount(state))
    rows.append(np.asarray(costs))
    upper.append(budget)
    immediate = estimate_all_student_benefits(state, wait, programme)
    students = {s.student_id: s for s in state.students}
    values = []
    cached = {}
    for item in candidates:
        elapsed = item.month - state.month
        student = students[item.student_id]
        if not elapsed:
            values.append(immediate[item.student_id])
            continue
        key = (student.condition, student.condition_probabilities, elapsed)
        if key not in cached:
            # WAIT-only unconditional distribution, including absorbing withdrawal.
            if student.condition_probabilities:
                distribution = np.asarray(student.condition_probabilities) @ np.linalg.matrix_power(wait, elapsed)
            else:
                distribution = np.linalg.matrix_power(wait, elapsed)[STATES.index(student.condition)]
            by_condition = [estimate_incremental_benefit(condition, state.months_remaining - elapsed,
                                                        wait, programme) for condition in STATES]
            cached[key] = float(distribution @ by_condition)
        values.append(cached[key])
    return candidates, np.asarray(rows), np.asarray(upper), np.asarray(values), np.asarray(costs), states


def validate_schedule(state, states, assignments):
    """Independent exact monetary and uniqueness checks, then monthly validator."""
    ids = [a.student_id for a in assignments]
    if len(ids) != len(set(ids)):
        raise ValueError("tentative schedule repeats a student")
    prices = {(snapshot.month, mentor.mentor_id): mentor.cost_per_appointment
              for snapshot in states for mentor in snapshot.mentors}
    if sum((programme_cost(prices[(a.month, a.mentor_id)]) for a in assignments), amount(0)) > budget_amount(state):
        raise ValueError("tentative schedule exceeds remaining episode budget")
    if any(a.month not in {s.month for s in states} for a in assignments):
        raise ValueError("tentative assignment outside active window")
    for snapshot in states:
        validate_allocation(snapshot, tuple(a for a in assignments if a.month == snapshot.month))

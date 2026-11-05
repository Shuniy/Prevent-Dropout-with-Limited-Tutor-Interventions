"""Priority-preserving feasible matching; this does not maximize cardinality."""

from collections import defaultdict

from .constraints import candidate_assignments, validate_allocation
from .money import budget_amount, programme_cost


def assign_feasible(state, ordered_students):
    """Choose the cheapest available mentor, then mentor ID, for each student.

    Local counters reserve resources without mutating the snapshot. A flexible
    student can consume a specialist's last slot before a restricted student;
    this deliberately simple greedy matcher does not rearrange earlier choices.
    """
    candidates = defaultdict(list)
    for assignment in candidate_assignments(state):
        candidates[assignment.student_id].append(assignment)
    admissions = {mentor.mentor_id: 0 for mentor in state.mentors}
    limits = {
        mentor.mentor_id: min(mentor.admissions, mentor.appointments // 5)
        for mentor in state.mentors
    }
    selected = []
    seen = set()
    budget = budget_amount(state)
    prices = {mentor.mentor_id: mentor.cost_per_appointment for mentor in state.mentors}
    for student in ordered_students:
        if student.student_id in seen:
            raise ValueError("student priority order contains duplicates")
        seen.add(student.student_id)
        for assignment in sorted(
            candidates[student.student_id], key=lambda item: (item.cost_units, item.mentor_id)
        ):
            if (
                admissions[assignment.mentor_id] < limits[assignment.mentor_id]
                and programme_cost(prices[assignment.mentor_id]) <= budget
            ):
                selected.append(assignment)
                admissions[assignment.mentor_id] += 1
                budget -= programme_cost(prices[assignment.mentor_id])
                break
    validate_allocation(state, selected)
    return tuple(selected)

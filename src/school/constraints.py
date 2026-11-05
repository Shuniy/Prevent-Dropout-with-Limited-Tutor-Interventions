"""Independent checks shared by the environment and all allocation policies."""

from collections import Counter
import math

from .mentor_assignment import MentorAssignment


TOLERANCE = 1e-7


def candidate_assignments(state) -> tuple[MentorAssignment, ...]:
    candidates = []
    for student in state.students:
        if not student.eligible:
            continue
        for mentor in state.mentors:
            # Complete programme cost = five appointments * appointment price.
            cost = 5 * mentor.cost_per_appointment
            if (
                student.student_id in mentor.compatible_student_ids
                and student.support_type in mentor.support_types
                and mentor.admissions >= 1
                and mentor.appointments >= 5
                and cost <= state.remaining_budget + TOLERANCE
            ):
                candidates.append(
                    MentorAssignment(
                        student.student_id,
                        mentor.mentor_id,
                        student.support_type,
                        state.month,
                        5,
                        cost,
                        5,
                    )
                )
    return tuple(candidates)


def validate_allocation(state, assignments) -> None:
    """Recompute feasibility; do not trust candidate generation or solver flags."""
    students = {student.student_id: student for student in state.students}
    mentors = {mentor.mentor_id: mentor for mentor in state.mentors}
    seen = set()
    admissions = Counter()
    appointments = Counter()
    spending = 0.0
    for assignment in assignments:
        student = students.get(assignment.student_id)
        mentor = mentors.get(assignment.mentor_id)
        if student is None or mentor is None:
            raise ValueError("allocation references an unknown student or mentor")
        if assignment.student_id in seen or not student.eligible:
            raise ValueError("student must be enrolled, unused, and assigned at most once")
        if (
            assignment.month != state.month
            or assignment.sessions != 5
            or assignment.completed_sessions != 5
        ):
            raise ValueError("programme must deliver five appointments in the admission month")
        if (
            assignment.support_type != student.support_type
            or assignment.support_type not in mentor.support_types
            or student.student_id not in mentor.compatible_student_ids
        ):
            raise ValueError("incompatible student, need, or mentor")
        cost = 5 * mentor.cost_per_appointment
        if (
            not math.isfinite(assignment.cost_units)
            or abs(assignment.cost_units - cost) > TOLERANCE
        ):
            raise ValueError("incorrect full programme cost")
        spending += cost
        seen.add(student.student_id)
        admissions[mentor.mentor_id] += 1
        appointments[mentor.mentor_id] += 5
    for mentor_id, count in admissions.items():
        if (
            count > mentors[mentor_id].admissions
            or appointments[mentor_id] > mentors[mentor_id].appointments
        ):
            raise ValueError("mentor admission or appointment capacity exceeded")
    if spending > state.remaining_budget + TOLERANCE:
        raise ValueError("episode budget exceeded")

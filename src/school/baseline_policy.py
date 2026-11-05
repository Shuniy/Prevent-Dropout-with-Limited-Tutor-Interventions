"""Simple allocation baselines with the same hard constraints as the planner."""

from .allocation_result import AllocationResult
from .constraints import candidate_assignments, validate_allocation
from .student_condition import STATES
from .transition_model import keyed_uniform


BASELINES = ("wait", "random", "severity", "need_priority", "longest_waiting")


class BaselinePolicy:
    """Need priority uses the fixed initial maximum shared-rule need severity.

    Waiting starts for everyone at the first decision. It ends on admission or
    withdrawal. Consequently, unserved survivors tie in this closed cohort.
    """

    def __init__(self, name="wait", seed=42):
        if name not in BASELINES:
            raise ValueError(f"unknown baseline: {name}")
        self.name = name
        self.seed = seed

    def plan(self, state):
        if self.name == "wait":
            return AllocationResult()
        students = {student.student_id: student for student in state.students}
        candidates = list(candidate_assignments(state))

        def priority(assignment):
            student = students[assignment.student_id]
            if self.name == "random":
                draw = keyed_uniform(
                    self.seed,
                    student.student_id + ":" + assignment.mentor_id,
                    state.month,
                    "policy_random_priority",
                )
                return (draw, student.student_id, assignment.mentor_id)
            if self.name == "severity":
                if student.condition is None:
                    raise ValueError("severity policy requires an observed or estimated condition")
                score = STATES.index(student.condition)
            elif self.name == "need_priority":
                score = student.need_score
            else:
                score = student.waiting_months
            return (-score, student.student_id, assignment.cost_units, assignment.mentor_id)

        candidates.sort(key=priority)
        admissions = {mentor.mentor_id: 0 for mentor in state.mentors}
        limits = {
            mentor.mentor_id: min(mentor.admissions, mentor.appointments // 5)
            for mentor in state.mentors
        }
        selected = []
        assigned_students = set()
        budget = state.remaining_budget
        for assignment in candidates:
            mentor_id = assignment.mentor_id
            if (
                assignment.student_id not in assigned_students
                and admissions[mentor_id] < limits[mentor_id]
                and assignment.cost_units <= budget
            ):
                selected.append(assignment)
                assigned_students.add(assignment.student_id)
                admissions[mentor_id] += 1
                budget -= assignment.cost_units
        validate_allocation(state, selected)
        return AllocationResult(tuple(selected))

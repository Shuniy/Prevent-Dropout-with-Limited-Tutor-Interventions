"""A small, configurable agent-based mentor allocation simulation."""

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from ..utils.constants import (
        DEFAULT_BUDGET,
        DEFAULT_MENTOR_COST_PER_SESSION,
        DEFAULT_NUMBER_OF_MENTORS,
        DEFAULT_NUMBER_OF_MONTHS,
        DEFAULT_NUMBER_OF_SESSIONS_PER_STUDENT,
        DEFAULT_NUMBER_OF_STUDENTS,
        DEFAULT_NUMBER_OF_STUDENTS_PER_MENTOR,
        SEED,
    )
except ImportError:
    from utils.constants import (
        DEFAULT_BUDGET,
        DEFAULT_MENTOR_COST_PER_SESSION,
        DEFAULT_NUMBER_OF_MENTORS,
        DEFAULT_NUMBER_OF_MONTHS,
        DEFAULT_NUMBER_OF_SESSIONS_PER_STUDENT,
        DEFAULT_NUMBER_OF_STUDENTS,
        DEFAULT_NUMBER_OF_STUDENTS_PER_MENTOR,
        SEED,
    )

try:
    from .mentor import Mentor, SupportType
    from .student import Student
    from ..utils.school import (
        DEFAULT_STUDENT_DATA_PATH,
        create_mentors,
        existing_assignments,
        load_students,
        mentor_can_take,
        validate_configuration,
        validate_unique_ids,
    )
except ImportError:  # Support running ``python src/main.py`` directly.
    from models.mentor import Mentor, SupportType
    from models.student import Student
    from utils.school import (
        DEFAULT_STUDENT_DATA_PATH,
        create_mentors,
        existing_assignments,
        load_students,
        mentor_can_take,
        validate_configuration,
        validate_unique_ids,
    )


@dataclass(frozen=True)
class MentorAssignment:
    """One mentor allocation made by the school."""

    student_id: str
    mentor_id: str
    support_type: SupportType
    month: int
    sessions: int
    cost_units: float


class School:
    """Coordinate student and mentor agents over a monthly allocation schedule.

    When explicit agents are not supplied, the school reads student agents from
    the synthetic population CSV and creates mentor agents using the defaults in
    :mod:`constants`.
    """

    def __init__(
        self,
        num_students: int = DEFAULT_NUMBER_OF_STUDENTS,
        num_mentors: int = DEFAULT_NUMBER_OF_MENTORS,
        *,
        students: Iterable[Student] | None = None,
        mentors: Iterable[Mentor] | None = None,
        student_data_path: str | Path = DEFAULT_STUDENT_DATA_PATH,
        num_months: int = DEFAULT_NUMBER_OF_MONTHS,
        budget: float = DEFAULT_BUDGET,
        mentor_cost_per_session: float = DEFAULT_MENTOR_COST_PER_SESSION,
        sessions_per_student: int = DEFAULT_NUMBER_OF_SESSIONS_PER_STUDENT,
        students_per_mentor: int = DEFAULT_NUMBER_OF_STUDENTS_PER_MENTOR,
        support_type: SupportType = "tutoring",
        seed: int = SEED,
    ) -> None:
        validate_configuration(
            num_students=num_students,
            num_mentors=num_mentors,
            num_months=num_months,
            budget=budget,
            mentor_cost_per_session=mentor_cost_per_session,
            sessions_per_student=sessions_per_student,
            students_per_mentor=students_per_mentor,
        )

        self.num_months = num_months
        self.budget = float(budget)
        self.sessions_per_student = sessions_per_student
        self.students_per_mentor = students_per_mentor
        self.support_type = support_type
        self.seed = seed
        self._rng = random.Random(seed)

        self.students = (
            list(students)
            if students is not None
            else load_students(student_data_path, num_students)
        )
        self.mentors = (
            list(mentors)
            if mentors is not None
            else create_mentors(
                num_mentors,
                num_months=num_months,
                students_per_mentor=students_per_mentor,
                sessions_per_student=sessions_per_student,
                support_type=support_type,
                cost_units_per_session=mentor_cost_per_session,
            )
        )

        validate_unique_ids(self.students, self.mentors)
        self.assignments = existing_assignments(self.students, self.mentors)
        self.assignment_history: list[MentorAssignment] = []
        self.monthly_assignments: dict[int, dict[str, str]] = {}
        self.spent_budget = 0.0
        self._school_assigned_student_ids: set[str] = set()
        self._sessions_used: dict[tuple[str, int], int] = {}

    @property
    def remaining_budget(self) -> float:
        return self.budget - self.spent_budget

    @property
    def unassigned_student_ids(self) -> list[str]:
        return [
            student.student_id
            for student in self.students
            if student.student_id not in self.assignments
        ]

    def step(
        self,
        month: int,
        *,
        support_type: SupportType | None = None,
    ) -> list[MentorAssignment]:
        """Allocate students for one month and return the new assignments."""

        if month < 1 or month > self.num_months:
            raise ValueError(f"month must be between 1 and {self.num_months}")

        # A mentor's student capacity renews at the start of every month.
        for mentor in self.mentors:
            for student_id in list(mentor.current_student_ids):
                if student_id in self._school_assigned_student_ids:
                    mentor.release_student(student_id)

        self._school_assigned_student_ids.clear()
        self.assignments = existing_assignments(self.students, self.mentors)

        selected_support_type = support_type or self.support_type
        required_sessions = self.sessions_per_student
        new_assignments: list[MentorAssignment] = []

        students_this_month = list(self.students)
        self._rng.shuffle(students_this_month)

        for student in students_this_month:
            if student.student_id in self.assignments:
                continue

            eligible_mentors = [
                mentor
                for mentor in self.mentors
                if mentor_can_take(
                    mentor,
                    student_id=student.student_id,
                    support_type=selected_support_type,
                    month=month,
                    required_sessions=required_sessions,
                    sessions_used=self._sessions_used.get(
                        (mentor.mentor_id, month), 0
                    ),
                    remaining_budget=self.remaining_budget,
                )
            ]
            if not eligible_mentors:
                continue

            mentor = min(
                eligible_mentors,
                key=lambda candidate: (candidate.current_caseload, candidate.mentor_id),
            )
            usage_key = (mentor.mentor_id, month)
            assignment_cost = required_sessions * mentor.cost_units_per_session

            mentor.assign_student(student.student_id)
            self.assignments[student.student_id] = mentor.mentor_id
            self._school_assigned_student_ids.add(student.student_id)
            self._sessions_used[usage_key] = (
                self._sessions_used.get(usage_key, 0) + required_sessions
            )
            self.spent_budget += assignment_cost

            assignment = MentorAssignment(
                student_id=student.student_id,
                mentor_id=mentor.mentor_id,
                support_type=selected_support_type,
                month=month,
                sessions=required_sessions,
                cost_units=assignment_cost,
            )
            self.assignment_history.append(assignment)
            new_assignments.append(assignment)

        self.monthly_assignments[month] = dict(self.assignments)
        return new_assignments

    def run_simulation(
        self,
        *,
        support_type: SupportType | None = None,
    ) -> dict[int, dict[str, str]]:
        """Run all configured months and return assignments grouped by month."""

        for mentor in self.mentors:
            for student_id in list(mentor.current_student_ids):
                if student_id in self._school_assigned_student_ids:
                    mentor.release_student(student_id)

        self._school_assigned_student_ids.clear()
        self.assignments = existing_assignments(self.students, self.mentors)
        self.assignment_history.clear()
        self.monthly_assignments.clear()
        self.spent_budget = 0.0
        self._sessions_used.clear()
        self._rng.seed(self.seed)

        for month in range(1, self.num_months + 1):
            self.step(month, support_type=support_type)
        return {
            month: dict(assignments)
            for month, assignments in self.monthly_assignments.items()
        }

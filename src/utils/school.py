"""Loading, validation, and feasibility helpers for the school simulation."""

from .constants import (
    ALL_SUPPORT_TYPES, BOOLEAN_FIELDS, DEFAULT_STUDENT_DATA_PATH, INTEGER_FIELDS, PROJECT_ROOT,
)
from .enums import SupportType

import csv
from pathlib import Path
from typing import Iterable

try:
    from ..models.mentor import Mentor, MentorAvailability
    from ..models.student import Student, StudentSimulation
except ImportError:  # Support running ``python src/main.py`` directly.
    from models.mentor import Mentor, MentorAvailability
    from models.student import Student, StudentSimulation


def validate_configuration(
    *,
    num_students: int,
    num_mentors: int,
    num_months: int,
    budget: float,
    mentor_cost_per_session: float,
    sessions_per_student: int,
    students_per_mentor: int,
) -> None:
    if num_students < 0:
        raise ValueError("num_students must be non-negative")
    if num_mentors < 0:
        raise ValueError("num_mentors must be non-negative")
    if num_months <= 0:
        raise ValueError("num_months must be positive")
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if mentor_cost_per_session < 0:
        raise ValueError("mentor_cost_per_session must be non-negative")
    if sessions_per_student <= 0:
        raise ValueError("sessions_per_student must be positive")
    if students_per_mentor < 0:
        raise ValueError("students_per_mentor must be non-negative")


def parse_bool(value: str, field_name: str, *, optional: bool = False) -> bool | None:
    normalized = value.strip().lower()
    if optional and not normalized:
        return None
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid boolean value for {field_name}: {value!r}")


def student_from_row(row: dict[str, str]) -> StudentSimulation:
    """Convert one synthetic-population CSV row into a student agent."""

    values: dict[str, object] = {
        "student_id": row["student_id"],
        "school_id": row["school_id"],
        "sex_source": row["sex_source"],
        "mother_job": row["mother_job"],
        "father_job": row["father_job"],
        "guardian": row["guardian"],
        "math_grade1_0_20": (
            int(row["math_grade1_0_20"])
            if row["math_grade1_0_20"].strip()
            else None
        ),
        "initial_attendance_fraction_assumed": float(
            row["initial_attendance_fraction_assumed"]
        ),
        "initial_engagement_assumed": float(row["initial_engagement_assumed"]),
        "enrolled_initial_assumed": parse_bool(
            row["enrolled_initial_assumed"], "enrolled_initial_assumed"
        ),
        "financial_need_verified": parse_bool(
            row["financial_need_verified"],
            "financial_need_verified",
            optional=True,
        ),
    }
    values.update(
        {
            field_name: parse_bool(row[field_name], field_name)
            for field_name in BOOLEAN_FIELDS
        }
    )
    values.update(
        {field_name: int(row[field_name]) for field_name in INTEGER_FIELDS}
    )
    return StudentSimulation(**values)  # type: ignore[arg-type]


def load_students(
    student_data_path: str | Path,
    num_students: int,
) -> list[StudentSimulation]:
    """Read a deterministic prefix of the synthetic student population."""

    path = Path(student_data_path)
    if not path.is_file():
        raise FileNotFoundError(f"synthetic student data not found: {path}")

    students: list[StudentSimulation] = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if len(students) == num_students:
                break
            students.append(student_from_row(row))

    if len(students) < num_students:
        raise ValueError(
            f"requested {num_students} students, but {path} "
            f"contains only {len(students)}"
        )
    return students


def create_mentors(
    num_mentors: int,
    *,
    num_months: int,
    students_per_mentor: int,
    sessions_per_student: int,
    support_type: SupportType,
    cost_units_per_session: float,
) -> list[Mentor]:
    """Create assumed generalist mentors with capacity for every month."""

    if support_type not in ALL_SUPPORT_TYPES:
        raise ValueError(f"unknown mentor support type: {support_type}")
    max_sessions = students_per_mentor * sessions_per_student
    return [
        Mentor(
            mentor_id=f"mentor-{index + 1}",
            support_types=list(ALL_SUPPORT_TYPES),
            max_active_students=students_per_mentor,
            availability_by_step=[
                MentorAvailability(
                    step=month,
                    available_hours=0.0,
                    max_sessions=max_sessions,
                )
                for month in range(1, num_months + 1)
            ],
            cost_units_per_hour=0.0,
            cost_units_per_session=cost_units_per_session,
        )
        for index in range(num_mentors)
    ]


def validate_unique_ids(students: Iterable[Student], mentors: Iterable[Mentor]) -> None:
    student_ids = [student.student_id for student in students]
    mentor_ids = [mentor.mentor_id for mentor in mentors]
    if len(student_ids) != len(set(student_ids)):
        raise ValueError("student IDs must be unique within a school")
    if len(mentor_ids) != len(set(mentor_ids)):
        raise ValueError("mentor IDs must be unique within a school")


def existing_assignments(
    students: Iterable[Student],
    mentors: Iterable[Mentor],
) -> dict[str, str]:
    """Return school students already present in mentor caseloads."""

    school_student_ids = {student.student_id for student in students}
    seen_student_ids: set[str] = set()
    assignments: dict[str, str] = {}
    for mentor in mentors:
        for student_id in mentor.current_student_ids:
            if student_id in seen_student_ids:
                raise ValueError(
                    f"student {student_id!r} is assigned to more than one mentor"
                )
            seen_student_ids.add(student_id)
            if student_id in school_student_ids:
                assignments[student_id] = mentor.mentor_id
    return assignments


def mentor_can_take(
    mentor: Mentor,
    *,
    student_id: str,
    support_type: SupportType,
    month: int,
    required_sessions: int,
    sessions_used: int,
    remaining_budget: float,
) -> bool:
    """Check all constraints for one possible mentor assignment."""

    if not mentor.supports(support_type):
        return False
    if not mentor.can_accept_student(
        student_id,
        support_type,
        month,
        required_hours=0.0,
    ):
        return False

    availability = mentor.availability_at(month)
    if availability is None:
        return False

    assignment_cost = required_sessions * mentor.cost_units_per_session
    return (
        availability.max_sessions - sessions_used >= required_sessions
        and assignment_cost <= remaining_budget
    )

"""Reuse existing synthetic population and generalist mentor creation."""

import csv
from dataclasses import replace

from .loading import create_mentors, student_from_row
from ..utils.constants import DEFAULT_STUDENT_DATA_PATH
from .cmdp_environment import initial_condition
from .school import School


def build_school(config, student_data_path=DEFAULT_STUDENT_DATA_PATH):
    # Deterministic enrolled prefix. No rows or source assumptions are rewritten.
    students = []
    with open(student_data_path, newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if len(students) == config.num_students:
                break
            student = student_from_row(row)
            if initial_condition(student) is not None:
                students.append(student)
    if len(students) != config.num_students:
        raise ValueError("source population has fewer enrolled students than requested")
    mentors = create_mentors(
        config.num_mentors,
        num_months=config.horizon,
        students_per_mentor=config.monthly_admissions,
        sessions_per_student=5,
        support_type="tutoring",
        cost_units_per_session=config.cost_per_appointment,
    )
    for mentor in mentors:
        mentor.availability_by_step = [
            replace(availability, max_sessions=config.monthly_appointments)
            for availability in mentor.availability_by_step
        ]
    return School(
        students=students,
        mentors=mentors,
        num_students=config.num_students,
        num_mentors=config.num_mentors,
        num_months=config.horizon,
        budget=config.budget,
        sessions_per_student=config.appointments_per_programme,
        students_per_mentor=config.monthly_admissions,
        mentor_cost_per_session=config.cost_per_appointment,
        seed=config.seed,
    )


def build_environment(config, student_data_path=DEFAULT_STUDENT_DATA_PATH):
    return build_school(config, student_data_path).create_cmdp_environment(config=config)


def run_episode(environment, policy):
    while not environment.done:
        state = environment.observe()
        allocation = policy.plan(state)
        environment.step(allocation)
    return environment

from dataclasses import replace

from src.school.cmdp_environment import CMDPEnvironment
from src.school.scenario_config import ScenarioConfig
from src.school.loading import create_mentors, load_students
from src.utils.constants import DEFAULT_STUDENT_DATA_PATH


def environment(count=3, **overrides):
    config = ScenarioConfig(num_students=count, **overrides)
    students = load_students(DEFAULT_STUDENT_DATA_PATH, count)
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
            replace(item, max_sessions=config.monthly_appointments)
            for item in mentor.availability_by_step
        ]
    return CMDPEnvironment(students, mentors, config), students, mentors

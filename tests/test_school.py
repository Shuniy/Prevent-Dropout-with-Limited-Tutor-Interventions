import unittest
from pathlib import Path

from src.models.mentor import Mentor, MentorAvailability
from src.models.school import School
from src.models.student import StudentSimulation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SchoolSimulationTests(unittest.TestCase):
    def test_loaded_students_are_assigned_without_exceeding_caseload(self) -> None:
        school = School(
            num_students=5,
            num_mentors=2,
            num_months=3,
            students_per_mentor=2,
            sessions_per_student=1,
        )

        assignments = school.run_simulation()

        self.assertEqual(list(assignments), [1, 2, 3])
        self.assertTrue(all(len(month) == 4 for month in assignments.values()))
        self.assertEqual([mentor.current_caseload for mentor in school.mentors], [2, 2])
        self.assertEqual(len(school.unassigned_student_ids), 1)
        self.assertEqual(len(school.assignment_history), 12)

    def test_students_are_loaded_and_converted_from_synthetic_csv(self) -> None:
        school = School(num_students=1, num_mentors=0)

        student = school.students[0]
        self.assertIsInstance(student, StudentSimulation)
        self.assertEqual(student.student_id, "SYN00001")
        self.assertEqual(student.school_id, "MS")
        self.assertEqual(student.age_years, 15)
        self.assertTrue(student.rural_residence)
        self.assertIsNone(student.math_grade1_0_20)
        self.assertAlmostEqual(student.initial_attendance_fraction_assumed, 0.9178379883)
        self.assertIsNone(student.financial_need_verified)

    def test_student_csv_path_can_be_overridden(self) -> None:
        student_data_path = (
            PROJECT_ROOT
            / "data/synthetic/populations/synthetic_student_population.csv"
        )

        school = School(
            num_students=2,
            num_mentors=0,
            student_data_path=student_data_path,
        )

        self.assertEqual(
            [student.student_id for student in school.students],
            ["SYN00001", "SYN00002"],
        )

    def test_monthly_assignment_respects_skill_and_session_availability(self) -> None:
        tutoring_mentor = Mentor(
            mentor_id="tutor",
            support_types=["tutoring"],
            max_active_students=3,
            availability_by_step=[
                MentorAvailability(step=1, available_hours=0.0, max_sessions=4),
                MentorAvailability(step=2, available_hours=0.0, max_sessions=4),
            ],
            cost_units_per_session=1.0,
        )
        liaison_mentor = Mentor(
            mentor_id="liaison",
            support_types=["family_liaison"],
            max_active_students=3,
            availability_by_step=[
                MentorAvailability(step=1, available_hours=0.0, max_sessions=10),
                MentorAvailability(step=2, available_hours=0.0, max_sessions=10),
            ],
        )
        school = School(
            num_students=3,
            mentors=[tutoring_mentor, liaison_mentor],
            num_months=2,
            sessions_per_student=2,
        )

        assignments = school.run_simulation()

        self.assertTrue(all(len(month) == 2 for month in assignments.values()))
        self.assertTrue(
            all(
                mentor_id == "tutor"
                for month in assignments.values()
                for mentor_id in month.values()
            )
        )
        self.assertEqual(tutoring_mentor.current_caseload, 2)
        self.assertEqual(liaison_mentor.current_caseload, 0)
        self.assertEqual(school.spent_budget, 8.0)

    def test_default_run_allocates_five_tutoring_sessions_for_twelve_months(self) -> None:
        school = School(
            num_students=2,
            num_mentors=1,
            students_per_mentor=2,
        )

        assignments = school.run_simulation()

        self.assertEqual(len(assignments), 12)
        self.assertTrue(all(len(month) == 2 for month in assignments.values()))
        self.assertEqual(len(school.assignment_history), 24)
        self.assertEqual(school.spent_budget, 120.0)
        self.assertTrue(
            all(
                assignment.sessions == 5
                and assignment.support_type == "tutoring"
                and assignment.cost_units == 5.0
                for assignment in school.assignment_history
            )
        )

    def test_students_are_random_each_month_and_can_be_repeated(self) -> None:
        school = School(
            num_students=6,
            num_mentors=1,
            num_months=4,
            students_per_mentor=3,
            sessions_per_student=1,
            seed=42,
        )

        assignments = school.run_simulation()
        monthly_student_sets = [set(month) for month in assignments.values()]
        assignment_counts: dict[str, int] = {}
        for student_ids in monthly_student_sets:
            self.assertEqual(len(student_ids), 3)
            for student_id in student_ids:
                assignment_counts[student_id] = assignment_counts.get(student_id, 0) + 1

        self.assertGreater(len(set(map(frozenset, monthly_student_sets))), 1)
        self.assertGreater(max(assignment_counts.values()), 1)

    def test_budget_limits_monthly_assignments(self) -> None:
        school = School(
            num_students=4,
            num_mentors=1,
            num_months=1,
            students_per_mentor=4,
            sessions_per_student=5,
            mentor_cost_per_session=2.0,
            budget=20.0,
        )

        assignments = school.run_simulation()

        self.assertEqual(len(assignments[1]), 2)
        self.assertEqual(school.spent_budget, 20.0)
        self.assertEqual(school.remaining_budget, 0.0)

    def test_repeated_run_does_not_double_assign_students(self) -> None:
        school = School(
            num_students=2,
            num_mentors=1,
            num_months=2,
            students_per_mentor=2,
            sessions_per_student=1,
        )

        first_result = school.run_simulation()
        second_result = school.run_simulation()

        self.assertEqual(second_result, first_result)
        self.assertEqual(len(school.assignment_history), 4)
        self.assertEqual(school.mentors[0].current_caseload, 2)


if __name__ == "__main__":
    unittest.main()

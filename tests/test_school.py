import unittest
from pathlib import Path

from src.school.mentor import Mentor
from src.school.mentor_availability import MentorAvailability
from src.school.school import School
from src.school.student_simulation import StudentSimulation


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

        assignments = school.allocate_programmes(support_type="tutoring")

        self.assertEqual(list(assignments), [1, 2, 3])
        self.assertEqual([len(month) for month in assignments.values()], [4, 1, 0])
        self.assertEqual([mentor.current_caseload for mentor in school.mentors], [0, 0])
        self.assertEqual(len(school.unassigned_student_ids), 0)
        self.assertEqual(len(school.assignment_history), 5)

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

        assignments = school.allocate_programmes(support_type="tutoring")

        self.assertEqual([len(month) for month in assignments.values()], [2, 1])
        self.assertTrue(
            all(
                mentor_id == "tutor"
                for month in assignments.values()
                for mentor_id in month.values()
            )
        )
        self.assertEqual(tutoring_mentor.current_caseload, 1)
        self.assertEqual(liaison_mentor.current_caseload, 0)
        self.assertEqual(school.spent_budget, 6.0)

    def test_plan_allocates_each_student_once_with_five_sessions(self) -> None:
        school = School(
            num_students=2,
            num_mentors=1,
            students_per_mentor=2,
        )

        assignments = school.allocate_programmes(support_type="tutoring")

        self.assertEqual(len(assignments), 12)
        self.assertEqual([len(month) for month in assignments.values()], [2] + [0] * 11)
        self.assertEqual(len(school.assignment_history), 2)
        self.assertEqual(school.spent_budget, 10.0)
        self.assertTrue(
            all(
                assignment.sessions == 5
                and assignment.support_type == "tutoring"
                and assignment.cost_units == 5.0
                for assignment in school.assignment_history
            )
        )

    def test_students_are_not_reused_but_mentors_are(self) -> None:
        school = School(num_students=6, num_mentors=1, num_months=4,
                        students_per_mentor=3, sessions_per_student=1)
        assignments = school.allocate_programmes()
        self.assertEqual([len(month) for month in assignments.values()], [3, 3, 0, 0])
        self.assertEqual(len({a.student_id for a in school.assignment_history}), 6)
        self.assertEqual({a.mentor_id for a in school.assignment_history}, {"mentor-1"})
        self.assertEqual({a.support_type for a in school.assignment_history},
                         {s.primary_support_type for s in school.students})

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

        assignments = school.allocate_programmes(support_type="tutoring")

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

        first_result = school.allocate_programmes(support_type="tutoring")
        second_result = school.allocate_programmes(support_type="tutoring")

        self.assertEqual(second_result, first_result)
        self.assertEqual(len(school.assignment_history), 2)
        self.assertEqual(school.mentors[0].current_caseload, 0)

    def test_allocation_seed_reproduces_after_reset_and_other_runs(self):
        def school(seed):
            return School(num_students=20, num_mentors=1, num_months=1,
                          students_per_mentor=5, sessions_per_student=1, seed=seed)

        first = school(17)
        expected = first.step(1, prioritize_by_need=False)
        school(99).step(1, prioritize_by_need=False)
        self.assertEqual(school(17).step(1, prioritize_by_need=False), expected)
        self.assertNotEqual(school(18).step(1, prioritize_by_need=False), expected)
        first.reset()
        self.assertEqual(first.step(1, prioritize_by_need=False), expected)


if __name__ == "__main__":
    unittest.main()

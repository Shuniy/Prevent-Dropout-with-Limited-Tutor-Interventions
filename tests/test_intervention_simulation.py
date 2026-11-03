import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.intervention.intervention import Intervention
from src.intervention.rag import InterventionRAG
from src.intervention.session_index import SessionIndex
from src.intervention.simulation import create_profile
from src.intervention.transcripts import load_sessions
from src.models.mentor import Mentor
from src.models.mentor_availability import MentorAvailability
from src.models.school import School
from tests.helpers import FakeClient, write_history


class InterventionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.root = self.directory / "histories"
        write_history(self.root, count=2)
        source = School(num_students=1, num_mentors=0).students[0]
        self.student = replace(source, anchor_grade1_0_20=2, math_grade1_0_20=None,
                               internet_at_home=True, travel_time_category=1,
                               study_time_category=2, health_self_rating=5,
                               family_relationship_rating=5,
                               initial_attendance_fraction_assumed=0.95,
                               initial_engagement_assumed=0.9)
        self.client = FakeClient()

    def school(self, count=2, **options):
        return School(students=[replace(self.student, student_id=f"student{n}") for n in range(count)],
                      num_mentors=1, students_per_mentor=count, **options)

    def run_school(self, school, name="run", client=None):
        if not school.monthly_assignments:
            school.run_simulation()
        return school.run_interventions(root=self.root, output_dir=self.directory / name,
                                        client=self.client if client is None else client)

    def test_short_programmes_save_findings_and_charge_only_recorded_sessions(self):
        school = self.school(num_months=2, budget=10)
        school.mentors[0].max_active_students = 1
        before = [vars(student).copy() for student in school.students]
        report = self.run_school(school)
        self.assertEqual(report["status"], "finished")
        self.assertEqual(report["spent_budget"], 4)
        self.assertEqual(report["remaining_budget"], 6)
        self.assertEqual([a.month for a in school.assignment_history], [1, 2])
        self.assertEqual([vars(student) for student in school.students], before)
        self.assertEqual(len(self.client.contexts), 4)
        self.assertEqual(self.client.contexts[2]["earlier_validated_memory"], [])
        for record in report["students"].values():
            self.assertEqual(record["status"], "incomplete")
            self.assertEqual(record["planned_sessions"], 5)
            self.assertEqual(record["sessions_completed"], 2)
            self.assertEqual(record["assignment"]["cost_units"], 2)
        output = Path(report["output_dir"])
        session = json.loads((output / "student_00001/session_01.json").read_text())
        self.assertEqual(session["session_number"], 1)
        self.assertEqual(session["findings"]["primary_concern"], "learning_gap")
        self.assertEqual(json.loads((output / "final_report.json").read_text()), report)

    def test_intervention_requires_a_school_plan(self):
        with self.assertRaisesRegex(ValueError, "run_simulation"):
            self.school().run_interventions(root=self.root, client=self.client)

    def test_intervention_uses_existing_plan_without_reset_or_allocation(self):
        school = self.school(count=3, num_months=3, sessions_per_student=2)
        school.mentors[0].max_active_students = 1
        school.run_simulation()
        plan = list(school.assignment_history)
        mapping = dict(school.assignments)
        with patch.object(school, "reset", side_effect=AssertionError("reset called")), \
             patch.object(school, "step", side_effect=AssertionError("allocation called")):
            report = self.run_school(school)
        self.assertEqual(school.assignments, mapping)
        self.assertEqual([(a.student_id, a.mentor_id, a.month) for a in school.assignment_history],
                         [(a.student_id, a.mentor_id, a.month) for a in plan])
        self.assertTrue(all(s["status"] == "completed" for s in report["students"].values()))

    def test_refunds_do_not_admit_students_outside_the_plan(self):
        school = self.school(count=2, num_months=2, budget=7)
        school.mentors[0].max_active_students = 1
        report = self.run_school(school)
        self.assertEqual(len(school.assignment_history), 1)
        self.assertEqual(report["spent_budget"], 2)
        self.assertEqual(sum(s["status"] == "unassigned" for s in report["students"].values()), 1)

    def test_planned_session_limit_produces_a_completed_programme(self):
        report = self.run_school(self.school(count=1, sessions_per_student=1))
        student = next(iter(report["students"].values()))
        self.assertEqual(student["status"], "completed")
        self.assertEqual(student["sessions_completed"], 1)
        self.assertEqual(len(self.client.contexts), 1)
        self.assertNotIn("task 2", json.dumps(self.client.contexts))

    def test_need_priority_selects_the_highest_need_with_limited_budget(self):
        low = replace(self.student, student_id="low", anchor_grade1_0_20=8, past_failures_count=0)
        high = replace(self.student, student_id="high", anchor_grade1_0_20=1, past_failures_count=0)
        school = School(students=[low, high], num_mentors=1, num_months=1, budget=5)
        report = self.run_school(school)
        self.assertEqual([a.student_id for a in school.assignment_history], ["high"])
        self.assertEqual(report["students"]["low"]["status"], "unassigned")

    def test_budget_skills_and_missing_histories_leave_students_unassigned(self):
        budget = self.run_school(self.school(budget=4), "budget")
        self.assertTrue(all(s["status"] == "unassigned" for s in budget["students"].values()))
        mentor = Mentor("specialist", ["family_liaison"], 2,
                        availability_by_step=[MentorAvailability(1, 0, 10)])
        skills = self.run_school(School(students=[self.student], mentors=[mentor], num_months=1), "skills")
        self.assertEqual(skills["students"][self.student.student_id]["status"], "unassigned")
        student = replace(self.student, travel_time_category=4)
        missing = self.run_school(School(students=[student], num_mentors=1), "missing")
        self.assertEqual(missing["students"][student.student_id]["unassigned_reason"], "no_matching_history")

    def test_capacity_renews_without_starting_second_programmes(self):
        school = self.school(count=3, num_months=3)
        school.mentors[0].max_active_students = 1
        first = self.run_school(school)
        self.assertEqual([a.month for a in school.assignment_history], [1, 2, 3])
        self.assertEqual(len({a.student_id for a in school.assignment_history}), 3)
        with self.assertRaisesRegex(ValueError, "already started"):
            self.run_school(school, "duplicate")
        school.run_simulation()
        second = self.run_school(school, "second")
        self.assertEqual(first["assignments"], second["assignments"])
        self.assertEqual(first["students"], second["students"])

    def test_failed_model_preserves_first_session_and_recorded_attendance(self):
        for failure in ("invalid", "network"):
            with self.subTest(failure=failure):
                client = FakeClient(fail_at=2, failure=failure)
                report = self.run_school(self.school(count=1), failure, client)
                student = next(iter(report["students"].values()))
                self.assertEqual(report["status"], "failed")
                self.assertEqual(student["status"], "report_failed")
                self.assertIsNone(student["conclusion"])
                self.assertTrue(student["error"])
                self.assertEqual(student["sessions_completed"], 2)
                self.assertEqual(report["spent_budget"], 2)
                output = Path(report["output_dir"]) / "student_00001"
                self.assertTrue((output / "session_01.json").exists())
                self.assertFalse((output / "session_02.json").exists())
                self.assertEqual(len(client.contexts), 2)

    def test_existing_mentor_is_preserved_and_cost_is_reconciled(self):
        mentor = Mentor("existing", ["tutoring"], 1, current_student_ids=[self.student.student_id],
                        availability_by_step=[MentorAvailability(1, 0, 5)], cost_units_per_session=2)
        school = School(students=[self.student], mentors=[mentor], num_months=1, budget=10)
        report = self.run_school(school)
        record = report["students"][self.student.student_id]
        self.assertEqual(record["mentor_id"], "existing")
        self.assertEqual(record["assignment"]["cost_units"], 4)

    def test_controller_checks_assignment_and_runs_only_once(self):
        school = self.school(count=1)
        assignment = school.step(1)[0]
        student, mentor = school.students[0], school.mentors[0]
        profile = create_profile(student)
        profile.mentor_id = assignment.mentor_id
        profile.history_id = "02_tutoring/student"
        index = SessionIndex()
        self.addCleanup(index.close)
        index.build(load_sessions(self.root))
        controller = Intervention(InterventionRAG(index, self.client), profile, self.directory / "direct")
        with self.assertRaisesRegex(ValueError, "match the assigned profile"):
            controller.start_intervention(replace(student, student_id="wrong"), mentor)
        mentor.release_student(student.student_id)
        with self.assertRaisesRegex(ValueError, "assigned to the mentor"):
            controller.start_intervention(student, mentor)
        mentor.assign_student(student.student_id)
        controller.start_intervention(student, mentor)
        with self.assertRaisesRegex(ValueError, "already started"):
            controller.start_intervention(student, mentor)
        self.assertEqual(len(self.client.contexts), 2)

    def test_existing_output_directory_is_protected(self):
        school = self.school()
        self.run_school(school)
        school.run_simulation()
        with self.assertRaises(FileExistsError):
            self.run_school(school)


if __name__ == "__main__":
    unittest.main()

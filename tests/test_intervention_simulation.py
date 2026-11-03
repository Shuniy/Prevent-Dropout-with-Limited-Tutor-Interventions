import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from src.intervention.intervention import Intervention
from src.intervention.rag import InterventionRAG, SessionIndex, load_sessions
from src.intervention.simulation import create_profile
from src.main import SchoolCMDPEnvironment
from src.models.mentor import Mentor, MentorAvailability
from src.models.school import School
from src.models.student import Student
from tests.test_intervention_rag import generated_finding


class RecordingClient:
    model = "test-local-client"

    def __init__(self):
        self.contexts = []

    def generate(self, messages, schema):
        context = json.loads(messages[1]["content"])
        self.contexts.append(context)
        return generated_finding(context)


class InterventionSimulationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "histories"
        for student, count in (("student_001", 5), ("student_002", 2)):
            folder = self.root / "02_tutoring" / student
            folder.mkdir(parents=True)
            for number in range(1, count + 1):
                stage = "initial" if number == 1 else "followup"
                (folder / f"session_{number:02d}_{stage}.md").write_text(
                    "# Student\n**Intervention type:** HEADER_SECRET\n\n"
                    f"**Student:** {student} practice task {number} remains difficult.\n\n"
                    "**Mentor:** We can review one example together.\n", encoding="utf-8")
        source = School(num_students=1, num_mentors=0).students[0]
        self.student = replace(source, anchor_grade1_0_20=2, math_grade1_0_20=None,
                               internet_at_home=True, travel_time_category=1,
                               study_time_category=2, health_self_rating=5,
                               family_relationship_rating=5,
                               initial_attendance_fraction_assumed=0.95,
                               initial_engagement_assumed=0.9)
        self.client = RecordingClient()

    def school(self, count=2, **kwargs):
        return School(students=[replace(self.student, student_id=f"student/{number}")
                                for number in range(count)], num_mentors=1,
                      students_per_mentor=count, seed=4, **kwargs)

    def run_school(self, school, folder="run", client=None):
        return school.run_interventions(root=self.root,
                                        output_dir=Path(self.directory.name) / folder,
                                        client=client or self.client)

    def controller(self):
        index = SessionIndex()
        self.addCleanup(index.close)
        index.build(load_sessions(self.root))
        school = self.school(count=1)
        assignment = school.step(1)[0]
        student, mentor = school.students[0], school.mentors[0]
        profile = create_profile(student)
        profile.mentor_id = assignment.mentor_id
        profile.history_id = "02_tutoring/student_001"
        controller = Intervention(InterventionRAG(index, self.client), profile,
                                  Path(self.directory.name) / "direct")
        return controller, student, mentor

    def test_controller_runs_first_and_followup_sessions_once(self):
        controller, student, mentor = self.controller()
        report = controller.start_intervention(student, mentor)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["sessions_completed"], 5)
        self.assertEqual(len(self.client.contexts), 5)
        self.assertEqual(len(self.client.contexts[0]["earlier_validated_memory"]), 0)
        self.assertEqual(len(self.client.contexts[-1]["earlier_validated_memory"]), 4)
        self.assertTrue((controller.output_dir / "session_05.json").exists())
        with self.assertRaisesRegex(ValueError, "already started"):
            controller.start_intervention(student, mentor)
        self.assertEqual(len(self.client.contexts), 5)

    def test_controller_rejects_wrong_or_unassigned_pair_before_model_calls(self):
        controller, student, mentor = self.controller()
        with self.assertRaisesRegex(ValueError, "match the assigned profile"):
            controller.start_intervention(replace(student, student_id="wrong"), mentor)
        with self.assertRaisesRegex(ValueError, "match the assigned profile"):
            controller.start_intervention(student, replace(mentor, mentor_id="wrong"))
        mentor.release_student(student.student_id)
        with self.assertRaisesRegex(ValueError, "assigned to the mentor"):
            controller.start_intervention(student, mentor)
        self.assertEqual(self.client.contexts, [])

    def test_profiles_use_features_and_preserve_unknowns_and_input_records(self):
        profile = create_profile(self.student)
        self.assertEqual(profile.problems[0]["support_type"], "tutoring")
        self.assertEqual(profile.initial_scores["learning_gap_0_1"], 0.8)
        self.assertIsNone(profile.initial_scores["school_dropout_risk"])
        self.assertIsNone(profile.dataset_profile["financial_need_verified"])
        self.assertNotIn("family_finances", [p["support_type"] for p in profile.problems])
        basic = Student(**{name: getattr(self.student, name) for name in Student.__dataclass_fields__})
        self.assertIsNone(create_profile(basic).initial_scores["attendance_fraction_assumed"])
        self.assertIsNone(create_profile(basic).initial_scores["engagement_assumed"])
        self.assertEqual(self.student.support_sessions_completed, 0)

    def test_feature_concerns_are_explicit_and_ranked(self):
        source = replace(self.student, anchor_grade1_0_20=18, travel_time_category=4,
                         internet_at_home=False, initial_attendance_fraction_assumed=0.6,
                         initial_engagement_assumed=0.4, financial_need_verified=True)
        profile = create_profile(source)
        self.assertEqual(profile.problems[0]["support_type"], "transport_assessment")
        supports = {p["support_type"] for p in profile.problems}
        self.assertTrue({"device_access", "attendance_planning", "peer_support", "family_finances"} <= supports)
        self.assertTrue(all(0 <= p["severity"] <= 1 for p in profile.problems))
        with self.assertRaises(ValueError):
            create_profile(replace(source, initial_engagement_assumed=1.2))

    def test_reports_cover_five_total_or_partial_sessions_and_actual_cost(self):
        school = self.school(num_months=12, budget=10)
        originals = [vars(student).copy() for student in school.students]
        report = self.run_school(school)
        self.assertEqual(report["status"], "finished")
        self.assertEqual(report["summary"]["completed_programmes"], 1)
        self.assertEqual(report["summary"]["incomplete_programmes"], 1)
        self.assertEqual(report["summary"]["recorded_sessions"], 7)
        self.assertEqual(report["summary"]["spent_budget"], 7)
        self.assertEqual(report["summary"]["remaining_budget"], 3)
        self.assertEqual(len(school.assignment_history), 2)
        self.assertEqual(len(self.client.contexts), 7)  # No quadratic LLM replay.
        self.assertEqual([vars(student) for student in school.students], originals)
        for student in report["students"].values():
            self.assertEqual(student["planned_sessions"], 5)
            self.assertIsNone(student["school_dropout"])
            self.assertEqual(len(student["session_reports"]), student["sessions_completed"])
            for session in student["session_reports"]:
                self.assertEqual(session["mentor_id"], student["mentor_id"])
                self.assertEqual(session["initial_scores"], student["initial_scores"])
                self.assertEqual(session["dataset_profile"]["student_id"], student["student_id"])
            if student["status"] == "incomplete":
                self.assertEqual(student["unrecorded_session_numbers"], [3, 4, 5])
        output = Path(report["output_dir"])
        self.assertEqual(len(list(output.glob("student_*/session_*.json"))), 7)
        self.assertEqual(len(list(output.rglob("final_report.json"))), 3)
        self.assertEqual(json.loads((output / "final_report.json").read_text())["summary"], report["summary"])
        prompt = json.dumps(self.client.contexts)
        self.assertNotIn("HEADER_SECRET", prompt)
        self.assertNotIn("initial_scores", prompt)
        self.assertNotIn("initial_attendance_fraction_assumed", prompt)
        self.assertEqual(len(self.client.contexts[4]["earlier_validated_memory"]), 4)
        self.assertEqual(self.client.contexts[5]["earlier_validated_memory"], [])

    def test_reports_are_written_before_the_next_model_call(self):
        output = Path(self.directory.name) / "run"

        class Client(RecordingClient):
            def generate(inner, messages, schema):
                number = json.loads(messages[1]["content"])["current_session_number"]
                if number > 1:
                    self.assertTrue((output / "student_00001" / f"session_{number - 1:02d}.json").exists())
                return super().generate(messages, schema)

        self.run_school(self.school(count=1), client=Client())

    def test_capacity_renewal_never_starts_a_second_programme(self):
        school = self.school(count=3, num_months=3)
        school.mentors[0].max_active_students = 1
        report = self.run_school(school)
        self.assertEqual(report["summary"]["assigned_students"], 3)
        self.assertEqual(len({a.student_id for a in school.assignment_history}), 3)
        self.assertEqual([a.month for a in school.assignment_history], [1, 2, 3])
        self.assertTrue(all(a.sessions == 5 for a in school.assignment_history))
        self.assertEqual(len(school.assignments), 3)
        self.assertEqual(school.unassigned_student_ids, [])
        replay = self.run_school(school, folder="replay")
        self.assertEqual(report["assignments"], replay["assignments"])
        self.assertEqual(report["students"], replay["students"])

    def test_configurable_total_dose_never_exposes_later_source_sessions(self):
        report = self.run_school(self.school(count=1, sessions_per_student=3))
        record = next(iter(report["students"].values()))
        self.assertEqual(record["planned_sessions"], 3)
        self.assertEqual(record["sessions_completed"], 3)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(len(self.client.contexts), 3)
        self.assertNotIn("task 4", json.dumps(self.client.contexts))
        self.assertNotIn("task 5", json.dumps(self.client.contexts))

    def test_unused_budget_is_available_to_the_next_admission_window(self):
        short_root = Path(self.directory.name) / "short_histories"
        folder = short_root / "02_tutoring" / "student"
        folder.mkdir(parents=True)
        for number, stage in ((1, "initial"), (2, "followup")):
            (folder / f"session_{number:02d}_{stage}.md").write_text(
                f"**Student:** Task {number} is still difficult.\n", encoding="utf-8")
        school = self.school(num_months=2, budget=7)
        school.mentors[0].max_active_students = 1
        report = school.run_interventions(root=short_root, client=self.client,
                                         output_dir=Path(self.directory.name) / "run")
        self.assertEqual([a.month for a in school.assignment_history], [1, 2])
        self.assertEqual(report["summary"]["recorded_sessions"], 4)
        self.assertEqual(report["summary"]["spent_budget"], 4)
        self.assertEqual(report["summary"]["remaining_budget"], 3)

    def test_budget_skill_and_missing_history_leave_explicit_unassigned_reports(self):
        for budget in (0, 4):
            report = self.run_school(self.school(budget=budget), folder=f"budget_{budget}")
            self.assertEqual(report["summary"]["unassigned_students"], 2)
            self.assertEqual(report["summary"]["spent_budget"], 0)
        mentor = Mentor("specialist", ["family_liaison"], max_active_students=2,
                        availability_by_step=[MentorAvailability(1, 0, 10)])
        report = self.run_school(School(students=[self.student], mentors=[mentor], num_months=1), folder="skills")
        self.assertEqual(report["summary"]["unassigned_students"], 1)
        school = School(students=[replace(self.student, anchor_grade1_0_20=20,
                                         travel_time_category=4)], num_mentors=1)
        report = self.run_school(school, folder="no_history")
        self.assertEqual(report["students"][self.student.student_id]["unassigned_reason"], "no_matching_history")

    def test_existing_caseload_keeps_its_mentor_and_resource_checks(self):
        mentor = Mentor("existing", ["tutoring"], max_active_students=2,
                        current_student_ids=[self.student.student_id],
                        availability_by_step=[MentorAvailability(1, 0, 10)], cost_units_per_session=2)
        school = School(students=[self.student], mentors=[mentor], num_months=1, budget=10)
        report = self.run_school(school)
        record = report["students"][self.student.student_id]
        self.assertEqual(record["mentor_id"], "existing")
        self.assertEqual(record["assignment"]["cost_units"], record["sessions_completed"] * 2)
        replay = self.run_school(school, folder="replay")
        self.assertEqual(report["assignments"], replay["assignments"])

    def test_failed_extraction_keeps_validated_reports_and_records_failure(self):
        class Client(RecordingClient):
            def generate(inner, messages, schema):
                if json.loads(messages[1]["content"])["current_session_number"] == 2:
                    raise RuntimeError("local model unavailable")
                return super().generate(messages, schema)

        report = self.run_school(self.school(count=1), client=Client())
        record = next(iter(report["students"].values()))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(record["status"], "report_failed")
        self.assertEqual(len(record["session_reports"]), 1)
        self.assertIsNone(record["conclusion"])
        self.assertEqual(record["error"], "local model unavailable")
        self.assertTrue((Path(report["output_dir"]) / "student_00001/session_01.json").exists())
        self.assertEqual(report["summary"]["failed_reports"], 1)

    def test_cmdp_score_is_participation_and_existing_outputs_are_protected(self):
        school = self.school()
        environment = SchoolCMDPEnvironment(school)
        output = Path(self.directory.name) / "run"
        report = environment.run_interventions(root=self.root, output_dir=output, client=self.client)
        self.assertEqual(environment.score, 0.7)
        self.assertEqual(report["participation_completion_score"], 0.7)
        self.assertEqual(json.loads((output / "final_report.json").read_text())["participation_completion_score"], 0.7)
        with self.assertRaises(FileExistsError):
            self.run_school(school)


if __name__ == "__main__":
    unittest.main()

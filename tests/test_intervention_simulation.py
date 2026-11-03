"""Observable school/intervention contracts, monthly feedback and confidentiality."""

import ast
from dataclasses import FrozenInstanceError, asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.intervention import Intervention, InterventionRequest, InterventionResult
from src.intervention.session_index import SessionIndex
from src.intervention.transcripts import load_sessions
from src.school import School, Mentor, MentorAvailability
from src.school.performance import current_needs
from tests.helpers import FakeClient, findings, write_history


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
                               family_relationship_rating=5, past_failures_count=0,
                               initial_attendance_fraction_assumed=0.95,
                               initial_engagement_assumed=0.9)
        self.client = FakeClient()

    def school(self, count=2, **options):
        return School(students=[replace(self.student, student_id=f"student{n}") for n in range(count)],
                      num_mentors=1, students_per_mentor=count, **options)

    def intervention(self, client=None, private=False):
        index = SessionIndex()
        self.addCleanup(index.close)
        index.build(load_sessions(self.root))
        return Intervention(index, self.client if client is None else client,
                            private_output_dir=self.directory / "private" if private else None)

    def run_school(self, school, name="run", client=None, private=False):
        return school.run_simulation(self.intervention(client, private), output_dir=self.directory / name)

    def request(self, **overrides):
        fields = dict(run_id="run", programme_id="programme", month=1, student_id="student",
                      mentor_id="mentor", support_type="tutoring", planned_sessions=5)
        return InterventionRequest(**(fields | overrides))

    def test_short_programmes_charge_recordings_and_track_all_students_every_month(self):
        school = self.school(num_months=2, budget=10)
        school.mentors[0].max_active_students = 1
        baseline = [asdict(student) for student in school.students]
        report = self.run_school(school)
        self.assertEqual(report["status"], "finished")
        self.assertEqual(report["spent_budget"], 4)
        self.assertEqual(report["remaining_budget"], 6)
        self.assertEqual([a.month for a in school.assignment_history], [1, 2])
        self.assertEqual([asdict(student) for student in school.students], baseline)
        self.assertEqual([len(e) for e in school.monthly_evaluations.values()], [2, 2])
        first_sid, second_sid = [a.student_id for a in school.assignment_history]
        month_one = {e.student_id: e for e in school.monthly_evaluations[1]}
        self.assertEqual(month_one[second_sid].before, month_one[second_sid].after)
        self.assertEqual(month_one[first_sid].after.support_sessions_completed,
                         self.student.support_sessions_completed + 2)
        self.assertEqual(school.current_month, 3)
        self.assertEqual(len(self.client.contexts), 4)
        self.assertEqual(self.client.contexts[2]["earlier_validated_memory"], [])
        for record in report["students"].values():
            self.assertEqual(record["result"]["status"], "incomplete")
            self.assertEqual(record["result"]["planned_sessions"], 5)
            self.assertEqual(record["result"]["sessions_completed"], 2)
        output = Path(report["output_dir"])
        self.assertTrue((output / "month_01.json").is_file())
        self.assertEqual(json.loads((output / "final_report.json").read_text()), report)

    def test_refunds_admit_later_students_without_refilling_current_month(self):
        school = self.school(count=3, num_months=3, budget=7)
        report = self.run_school(school)
        self.assertEqual([a.month for a in school.assignment_history], [1, 2])
        self.assertEqual([len(school.monthly_assignments[m]) for m in (1, 2, 3)], [1, 1, 0])
        self.assertEqual(report["spent_budget"], 4)
        self.assertEqual(sum(s["result"] is None for s in report["students"].values()), 1)

    def test_planned_session_limit_excludes_future_sessions(self):
        report = self.run_school(self.school(count=1, sessions_per_student=1))
        result = next(iter(report["students"].values()))["result"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sessions_completed"], 1)
        self.assertEqual(len(self.client.contexts), 1)
        self.assertNotIn("task 2", json.dumps(self.client.contexts))

    def test_need_priority_selects_highest_current_need(self):
        low = replace(self.student, student_id="low", anchor_grade1_0_20=8)
        high = replace(self.student, student_id="high", anchor_grade1_0_20=1)
        school = School(students=[low, high], num_mentors=1, num_months=1, budget=5)
        self.run_school(school)
        self.assertEqual([a.student_id for a in school.assignment_history], ["high"])
        school.reset()
        # A school-observed current grade can change priority without editing baseline.
        school.performance["low"].anchor_grade = 0
        self.assertEqual(school.step(1)[0].student_id, "low")
        self.assertEqual(low.anchor_grade1_0_20, 8)

    def test_budget_skills_and_missing_histories_have_distinct_results(self):
        budget = self.run_school(self.school(budget=4), "budget")
        self.assertTrue(all(s["result"] is None for s in budget["students"].values()))
        mentor = Mentor("specialist", ["family_liaison"], 2,
                        availability_by_step=[MentorAvailability(1, 0, 10)])
        skills = self.run_school(School(students=[self.student], mentors=[mentor], num_months=1), "skills")
        self.assertIsNone(skills["students"][self.student.student_id]["result"])
        student = replace(self.student, travel_time_category=4)
        missing_school = School(students=[student], num_mentors=1)
        missing = self.run_school(missing_school, "missing")
        result = missing["students"][student.student_id]["result"]
        self.assertEqual((result["status"], result["analysis_status"]), ("unavailable", "unavailable"))
        self.assertEqual(result["sessions_completed"], 0)
        self.assertEqual(missing["spent_budget"], 0)
        self.assertEqual(len(missing_school.assignment_history), 1)

    def test_capacity_renews_without_second_programmes_and_reset_is_deterministic(self):
        write_history(self.root, "02_tutoring/another", count=1)
        school = self.school(count=3, num_months=12)
        school.mentors[0].max_active_students = 1
        intervention = self.intervention()
        first = school.run_simulation(intervention, output_dir=self.directory / "first")
        first_contexts = json.loads(json.dumps(self.client.contexts))
        self.assertEqual([a.month for a in school.assignment_history], [1, 2, 3])
        self.assertEqual(len({a.student_id for a in school.assignment_history}), 3)
        school.performance["student0"].anchor_grade = 19
        school.reset()
        self.assertEqual(school.performance["student0"].anchor_grade, self.student.anchor_grade1_0_20)
        self.assertEqual(school.intervention_results, {})
        self.assertEqual(school.monthly_evaluations, {})
        self.assertEqual(school.spent_budget, 0)
        self.client.contexts.clear()
        second = school.run_simulation(intervention, output_dir=self.directory / "second")
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["assignments"], second["assignments"])
        self.assertEqual(first_contexts, self.client.contexts)
        self.assertEqual(first["spent_budget"], second["spent_budget"])

    def test_failed_model_keeps_partial_findings_private_and_attendance_independent(self):
        for failure in ("invalid", "network"):
            with self.subTest(failure=failure):
                client = FakeClient(fail_at=2, failure=failure)
                private = self.directory / failure / "private"
                index = SessionIndex()
                self.addCleanup(index.close)
                index.build(load_sessions(self.root))
                intervention = Intervention(index, client, private_output_dir=private)
                report = self.school(count=1).run_simulation(
                    intervention, output_dir=self.directory / failure / "public")
                result = next(iter(report["students"].values()))["result"]
                self.assertEqual(report["status"], "failed")
                self.assertEqual((result["status"], result["analysis_status"]), ("incomplete", "failed"))
                self.assertEqual(result["attendance_improved"], "unknown")
                self.assertEqual(result["sessions_completed"], 2)
                self.assertEqual(report["spent_budget"], 2)
                self.assertTrue((private / "programme_00001/session_01.json").is_file())
                self.assertFalse((private / "programme_00001/session_02.json").exists())
                self.assertTrue(json.loads((private / "programme_00001/private_report.json").read_text())["error"])
                self.assertEqual(len(client.contexts), 2)

    def test_completion_and_analysis_failure_are_separate(self):
        report = self.run_school(self.school(count=1, sessions_per_student=2), client=FakeClient(fail_at=1))
        result = next(iter(report["students"].values()))["result"]
        self.assertEqual((result["status"], result["analysis_status"]), ("completed", "failed"))
        self.assertEqual(result["sessions_completed"], 2)

    def test_existing_mentor_and_external_caseload_restore_on_reset(self):
        mentor = Mentor("existing", ["tutoring"], 2,
                        current_student_ids=[self.student.student_id, "external"],
                        availability_by_step=[MentorAvailability(1, 0, 5)], cost_units_per_session=2)
        school = School(students=[self.student], mentors=[mentor], num_months=1, budget=10)
        report = self.run_school(school)
        result = report["students"][self.student.student_id]["result"]
        self.assertEqual(result["mentor_id"], "existing")
        self.assertEqual(report["spent_budget"], 4)
        school.reset()
        self.assertEqual(mentor.current_student_ids, [self.student.student_id, "external"])

    def test_request_result_are_immutable_scalars_and_controller_is_school_independent(self):
        school = self.school(count=1)
        assignment = school.step(1)[0]
        request = school.make_intervention_request(assignment)
        state = (asdict(school.students[0]), asdict(school.mentors[0]),
                 list(school.assignment_history), school.spent_budget, dict(school.performance))
        with self.assertRaises(FrozenInstanceError):
            request.student_id = "wrong"
        self.assertTrue(all(isinstance(v, (str, int)) for v in asdict(request).values()))
        controller = self.intervention()
        result = controller.simulate(request)
        with self.assertRaises(FrozenInstanceError):
            result.sessions_completed = 0
        self.assertEqual(state, (asdict(school.students[0]), asdict(school.mentors[0]),
                                list(school.assignment_history), school.spent_budget, dict(school.performance)))
        self.assertFalse(list(self.directory.glob("**/final_report.json")))
        with self.assertRaisesRegex(ValueError, "already started"):
            controller.simulate(request)
        with self.assertRaisesRegex(ValueError, "already started"):
            controller.simulate(replace(request, student_id="other"))

    def test_identity_counts_and_duplicate_results_rejected_before_any_school_change(self):
        school = self.school(count=1)
        request = school.make_intervention_request(school.step(1)[0])
        result = self.intervention().simulate(request)
        before = (school.spent_budget, list(school.assignment_history), asdict(school.performance[request.student_id]))
        for changes in ({"run_id": "other"}, {"programme_id": "other"}, {"student_id": "other"},
                        {"mentor_id": "other"}, {"month": 2}, {"planned_sessions": 6},
                        {"support_type": "peer_support"}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "match"):
                school.apply_intervention_result(replace(result, **changes))
            self.assertEqual(before, (school.spent_budget, list(school.assignment_history),
                                     asdict(school.performance[request.student_id])))
        for count in (-1, 6, True):
            with self.assertRaises(ValueError):
                replace(result, sessions_completed=count)
        school.apply_intervention_result(result)
        after = (school.spent_budget, list(school.assignment_history), asdict(school.performance[request.student_id]))
        with self.assertRaisesRegex(ValueError, "already been applied"):
            school.apply_intervention_result(result)
        self.assertEqual(after, (school.spent_budget, list(school.assignment_history),
                                asdict(school.performance[request.student_id])))

    def test_month_two_sees_month_one_outcomes_without_numeric_or_baseline_changes(self):
        class ImprovingClient(FakeClient):
            def generate(self, messages, schema):
                result = super().generate(messages, schema)
                result["outcome"]["attendance_improved"] = "yes"
                return result
        school = self.school(count=1, num_months=2)
        baseline = asdict(school.students[0])
        self.run_school(school, client=ImprovingClient())
        first, second = school.monthly_evaluations[1][0], school.monthly_evaluations[2][0]
        self.assertEqual(first.before.attendance_improved, "unknown")
        self.assertEqual(first.after.attendance_improved, "yes")
        self.assertEqual(first.after, second.before)
        self.assertEqual(first.before.attendance_fraction, second.after.attendance_fraction)
        self.assertEqual(first.before.anchor_grade, second.after.anchor_grade)
        self.assertEqual(first.before.need_score, second.after.need_score)
        self.assertEqual(asdict(school.students[0]), baseline)
        self.assertEqual(second.after.support_sessions_completed, self.student.support_sessions_completed + 2)

    def test_unknown_outcomes_and_failed_analysis_leave_measures_unchanged_with_reason(self):
        for name, client in (("unknown", FakeClient()), ("failed", FakeClient(fail_at=1))):
            school = self.school(count=1, num_months=1)
            self.run_school(school, name, client)
            evaluation = school.monthly_evaluations[1][0]
            self.assertEqual(evaluation.after.attendance_improved, "unknown")
            self.assertEqual(evaluation.before.anchor_grade, evaluation.after.anchor_grade)
            self.assertEqual(evaluation.before.attendance_fraction, evaluation.after.attendance_fraction)
            self.assertIn("unknown_outcomes", evaluation.after.evaluation_reason)
            if name == "failed":
                self.assertIn("analysis_failed", evaluation.after.evaluation_reason)

    def test_conflicting_outcomes_do_not_overwrite_reported_state(self):
        school = self.school(count=1)
        assignment = school.step(1)[0]
        request = school.make_intervention_request(assignment)
        school.performance[request.student_id].attendance_improved = "yes"
        result = replace(self.intervention().simulate(request), attendance_improved="conflicting")
        school.apply_intervention_result(result)
        performance = school.performance[request.student_id]
        self.assertEqual(performance.attendance_improved, "yes")
        self.assertEqual(performance.attendance_fraction, self.student.initial_attendance_fraction_assumed)
        self.assertIn("conflicting_outcomes_unchanged:attendance_improved", performance.evaluation_reason)

    def test_no_private_text_or_history_references_in_any_school_file(self):
        class SecretClient(FakeClient):
            def generate(self, messages, schema):
                result = findings()
                result["conclusion"] = "PRIVATE_SECRET"
                result["next_steps"] = ["PRIVATE_SECRET"]
                return result
        school = self.school(count=1)
        self.run_school(school, client=SecretClient(), private=True)
        for path in (self.directory / "run").rglob("*.json"):
            text = path.read_text()
            for secret in ("PRIVATE_SECRET", "history_id", "history_path", "session_summary",
                           "conclusion", "next_steps", "session_reports", str(self.directory / "private")):
                self.assertNotIn(secret, text, str(path))
        private_text = (self.directory / "private/programme_00001/private_report.json").read_text()
        self.assertIn("PRIVATE_SECRET", private_text)
        self.assertFalse(hasattr(school, "intervention_profiles"))

    def test_fresh_memory_for_pairs_runs_and_reassignments(self):
        controller = self.intervention()
        for request in (self.request(), self.request(programme_id="second", student_id="other"),
                        self.request(run_id="other_run"),
                        self.request(programme_id="reassigned", mentor_id="new_mentor")):
            controller.simulate(request)
        self.assertEqual(len(self.client.contexts), 8)
        self.assertTrue(all(self.client.contexts[n]["earlier_validated_memory"] == [] for n in (0, 2, 4, 6)))

    def test_zero_agents_and_default_twelve_months(self):
        for students, mentors in ((0, 0), (2, 0)):
            school = School(num_students=students, num_mentors=mentors)
            report = self.run_school(school, f"empty_{students}")
            self.assertEqual(len(school.monthly_evaluations), 12)
            self.assertEqual(len(report["students"]), students)
            self.assertEqual(report["spent_budget"], 0)
            self.assertEqual(self.client.contexts, [])

    def test_existing_output_directory_is_protected_before_reset(self):
        school = self.school()
        self.run_school(school)
        run_id = school.run_id
        with self.assertRaises(FileExistsError):
            self.run_school(school)
        self.assertEqual(school.run_id, run_id)

    def test_malformed_history_rejected_before_generation(self):
        path = self.root / "02_tutoring/student/session_01_initial.md"
        path.rename(path.with_name("session_03_followup.md"))
        with self.assertRaisesRegex(ValueError, "consecutive"):
            self.intervention()
        self.assertEqual(self.client.contexts, [])

    def test_intervention_never_imports_school(self):
        root = Path(__file__).resolve().parents[1] / "src/intervention"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn("school", (node.module or "").split("."), str(path))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn("school", alias.name.split("."), str(path))


if __name__ == "__main__":
    unittest.main()

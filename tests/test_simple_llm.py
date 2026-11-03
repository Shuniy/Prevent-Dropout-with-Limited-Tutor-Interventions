import copy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.intervention import Intervention, InterventionRequest
from src.intervention.session import Session
from src.intervention.simple_llm import SimpleLLM, main
from tests.helpers import FakeClient


class SimpleLLMTests(unittest.TestCase):
    def setUp(self):
        self.sessions = [
            Session("tutoring/student", 2, ("Student: The agreed task is still pending.",)),
            Session("tutoring/student", 1, ("Student: I need help with fractions.",)),
            Session("tutoring/student", 3, ("Student: FUTURE_SECRET",)),
            Session("reentry_support/other", 1, ("Student: OTHER_SECRET",)),
        ]
        self.client = FakeClient()

    def test_one_call_receives_all_selected_turns_without_retrieval_or_memory(self):
        saved = []
        with patch("src.intervention.session_index.SessionIndex", side_effect=AssertionError("no index")):
            report = SimpleLLM(self.sessions, self.client).analyse(
                "tutoring/student", 2, on_session=saved.append)
        self.assertEqual(len(self.client.contexts), 1)
        context = self.client.contexts[0]
        self.assertEqual([s["session_number"] for s in context["sessions"]], [1, 2])
        self.assertEqual(context["sessions"][0]["conversation"],
                         [{"turn_number": 1, "speaker": "Student", "utterance": "I need help with fractions."}])
        self.assertEqual(context["record_scope"], {"first_supplied_session": 1,
                         "last_supplied_session": 2, "session_count": 2})
        self.assertEqual([s["conversation_position"] for s in context["sessions"]], [1, 2])
        self.assertEqual([s["prior_session_numbers"] for s in context["sessions"]], [[], [1]])
        self.assertIn("first supplied conversation", context["sessions"][0]["chronology_label"])
        self.assertEqual(context["sessions"][1]["chronology_label"], "Conversation 2 of 2")
        self.assertNotIn("SECRET", json.dumps(context))
        self.assertEqual(set(report), {"history_id", "as_of_session", "timeline", "conclusion"})
        self.assertEqual(saved, report["timeline"])
        self.assertEqual(report["conclusion"], report["timeline"][-1]["findings"])

    def test_sparse_source_numbers_keep_position_separate_and_pass_metadata(self):
        sessions = [Session("s", 5, ("Student: Later progress.",)),
                    Session("s", 2, ("Student: Initial difficulty.",),
                            intervention_type="Tutoring", date="2026-09-10", stage="Initial session")]
        with patch.object(self.client, "generate", wraps=self.client.generate) as generate:
            SimpleLLM(sessions, self.client).analyse("s")
        context = self.client.contexts[0]
        self.assertEqual([s["session_number"] for s in context["sessions"]], [2, 5])
        self.assertEqual(context["sessions"][1]["prior_session_numbers"], [2])
        self.assertEqual(context["sessions"][0]["metadata"], {
            "intervention_type": "Tutoring", "date": "2026-09-10", "stage": "Initial session"})
        self.assertEqual(context["sessions"][1]["metadata"], {})
        system = generate.call_args_list[0].args[0][0]["content"]
        self.assertIn("school-support intervention", system)
        self.assertIn("never use later disclosures", system)

    def test_bad_history_cutoff_and_budget_fail_before_generation(self):
        for history, cutoff in [("missing", None), ("tutoring/student", 4)]:
            with self.assertRaises(ValueError):
                SimpleLLM(self.sessions, self.client).analyse(history, cutoff)
        with self.assertRaisesRegex(ValueError, "prompt budget"):
            SimpleLLM(self.sessions, self.client, max_prompt_chars=1).analyse("tutoring/student")
        self.assertEqual(self.client.contexts, [])

    def test_invalid_response_never_saves_partial_timeline_or_retries(self):
        valid = FakeClient().generate([
            {}, {"content": json.dumps({"sessions": [{"session_number": 1}, {"session_number": 2}]})}
        ], {})
        malformed = []
        missing = copy.deepcopy(valid)
        missing["timeline"].pop()
        malformed.append(missing)
        invalid = copy.deepcopy(valid)
        invalid["timeline"][1]["findings"]["outcome"]["attendance_improved"] = "invented"
        malformed.append(invalid)
        duplicate = copy.deepcopy(valid)
        duplicate["timeline"][1]["session_number"] = 1
        malformed.append(duplicate)
        reversed_steps = copy.deepcopy(valid)
        reversed_steps["timeline"].reverse()
        malformed.append(reversed_steps)
        malformed.append({})
        for response in malformed:
            saved = []
            with self.subTest(response=response), patch.object(self.client, "generate", return_value=response) as generate:
                with self.assertRaises(ValueError):
                    SimpleLLM(self.sessions, self.client).analyse("tutoring/student", 2, on_session=saved.append)
                generate.assert_called_once()
                self.assertEqual(saved, [])

    def test_duplicate_or_empty_source_sessions_are_rejected(self):
        for sessions in ([self.sessions[0], self.sessions[0]], [Session("s", 1, ())]):
            with self.assertRaises(ValueError):
                SimpleLLM(sessions, self.client)

    def test_default_intervention_saves_existing_private_structure_without_index(self):
        request = InterventionRequest("run", "programme", 1, "student", "mentor", "tutoring", 2)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "private"
            result = Intervention(self.sessions, self.client, private_output_dir=destination).simulate(request)
            self.assertEqual(result.analysis_status, "completed")
            self.assertEqual(result.sessions_completed, 2)
            self.assertEqual(len(self.client.contexts), 1)
            folder = destination / "programme_00001"
            self.assertEqual({path.name for path in folder.iterdir()},
                             {"session_01.json", "session_02.json", "private_report.json"})
            private = json.loads((folder / "private_report.json").read_text())
            self.assertEqual(private["result"], asdict(result))
            self.assertEqual(set(private), set(asdict(request)) | {"history_id", "error", "result", "conclusion"})

    def test_batch_failure_keeps_recorded_attendance_and_private_error(self):
        request = InterventionRequest("run", "programme", 1, "student", "mentor", "tutoring", 2)
        for failure in ("invalid", "network"):
            with tempfile.TemporaryDirectory() as directory:
                client = FakeClient(fail_at=2, failure=failure)
                result = Intervention(self.sessions, client, private_output_dir=Path(directory)).simulate(request)
                self.assertEqual((result.sessions_completed, result.analysis_status), (2, "failed"))
                self.assertEqual(result.intervention_helpful, "unknown")
                folder = Path(directory) / "programme_00001"
                self.assertEqual([path.name for path in folder.iterdir()], ["private_report.json"])
                self.assertTrue(json.loads((folder / "private_report.json").read_text())["error"])
                self.assertEqual(len(client.contexts), 1)

    def test_standalone_simple_command_uses_same_report_contract(self):
        from tests.helpers import write_history
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_history(root)
            output = root / "result.json"
            arguments = ["simple", "02_tutoring/student", "--root", str(root), "--output", str(output)]
            with patch("sys.argv", arguments), patch("src.intervention.simple_llm.OllamaClient", return_value=self.client), contextlib.redirect_stdout(io.StringIO()):
                main()
            self.assertEqual(json.loads(output.read_text())["as_of_session"], 2)
            self.assertEqual(len(self.client.contexts), 1)


if __name__ == "__main__":
    unittest.main()

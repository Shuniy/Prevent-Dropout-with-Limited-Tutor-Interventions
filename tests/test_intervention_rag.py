import json
from pathlib import Path
import tempfile
import unittest

from src.intervention.rag import InterventionRAG
from src.intervention.session import Session
from src.intervention.session_index import SessionIndex
from src.intervention.transcripts import load_sessions
from tests.helpers import FakeClient, write_history


class RAGTests(unittest.TestCase):
    def setUp(self):
        self.index = SessionIndex()
        self.addCleanup(self.index.close)
        self.index.build([
            Session("transport/student", 1, ("Student: I cannot pay bus fares.",)),
            Session("transport/student", 2, ("Mentor: The application was submitted.",)),
            Session("transport/student", 3, ("Student: FUTURE_SECRET",)),
            Session("tutoring/student", 1, ("Student: OTHER_SECRET",)),
        ])

    def test_retrieval_only_uses_earlier_sessions_from_the_same_history(self):
        passages = self.index.retrieve("transport/student", "bus fares application", 3)
        self.assertEqual([p.session_number for p in passages], [1, 2])
        self.assertNotIn("SECRET", json.dumps([p.text for p in passages]))
        self.assertEqual(self.index.retrieve("transport/student", "bus", 1), [])

    def test_matching_passages_and_fallback_are_available(self):
        self.index.build([Session("s", 1, (
            "Student: bus fares", "Mentor: apply", "Student: unrelated", "Mentor: ending"))], 2)
        self.assertEqual(self.index.retrieve("s", "fares", 2, 1)[0].text,
                         "Student: bus fares\n\nMentor: apply")
        self.assertIn("ending", self.index.retrieve("s", "", 2, 1)[0].text)

    def test_later_sessions_receive_previous_findings(self):
        client = FakeClient()
        report = InterventionRAG(self.index, client).analyse("transport/student", 2)
        self.assertEqual(report["as_of_session"], 2)
        self.assertEqual(client.contexts[0]["earlier_validated_memory"], [])
        self.assertEqual(client.contexts[1]["earlier_validated_memory"], report["timeline"][:1])
        self.assertIn("bus fares", json.dumps(client.contexts[1]))
        self.assertNotIn("SECRET", json.dumps(client.contexts))
        self.assertEqual(report["conclusion"], report["timeline"][-1]["findings"])

    def test_invalid_findings_stop_without_retry(self):
        client = FakeClient(fail_at=2)
        saved = []
        with self.assertRaisesRegex(ValueError, "Session 2: Invalid findings"):
            InterventionRAG(self.index, client).analyse("transport/student", 2, on_session=saved.append)
        self.assertEqual(len(client.contexts), 2)
        self.assertEqual([step["session_number"] for step in saved], [1])

    def test_invalid_history_cutoff_and_prompt_size_fail_before_generation(self):
        client = FakeClient()
        rag = InterventionRAG(self.index, client)
        for history, cutoff in [("missing", 1), ("transport/student", 4)]:
            with self.assertRaises(ValueError):
                rag.analyse(history, cutoff)
        with self.assertRaisesRegex(ValueError, "prompt budget"):
            InterventionRAG(self.index, client, max_prompt_chars=1).analyse("transport/student", 1)
        self.assertEqual(client.contexts, [])

    def test_transcript_loader_excludes_headers_and_handles_multiline_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_history(root)
            path = root / "02_tutoring/student/session_01_initial.md"
            path.write_text(path.read_text().replace("Practice task 1", "First line\nPractice task 1"))
            sessions = load_sessions(root)
        self.assertEqual(len(sessions), 2)
        self.assertIn("First line\nPractice task 1", sessions[0].text)
        self.assertNotIn("HEADER_SECRET", sessions[0].text)


if __name__ == "__main__":
    unittest.main()

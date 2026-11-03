import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.intervention.rag import (
    HISTORIES, InterventionRAG, Session, SessionIndex, load_sessions, map_evidence, validate_conclusion,
)


def finding(number, quote):
    evidence = [{"session_number": number, "quote": quote}]
    return {
        "session_summary": "Transport support remains pending.",
        "primary_concern": "transport_cost",
        "tracked_details": [{"detail": "Transport support", "status": "pending", "evidence": evidence}],
        "intervention": {"type": "transport_support", "status": "pending", "service_delivered": None,
                         "delivery_evidence": []},
        "outcome": {"primary_barrier_resolved": "unknown", "attendance_improved": "unknown",
                    "intervention_helpful": "unknown", "outcome_evidence": []},
        "session_helpful": "unknown", "next_steps": ["Check application"],
        "uncertainties": ["Delivery unverified"], "conclusion": "No delivery evidence.",
        "evidence": evidence,
    }


def generated_finding(context, evidence_id=None):
    """A model response selects a source ID rather than rewriting its words."""
    turn = context["current_conversation"][0]
    result = finding(context["current_session_number"], turn["utterance"])
    return map_evidence(result, lambda evidence: {"evidence_id": evidence_id or turn["evidence_id"]})


class RAGTests(unittest.TestCase):
    def setUp(self):
        self.index = SessionIndex()
        self.addCleanup(self.index.close)
        self.sessions = [
            Session("transport/student_001", 1, "a/1.md", ("Student: I cannot pay bus fares.",)),
            Session("transport/student_001", 2, "a/2.md", ("Mentor: The application was submitted.",)),
            Session("transport/student_001", 3, "a/3.md", ("Student: Still pending; I missed another day.",)),
            Session("transport/student_001", 4, "a/4.md", ("Student: FUTURE_SECRET",)),
            Session("tutoring/student_001", 1, "b/1.md", ("Student: OTHER_STUDENT_SECRET",)),
        ]
        self.index.build(self.sessions)

    def test_retrieval_scopes_student_and_excludes_current_and_future(self):
        passages = self.index.retrieve("transport/student_001", "bus fares application pending", 4)
        self.assertEqual([p.session_number for p in passages], [1, 2, 3])
        text = json.dumps([p.text for p in passages])
        self.assertNotIn("SECRET", text)
        self.assertEqual(self.index.retrieve("transport/student_001", "bus", 1), [])

    def test_bm25_finds_matching_chunk_and_fallback_preserves_session(self):
        self.index.build([Session("s", 1, "1.md", (
            "Student: bus fares", "Mentor: apply", "Student: unrelated", "Mentor: ending"))], 2)
        self.assertEqual(self.index.retrieve("s", "fares", 2, 1)[0].chunk, 0)
        self.assertEqual(self.index.retrieve("s", "", 2, 1)[0].chunk, 1)

    def test_rebuild_removes_deleted_sources_and_rejects_duplicate_sessions(self):
        self.index.build(self.sessions[:1])
        self.assertEqual(len(self.index.retrieve("transport/student_001", "bus", 4)), 1)
        with self.assertRaises(ValueError):
            self.index.build(self.sessions[:1] * 2)

    def test_real_corpus_ignores_labels_and_has_unique_full_history_ids(self):
        sessions = load_sessions(HISTORIES)
        self.assertEqual(len(sessions), 390)
        self.assertEqual(len({s.student_id for s in sessions}), 130)
        self.assertTrue(all("Intervention type:" not in s.text for s in sessions))
        self.assertTrue(all("series_end_status" not in s.text for s in sessions))

    def test_multiline_spoken_turns_and_header_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "support" / "student"
            path.mkdir(parents=True)
            (path / "session_01_initial.md").write_text(
                "# Student\n**Intervention type:** SECRET\n\n"
                "**Student:** First line\nsecond line\n\n**Mentor:** Okay.\n")
            session = load_sessions(Path(directory))[0]
            self.assertEqual(session.turns[0], "Student: First line\nsecond line")
            self.assertNotIn("SECRET", session.text)

    def test_replay_preserves_memory_and_provenance_at_cutoff(self):
        calls = []

        class Client:
            model = "test"

            def generate(self, messages, schema):
                context = json.loads(messages[1]["content"])
                calls.append(context)
                return generated_finding(context)

        report = InterventionRAG(self.index, Client()).analyse("transport/student_001", 3)
        self.assertEqual(report["as_of_session"], 3)
        self.assertEqual(len(calls[0]["earlier_validated_memory"]), 0)
        self.assertEqual(len(calls[2]["earlier_validated_memory"]), 2)
        self.assertIn("I cannot pay bus fares.", json.dumps(calls[2]))
        self.assertNotIn("SECRET", json.dumps(calls))
        # Relative source paths contain intervention labels; keep them in the
        # audit report, outside the extraction prompt.
        self.assertNotIn('"source"', json.dumps(calls))
        self.assertEqual(report["timeline"][0]["sha256"], self.sessions[0].digest)
        self.assertIn("evidence_id", json.dumps(calls[1]["earlier_validated_memory"]))
        self.assertNotIn("evidence_id", json.dumps(report))

    def test_source_ids_preserve_punctuation_and_single_utterance_boundaries(self):
        utterance = "For today’s work, check the authorised support office."
        self.index.build([Session("s", 1, "1.md", (
            f"Mentor: {utterance}", "Student: I can ask tomorrow."))])

        class Client:
            model = "test"

            def generate(self, messages, schema):
                context = json.loads(messages[1]["content"])
                result = generated_finding(context)
                result["conclusion"] = f"The barrier remains (evidence {context['current_conversation'][0]['evidence_id']})."
                return result

        report = InterventionRAG(self.index, Client()).analyse("s")
        self.assertEqual(report["conclusion"]["evidence"], [{"session_number": 1, "quote": utterance}])
        self.assertNotIn("Student:", report["conclusion"]["evidence"][0]["quote"])
        self.assertEqual(report["conclusion"]["conclusion"], "The barrier remains.")

    def test_schema_quotes_and_unsupported_helpfulness_are_rejected(self):
        good = finding(1, "I cannot pay bus fares.")
        visible = {1: ["I cannot pay bus fares."]}
        validate_conclusion(good, visible)
        for change in ("future", "invented", "effect", "delivery", "extra", "outcome"):
            bad = copy.deepcopy(good)
            if change == "future":
                bad["evidence"][0]["session_number"] = 4
            elif change == "invented":
                bad["evidence"][0]["quote"] = "The bus pass arrived"
            elif change == "effect":
                bad["outcome"]["intervention_helpful"] = "yes"
            elif change == "delivery":
                bad["intervention"]["service_delivered"] = True
            elif change == "extra":
                bad["unexpected"] = True
            else:
                bad["outcome"]["attendance_improved"] = "yes"
            with self.subTest(change=change), self.assertRaises(Exception):
                validate_conclusion(bad, visible)

    def test_observed_unresolved_barrier_is_not_overwritten_to_unknown(self):
        result = finding(3, "Still pending; I missed another day.")
        result["outcome"]["primary_barrier_resolved"] = "no"
        result["outcome"]["outcome_evidence"] = result["evidence"]
        validate_conclusion(result, {3: ["Still pending; I missed another day."]})
        self.assertEqual(result["outcome"]["primary_barrier_resolved"], "no")

    def test_repair_is_bounded_and_rejected_output_never_enters_memory(self):
        class Client:
            model = "test"
            calls = 0

            def generate(self, messages, schema):
                self.calls += 1
                context = json.loads(messages[1]["content"])
                return generated_finding(context, "e99999" if self.calls == 1 else None)

        client = Client()
        report = InterventionRAG(self.index, client).analyse("transport/student_001", 1)
        self.assertEqual(client.calls, 2)
        self.assertEqual(len(report["timeline"][0]["validation_failures"]), 1)
        self.assertNotIn("e99999", json.dumps(report["conclusion"]))
        with self.assertRaisesRegex(ValueError, "after 1 attempts"):
            InterventionRAG(self.index, Client(), validation_retries=0).analyse("transport/student_001", 1)

    def test_invalid_cutoff_unknown_student_and_prompt_overflow_fail(self):
        for student, cutoff in [("student_001", 1), ("transport/student_001", 5)]:
            with self.assertRaises(ValueError):
                self.index.history(student, cutoff)
        with self.assertRaisesRegex(ValueError, "prompt budget"):
            InterventionRAG(self.index, max_prompt_chars=1).analyse("transport/student_001", 1)


if __name__ == "__main__":
    unittest.main()

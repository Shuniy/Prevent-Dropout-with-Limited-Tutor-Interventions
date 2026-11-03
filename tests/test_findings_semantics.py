"""Evidence, scope, chronology and persistence regressions; no live model required."""

import copy
import json
import unittest
from unittest.mock import patch

from src.intervention.findings import validate_findings
from src.intervention.rag import InterventionRAG
from src.intervention.semantic_validation import source_backed_actions, validate_semantics
from src.intervention.session import Session
from src.intervention.session_index import SessionIndex
from src.intervention.simple_llm import SimpleLLM
from tests.helpers import FakeClient, findings


HISTORY = "homework/student"
SESSIONS = [
    Session(HISTORY, 2, (
        "Student: I will submit both assignments by Friday.",
        "Student: I have not started yet.",
    ), date="2026-09-10"),
    Session(HISTORY, 5, (
        "Student: I submitted one assignment; the other is still unfinished.",
        "Mentor: We completed our review of your progress.",
    ), date="2026-09-17"),
    Session(HISTORY, 8, ("Student: I now submitted both assignments.",), date="2026-09-24"),
]


def cite(number, turn=1, quote=None):
    source = next(s for s in SESSIONS if s.number == number)
    return {"history_id": HISTORY, "session_number": number, "turn_number": turn,
            "quote": quote or source.turns[turn - 1].split(": ", 1)[1]}


def action(status="not_started", evidence=None):
    return {"action_id": f"{HISTORY}:s2:a1",
            "original_action": cite(2)["quote"], "responsible_person": "Student",
            "agreed_on": "2026-09-10", "due_date": "by Friday",
            "original_evidence": cite(2), "status": status,
            "status_evidence": evidence if evidence is not None else [cite(2, 2)]}


def with_action(status="not_started", evidence=None):
    result = findings()
    result["actions"] = [action(status, evidence)]
    return result


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()

    def validate(self, result, sources=None, previous=None):
        validate_findings(result)
        validate_semantics(result, sources or SESSIONS[:1], previous or [], self.client)

    def test_known_statuses_require_verbatim_source_evidence(self):
        cases = [
            ("not_started", [cite(2, 2)], SESSIONS[:1]),
            ("partially_completed", [cite(5)], SESSIONS[:2]),
            ("completed", [cite(8)], SESSIONS),
            ("unknown", [], SESSIONS[:1]),
        ]
        for status, evidence, sources in cases:
            with self.subTest(status=status):
                self.validate(with_action(status, evidence), sources)
        self.assertEqual(len(self.client.reviews), 4)
        invalid = with_action("completed", [])
        with self.assertRaisesRegex(ValueError, "known action status requires evidence"):
            self.validate(invalid)
        invalid = with_action()
        invalid["actions"][0]["status_evidence"][0]["quote"] = "Invented completion."
        with self.assertRaisesRegex(ValueError, "not verbatim"):
            self.validate(invalid)

    def test_citations_cannot_use_future_other_history_or_wrong_turn(self):
        for ref in (cite(8), {**cite(2), "history_id": "other/student"},
                    {**cite(2), "turn_number": 99}):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "unavailable source turn"):
                self.validate(with_action("completed", [ref]))
        self.assertEqual(self.client.reviews, [])

    def test_original_identity_wording_dates_and_deadline_are_preserved(self):
        original = with_action()
        previous = source_backed_actions([{"session_number": 2, "findings": original}], SESSIONS[:1])
        for field, replacement in (("original_action", "Submit one assignment"),
                                   ("responsible_person", "Mentor"),
                                   ("agreed_on", "2026-09-17"), ("due_date", "Friday"),
                                   ("action_id", f"{HISTORY}:s2:a2")):
            changed = copy.deepcopy(original)
            changed["actions"][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(changed, SESSIONS[:2], previous)
        duplicate = copy.deepcopy(original)
        duplicate["actions"].append({**duplicate["actions"][0], "action_id": f"{HISTORY}:s2:a2"})
        with self.assertRaisesRegex(ValueError, "multiple IDs"):
            self.validate(duplicate)

    def test_silence_retains_actions_and_status_changes_need_new_evidence(self):
        original = with_action()
        previous = source_backed_actions([{"session_number": 2, "findings": original}], SESSIONS[:1])
        self.validate(original, SESSIONS[:2], previous)
        with self.assertRaisesRegex(ValueError, "carried forward"):
            self.validate(findings(), SESSIONS[:2], previous)
        changed = copy.deepcopy(original)
        changed["actions"][0]["status"] = "completed"
        with self.assertRaisesRegex(ValueError, "without new current-session evidence"):
            self.validate(changed, SESSIONS[:2], previous)

    def test_delivery_and_helpfulness_are_scoped_to_intended_components(self):
        sources = [Session(HISTORY, 2, (
            "Mentor: We filled out your transport application together.",
            "Student: The transport grant is still pending.",
            "Student: This meeting helped clarify the application.",
        ))]
        result = findings()
        result["intervention"] = {
            "intended_intervention": {"type": "transport grant", "status": "pending",
                                      "component_ids": ["grant"], "evidence": [cite(2, 2, "The transport grant is still pending.")]},
            "direct_activities": [{"component_id": "application", "description": "Application preparation",
                                   "status": "delivered", "evidence": [cite(2, 1, "We filled out your transport application together.")]}],
            "external_support": [{"component_id": "grant", "description": "Transport grant",
                                  "status": "pending", "evidence": [cite(2, 2, "The transport grant is still pending.")]}],
        }
        result["session_helpful"] = "yes"
        result["session_helpful_evidence"] = [cite(2, 3, "This meeting helped clarify the application.")]
        self.validate(result, sources)
        result["outcome"]["intervention_helpful"] = "yes"
        result["outcome_evidence"]["intervention_helpful"] = result["session_helpful_evidence"]
        with self.assertRaisesRegex(ValueError, "delivery of all intended components"):
            self.validate(result, sources)
        result["outcome"]["intervention_helpful"] = "unknown"
        result["intervention"]["intended_intervention"]["status"] = "completed"
        with self.assertRaisesRegex(ValueError, "delivered intended components"):
            self.validate(result, sources)

    def test_outcome_claims_and_non_delivery_need_citations(self):
        result = findings()
        result["outcome"]["attendance_improved"] = "no"
        with self.assertRaisesRegex(ValueError, "attendance_improved requires evidence"):
            self.validate(result)
        result = findings()
        result["intervention"]["external_support"] = [{
            "component_id": "grant", "description": "Grant", "status": "not_received", "evidence": []}]
        with self.assertRaisesRegex(ValueError, "component status requires evidence"):
            self.validate(result)

    def test_independent_review_can_reject_review_as_task_completion(self):
        result = with_action("completed", [cite(5, 2)])
        result["conclusion"] = "Both assignments are complete."
        issue = {"issues": [{"path": "actions[0].status",
                             "reason": "Only the progress review is complete; the second assignment is unfinished."}]}
        with patch.object(self.client, "generate", return_value=issue) as review:
            with self.assertRaisesRegex(ValueError, "second assignment is unfinished"):
                self.validate(result, SESSIONS[:2])
        context = json.loads(review.call_args.args[0][1]["content"])
        self.assertEqual(context["candidate_findings"]["conclusion"], result["conclusion"])
        self.assertIn("I will submit both assignments", json.dumps(context["cited_source_turns"]))

    def test_malformed_semantic_review_is_rejected(self):
        with patch.object(self.client, "generate", return_value={"accepted": True}):
            with self.assertRaisesRegex(ValueError, "invalid semantic review"):
                self.validate(findings())

    def test_status_history_keeps_original_and_each_report_with_source_dates(self):
        timeline = [
            {"session_number": 2, "findings": with_action()},
            {"session_number": 5, "findings": with_action("partially_completed", [cite(5)])},
            {"session_number": 8, "findings": with_action("completed", [cite(8)])},
        ]
        record = source_backed_actions(timeline, SESSIONS)[0]
        self.assertEqual(record["original_action"], cite(2)["quote"])
        self.assertEqual(record["original_source_turn"]["date"], "2026-09-10")
        self.assertEqual([r["reported_status"] for r in record["status_history"]],
                         ["not_started", "partially_completed", "completed"])
        self.assertEqual([r["source_turns"][0]["date"] for r in record["status_history"]],
                         ["2026-09-10", "2026-09-17", "2026-09-24"])


class EvidencePipelineTests(unittest.TestCase):
    def test_rag_pins_action_sources_even_when_retrieval_omits_them(self):
        class ActionClient(FakeClient):
            def generate(self, messages, schema):
                result = super().generate(messages, schema)
                if "issues" in result:
                    return result
                number = self.contexts[-1]["current_session_number"]
                return with_action() if number == 2 else with_action("partially_completed", [cite(5)])
        index = SessionIndex()
        self.addCleanup(index.close)
        index.build(SESSIONS)
        client = ActionClient()
        with patch.object(index, "retrieve", return_value=[]):
            report = InterventionRAG(index, client).analyse(HISTORY, 5)
        record = client.contexts[1]["source_backed_actions"][0]
        self.assertEqual(record["original_source_turn"]["session_number"], 2)
        self.assertEqual(record["original_source_turn"]["date"], "2026-09-10")
        self.assertEqual(record["status_history"][0]["reported_status"], "not_started")
        self.assertNotIn("2026-09-24", json.dumps(client.contexts + client.reviews))
        self.assertEqual(report["conclusion"]["actions"][0]["status"], "partially_completed")

    def test_semantic_failure_stops_persistence_in_both_modes(self):
        class RejectingClient(FakeClient):
            def generate(self, messages, schema):
                result = super().generate(messages, schema)
                if "issues" in result and self.reviews[-1]["as_of_session"] == 5:
                    return {"issues": [{"path": "conclusion", "reason": "Unsupported completion claim"}]}
                return result
        index = SessionIndex()
        self.addCleanup(index.close)
        index.build(SESSIONS)
        for mode in ("simple", "rag"):
            client = RejectingClient()
            analyser = SimpleLLM(SESSIONS, client) if mode == "simple" else InterventionRAG(index, client)
            saved = []
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "Unsupported completion claim"):
                analyser.analyse(HISTORY, 5, on_session=saved.append)
            self.assertEqual([s["session_number"] for s in saved], [] if mode == "simple" else [2])
            self.assertEqual(len(client.reviews), 2)
            self.assertNotIn("now submitted both", json.dumps(client.contexts + client.reviews))

    def test_retrieved_chunks_keep_absolute_turn_numbers(self):
        index = SessionIndex()
        self.addCleanup(index.close)
        index.build([Session(HISTORY, 2, ("Student: First.", "Mentor: Second.",
                                         "Student: Third.", "Mentor: Fourth.")),
                     Session(HISTORY, 5, ("Student: Current.",))], turns_per_chunk=2)
        client = FakeClient()
        with patch.object(index, "retrieve", wraps=index.retrieve):
            InterventionRAG(index, client).analyse(HISTORY, 5, question="Third")
        passages = client.contexts[1]["retrieved_prior_passages"]
        third = next(turn for passage in passages for turn in passage["conversation"]
                     if turn["utterance"] == "Third.")
        self.assertEqual(third["turn_number"], 3)


if __name__ == "__main__":
    unittest.main()

"""Matched note channels, honest manifests and policy-facing information boundaries."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.evaluation.research_experiments import (load_config, make_controller,
    digest_controller, freeze, checked_manifest, aggregate, require_pilot, secondary)
from src.intervention.feedback_notes import NoteQuality, render_note
from src.intervention.observation_extractor import FixtureObservationExtractor
from src.school.student_condition import StudentCondition as S
from src.observations.observable_events import ObservableEvent


class ResearchInformationTests(unittest.TestCase):
    def setUp(self):
        config = load_config()
        self.config = {**config, "scenario": {**config["scenario"], "num_students": 12,
            "horizon": 3, "budget": 15, "monthly_admissions": 1, "monthly_appointments": 5}}

    def test_gold_and_extracted_modes_have_identical_corrupted_content_and_cutoffs(self):
        gold = make_controller(self.config, "FairPoint", "d_matched", 0)
        extracted = make_controller(self.config, "FairPoint", "noisy_notes", 0,
                                    extractor=FixtureObservationExtractor())
        gold.run_episode()
        extracted.run_episode()
        self.assertEqual(gold.notes, extracted.notes)
        self.assertEqual(gold.evaluator_truth, extracted.evaluator_truth)
        self.assertEqual(gold.snapshots, extracted.snapshots)
        self.assertEqual(digest_controller(gold), digest_controller(extracted))
        self.assertEqual([n.source_event_ids for n in gold.notes],
                         [n.source_event_ids for n in extracted.notes])

    def test_group_quality_changes_notes_without_putting_group_or_truth_in_notes(self):
        controller = make_controller(self.config, "FairPoint", "d_matched", 0)
        controller.note_quality_by_student = {sid: NoteQuality(omission_probability=1)
            for sid in controller.note_quality_by_student}
        controller.initialize()
        self.assertTrue(controller.notes)
        self.assertTrue(all(n.text == "There is insufficient evidence about participation."
                            for n in controller.notes))
        snapshot = controller.prepare_decision_snapshot(1)
        serialized = json.dumps(asdict(snapshot), sort_keys=True)
        sid = snapshot.students[0].student_id
        controller.environment._conditions[sid] = S.WITHDRAWN  # evaluator-only test mutation
        registry = tuple(r for r in controller.registry if r.event_month == 0)
        again = controller.environment.operational_snapshot(registry,
            estimates=snapshot.estimated_student_states, risks=snapshot.risk_estimates)
        self.assertEqual(serialized, json.dumps(asdict(again), sort_keys=True))
        self.assertNotIn("_conditions", serialized)

    def test_ambiguity_negation_partial_reporting_and_delay_are_note_channel_changes(self):
        event = ObservableEvent("event", "student", 0, 1, "assignment_difficulty")
        cases = (("ambiguity_probability", "insufficient evidence"),
                 ("negation_probability", "denies difficulty"),
                 ("partial_reporting_probability", "not yet consistent"))
        for parameter, phrase in cases:
            quality = NoteQuality(**{parameter: 1}, delay_probability=1)
            note = render_note(event, seed=0, quality=quality)
            self.assertIn(phrase, note.text)
            self.assertEqual(note.event_month, 0)
            self.assertEqual(note.available_from_month, 2)
            self.assertEqual(note.source_event_ids, (event.event_id,))
            batch = FixtureObservationExtractor().extract(note, 2)
            self.assertEqual(len(batch.facts), 1)
        self.assertEqual(event.signal, "assignment_difficulty")

    def test_fairpoint_and_robust_start_with_identical_authorized_information(self):
        inputs = []
        for policy in ("FairPoint", "FairRobust"):
            controller = make_controller(self.config, policy, "d_matched", 0)
            controller.initialize()
            inputs.append(controller.prepare_decision_snapshot(1))
        self.assertEqual(inputs[0], inputs[1])
        with self.assertRaises(ValueError):
            replace(inputs[0], month=2).validate_estimates()

    def test_protocol_manifest_freeze_is_idempotent_and_requires_explicit_amendment(self):
        with tempfile.TemporaryDirectory() as directory:
            # Test manifest mechanics against an explicit fixture. The removed
            # research protocol must not be restored or silently fabricated.
            from src.evaluation.research_experiments import PROTOCOL
            protocol = Mock(wraps=PROTOCOL)
            protocol.read_text.return_value = "Test-only protocol fixture; not a research authorization."
            protocol.read_bytes.return_value = protocol.read_text.return_value.encode()
            with patch("src.evaluation.research_experiments.PROTOCOL", protocol), patch(
                    "src.evaluation.research_experiments.fingerprint", return_value={
                    "docs/research_evaluation_protocol.md": "first"}):
                first = freeze(directory)
                self.assertEqual(freeze(directory), first)
                checked_manifest(directory)
            with patch("src.evaluation.research_experiments.PROTOCOL", protocol), patch(
                    "src.evaluation.research_experiments.fingerprint", return_value={
                    "docs/research_evaluation_protocol.md": "changed"}):
                with self.assertRaises(ValueError):
                    checked_manifest(directory)
                with self.assertRaises(ValueError):
                    freeze(directory)
                second = freeze(directory, "Development correction before heldout evaluation")
            self.assertNotEqual(second["input_digest"], first["input_digest"])
            self.assertEqual(json.loads((Path(directory)/"configuration_manifest.json").read_text()), second)
            self.assertEqual(len(list(Path(directory).glob("configuration_manifest*.json"))), 1)
            with self.assertRaises(ValueError):
                require_pilot(directory, second)

    def test_changed_input_episodes_and_completion_marker_cannot_enter_active_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for digest in ("previous", "current"):
                destination = root / "episodes" / digest
                destination.mkdir(parents=True)
                (destination / "summary.json").write_text(json.dumps({
                    "phase": "development", "policy": "FairPoint", "mode": "d_matched",
                    "seed": 0, "setting": "primary", "input_digest": digest,
                    "trace_path": f"episodes/{digest}/trace.json.gz"}))
            with patch("src.evaluation.research_experiments.checked_manifest", return_value={"input_digest": "current"}):
                rows = aggregate(root)
            self.assertEqual([row["input_digest"] for row in rows], ["current"])
            (root / "primary_complete.json").write_text(json.dumps({"input_digest": "previous"}))
            with patch("src.evaluation.research_experiments.require_pilot"):
                with self.assertRaisesRegex(ValueError, "primary comparison"):
                    secondary(root, self.config, {"input_digest": "current"})


if __name__ == "__main__":
    unittest.main()

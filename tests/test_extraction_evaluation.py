"""Behavioral tests for frozen evaluation, scoring and genuine-output caching."""

from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.evaluation.cached_observation_extractor import CachedObservationExtractor
from src.evaluation.extraction_evaluation import (
    GOLD_SENTENCES, _note, build_benchmark, evaluate_records, freeze_benchmark, run_comparator,
)
from src.intervention.observation_extractor import gold_payload


class ExtractionEvaluationTests(unittest.TestCase):
    def test_independent_gold_provenance_and_temporal_holdouts(self):
        cases = build_benchmark()
        self.assertEqual(len(cases), 28)
        self.assertEqual(sum(c["eligible"] for c in cases), 24)
        self.assertEqual(len({c["note"]["student_id"] for c in cases}), 28)
        for case in cases:
            if not case["eligible"]:
                self.assertIsNone(case["gold"])
                continue
            note = case["note"]
            for fact in case["gold"]["observations"]:
                self.assertEqual(note["text"][fact["start_offset"]:fact["end_offset"]], fact["evidence"])
                self.assertEqual(fact["source_month"], note["event_month"])
                self.assertEqual(len(note["source_event_ids"]), 1)
        with patch("src.evaluation.extraction_evaluation.gold_payload", side_effect=AssertionError("not gold")):
            self.assertEqual(build_benchmark(), cases)

    def test_freeze_refuses_changed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = freeze_benchmark(directory)
            self.assertEqual(freeze_benchmark(directory), manifest)
            path = Path(directory) / "gold_manifest.json"
            changed = deepcopy(manifest)
            changed["cases"][0]["gold"]["observations"][0]["value"] = "low"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "Frozen"):
                freeze_benchmark(directory)

    def test_baseline_ceiling_and_missing_model_are_not_conflated(self):
        cases = build_benchmark()
        for method in ("exact_rule", "gold_reference"):
            metrics = evaluate_records(cases, run_comparator(cases, method))
            self.assertEqual(metrics["micro"]["f1"], 1)
            self.assertEqual(metrics["diagnostics"]["temporal_correct_rejections"], 4)
            self.assertEqual(metrics["diagnostics"]["unsupported_only_correct_abstentions"], 3)
            self.assertEqual(metrics["diagnostics"]["raw_unsupported_observations"], 0)
        failed = evaluate_records(cases, [])
        self.assertEqual(failed["micro"]["recall"], 0)
        self.assertEqual(failed["failure_rate_all_eligible"], 1)
        self.assertIsNone(failed["micro"]["precision"])

    def test_raw_errors_are_visible_even_when_validator_discards_all_facts(self):
        cases = build_benchmark()[:1]
        raw = deepcopy(cases[0]["gold"])
        raw["observations"][0].update(source_month=999, start_offset=999, trend="improved")
        metrics = evaluate_records(cases, [{"case_id": cases[0]["case_id"], "status": "quarantined", "raw_output": raw}])
        self.assertEqual(metrics["micro"]["fn"], 1)
        self.assertEqual(metrics["diagnostics"]["raw_unsupported_observations"], 1)
        self.assertEqual(metrics["diagnostics"]["raw_evidence_span_errors"], 1)
        self.assertEqual(metrics["diagnostics"]["raw_timestamp_errors"], 1)

    def test_persistent_cache_invalidates_context_and_revalidates(self):
        metadata = {"models": [{"name": "qwen3.5:latest", "digest": "test-digest"}]}
        note = _note(build_benchmark()[0])
        with tempfile.TemporaryDirectory() as directory, patch(
            "src.evaluation.cached_observation_extractor.urlopen",
            side_effect=lambda *a, **k: io.BytesIO(json.dumps(metadata).encode()),
        ), patch("src.evaluation.cached_observation_extractor.OllamaClient.generate", side_effect=lambda messages, schema: gold_payload(
            replace(note, **{k: v for k, v in json.loads(messages[1]["content"])["note"].items() if k != "source_event_ids"})
        )) as generate:
            extractor = CachedObservationExtractor(directory)
            extractor.extract(note, 3)
            extractor.extract(note, 3)
            self.assertEqual(generate.call_count, 1)
            extractor.extract(note, 4)
            self.assertEqual(generate.call_count, 2)
            extractor.extract(replace(note, text=note.text + " Additional unknown observation."), 3)
            self.assertEqual(generate.call_count, 3)
            altered = CachedObservationExtractor(directory, num_ctx=4096)
            altered.extract(note, 3)
            self.assertEqual(generate.call_count, 4)
            self.assertTrue(extractor.audit_records[1]["cache_hit"])
            with self.assertRaisesRegex(ValueError, "cutoff"):
                extractor.extract(note, 2)
            self.assertEqual(generate.call_count, 4)


if __name__ == "__main__":
    unittest.main()

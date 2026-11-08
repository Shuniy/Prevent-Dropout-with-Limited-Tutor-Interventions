"""Actionable extraction and common-history comparisons; all inference is offline."""
from dataclasses import asdict, replace
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.evaluation.research_experiments import load_config, live_snapshot_comparisons, make_controller, live
from src.intervention.feedback_notes import NoteQuality
from src.intervention.observation_extractor import FixtureObservationExtractor, validate_extraction
from src.school.closed_loop_controller import ClosedLoopCMDPController
from src.school.cmdp_scenarios import build_school
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.constraints import validate_allocation
from src.school.feedback_validation import FixedMonitoringRecords
from src.school.feedback_validation import validate_feedback_episode
from src.school.feedback_experiments import save_episode
from src.school.feedback_replay import replay_feedback_episode
from src.school.observation_model import ObservationConfig
from src.school.scenario_config import ScenarioConfig
from src.school.student_condition import StudentCondition
from tests.test_feedback_closed_loop import counted_extractor


class CountingExtractor:
    def __init__(self, *, omit=False, fail=False):
        self.received = []
        self.omit, self.fail = omit, fail

    def extract(self, note, cutoff):
        self.received.append((note, cutoff))
        if self.fail:
            raise RuntimeError("fixture unavailable")
        batch = FixtureObservationExtractor().extract(note, cutoff)
        if self.omit and note.event_month == 1 and "low participation" in note.text:
            return replace(batch, facts=())
        return batch


class MonitoringFixture(FixedMonitoringRecords):
    def generate(self, conditions, **kwargs):
        events, registry = super().generate(conditions, **kwargs)
        # Two still-eligible candidates: moderate difficulty versus low
        # participation. Omission reverses a STRICT benefit ordering; neither
        # month-2 allocation depends on a tie or a binding fairness requirement.
        if kwargs["month"] == 1:
            events = (replace(events[1], signal="assignment_difficulty"), events[2])
        return events, registry


def controlled_episode(*, omit=False, run=True):
    config = ScenarioConfig(num_students=3, num_mentors=1, horizon=3,
        monthly_admissions=1, monthly_appointments=5, budget=10, seed=42,
        fairness_min_access=0)
    controller = ClosedLoopCMDPController(build_school(config).create_cmdp_environment(config=config),
        ConstrainedAllocationPlanner(), mode="llm_notes", extractor=CountingExtractor(omit=omit),
        max_monitoring_notes_per_month=3)
    controller.observation_model = MonitoringFixture(True)
    return controller.run_episode() if run else controller


def standard_controller(mode="llm_notes", *, limit=2, budget=10, extractor=None, quality=NoteQuality()):
    config = ScenarioConfig(num_students=6, num_mentors=1, horizon=3,
        monthly_admissions=1, monthly_appointments=5, budget=budget, seed=42,
        fairness_min_access=0)
    return ClosedLoopCMDPController(build_school(config).create_cmdp_environment(config=config),
        ConstrainedAllocationPlanner(), mode=mode, extractor=extractor or CountingExtractor(),
        max_monitoring_notes_per_month=limit, max_notes_per_month=1, note_quality=quality,
        observation_config=ObservationConfig(missing_probability=0, delay_probability=0))


class Phase2Reproductions(unittest.TestCase):
    def test_changed_extraction_alone_changes_month_two_feasible_action(self):
        gold, omitted = controlled_episode(), controlled_episode(omit=True)
        self.assertEqual(gold.snapshots[0], omitted.snapshots[0])
        self.assertEqual(gold.decisions[0]["admitted_ids"], omitted.decisions[0]["admitted_ids"])
        self.assertEqual(gold.environment.records[0].conditions, omitted.environment.records[0].conditions)
        self.assertEqual([n for n in gold.notes if n.event_month <= 1],
                         [n for n in omitted.notes if n.event_month <= 1])
        self.assertNotEqual(gold.decisions[1]["admitted_ids"], omitted.decisions[1]["admitted_ids"])
        target = sorted(gold.estimates)[2]
        self.assertNotEqual(gold.snapshots[1].students[2].condition_probabilities,
                            omitted.snapshots[1].students[2].condition_probabilities)
        self.assertNotEqual(gold.decisions[1]["benefits"][target], omitted.decisions[1]["benefits"][target])
        self.assertNotEqual(gold.snapshots[1].risk_estimates[2].probability,
                            omitted.snapshots[1].risk_estimates[2].probability)
        for c in (gold, omitted):
            self.assertGreaterEqual(sum(s.eligible for s in c.snapshots[1].students), 2)
            chosen = c.decisions[1]["admitted_ids"][0]
            benefits = c.decisions[1]["benefits"]
            self.assertGreater(benefits[chosen], max(v for sid, v in benefits.items() if sid != chosen))
            for snapshot, record in zip(c.snapshots, c.environment.records):
                snapshot.validate_estimates()
                validate_allocation(snapshot, record.allocation.assignments)

    def test_injected_monitoring_extraction_precedes_any_admission(self):
        controller = controlled_episode(run=False)
        controller.initialize()
        controller.prepare_decision_snapshot(1)
        self.assertEqual(len(controller.extractor.received), 3)
        self.assertTrue(all(n.note_type == "monitoring" for n, _ in controller.extractor.received))
        self.assertFalse(controller.environment.records)

    def test_live_snapshot_comparison_exercises_failing_extractor(self):
        config = load_config()
        config["scenario"].update(num_students=3, num_mentors=1, horizon=3,
            monthly_admissions=1, monthly_appointments=5, budget=10, fairness_min_access=0)
        config["evaluation"]["live_seeds"] = [42]
        extractor = CountingExtractor(fail=True)
        with tempfile.TemporaryDirectory() as directory:
            live_snapshot_comparisons(directory, config, extractor)
            self.assertGreater(len(extractor.received), 0)
            diagnostics = json.loads((Path(directory) / "live_snapshot_rank_42_b_matched.json").read_text())
            self.assertGreater(diagnostics["extractor_attempts"], 0)
            self.assertEqual(diagnostics["status"], "UNAVAILABLE / UNUSABLE")
            self.assertIsNone(diagnostics["spearman_average_ties"])


class Phase2Contracts(unittest.TestCase):
    def test_live_runtime_counts_include_snapshot_invocations(self):
        class RuntimeFixture:
            calls = 0
            configuration = {"origin": "offline_test"}

        extractor = RuntimeFixture()

        def increment(count):
            extractor.calls += count

        config = load_config()
        config["evaluation"]["live_seeds"] = [42]
        with tempfile.TemporaryDirectory() as directory, patch(
                "src.evaluation.research_experiments.require_pilot"), patch(
                "src.evaluation.extraction_evaluation.make_cached_extractor", return_value=extractor), patch(
                "src.evaluation.research_experiments.run_pairs", side_effect=lambda *a, **k: increment(2)), patch(
                "src.evaluation.research_experiments.live_snapshot_comparisons", side_effect=lambda *a: increment(3)):
            live(directory, config, {})
            runtime = json.loads((Path(directory) / "live_runtime.json").read_text())
        self.assertEqual(runtime["closed_loop_inference_calls"], 8)
        self.assertEqual(runtime["snapshot_inference_calls"], 3)
        self.assertEqual(runtime["new_inference_calls"], 11)

    def test_bounded_injection_without_programmes_and_explicit_no_fallback(self):
        for mode in ("llm_notes", "noisy_notes"):
            c = standard_controller(mode, budget=0).run_episode()
            self.assertEqual(len(c.extractor.received), 6)  # two per decision, no terminal monitoring
            self.assertFalse(any(d["admitted_ids"] for d in c.decisions))
            self.assertTrue(all(n.note_type == "monitoring" for n, _ in c.extractor.received))
            self.assertTrue(any(s["reason"] == "monitoring_cutoff_cap" for s in c.note_selection))
            self.assertTrue(any(s["reason"] == "no_remaining_decision" for s in c.note_selection))
            self.assertEqual(sum(bool(e.evidence_ids) for e in c.snapshots[0].estimated_student_states), 2)
            self.assertEqual(len(c.batches), 6)
            self.assertEqual(c.extraction_diagnostics()["actual_model_invocations"], 0)
        full = standard_controller("structured", limit=0).run_episode()
        self.assertEqual(len(full.batches), 24)
        self.assertTrue(all(e.evidence_ids for e in full.snapshots[0].estimated_student_states))

    def test_perfect_extraction_matches_clean_and_noisy_gold(self):
        for mode, quality in (("llm_notes", NoteQuality()), ("noisy_notes", NoteQuality(
                omission_probability=.2, conflict_probability=.3, delay_probability=.25))):
            gold = standard_controller("b_matched", quality=quality).run_episode()
            extracted = standard_controller(mode, quality=quality).run_episode()
            self.assertEqual(gold.notes, extracted.notes)
            self.assertEqual(gold.note_selection, extracted.note_selection)
            self.assertEqual(gold.snapshots, extracted.snapshots)
            self.assertEqual(gold.risks, extracted.risks)
            self.assertEqual([d["admitted_ids"] for d in gold.decisions],
                             [d["admitted_ids"] for d in extracted.decisions])
            self.assertTrue(extracted.extractor.received)
            self.assertTrue(validate_feedback_episode(extracted))

    def test_invalid_unsupported_forged_and_exception_outputs_are_quarantined(self):
        class BadExtractor:
            def __init__(self, behavior):
                self.behavior = behavior

            def extract(self, note, cutoff):
                batch = FixtureObservationExtractor().extract(note, cutoff)
                if self.behavior == "schema":
                    return {"observations": "not a batch"}
                if self.behavior == "json":
                    return validate_extraction("{broken", note, cutoff)
                if self.behavior == "unsupported":
                    return replace(batch, facts=(replace(batch.facts[0], trend="improved"),))
                if self.behavior == "forged":
                    return replace(batch, facts=(replace(batch.facts[0], evidence_id="forged"),))
                raise LookupError("fixture exception")

        for behavior in ("schema", "json", "unsupported", "forged", "exception"):
            with self.subTest(behavior=behavior):
                c = controlled_episode(run=False)
                c.run_month()
                before = c.snapshots[0]
                c.extractor = BadExtractor(behavior)
                c.run_month()
                self.assertEqual(len(c.failures), 2)
                self.assertEqual(c.failures[0]["status"], "quarantined")
                self.assertEqual(c.snapshots[0], before)
                estimate = c.snapshots[1].estimated_student_states[2]
                reference = controlled_episode(omit=True).snapshots[1].estimated_student_states[2]
                self.assertEqual(estimate, reference)
                self.assertEqual(estimate.last_observation_month, 0)
                self.assertTrue(dict(estimate.observation_uncertainty)["missing_current_signal"])
                self.assertEqual(c.snapshots[1].risk_estimates[2].input_estimate_id, estimate.estimate_id)

    def test_empty_unknown_and_conflict_are_distinct_and_do_not_refresh(self):
        values = (("empty", "No supported observations are available."),
                  ("unknown", "There is insufficient evidence about participation."),
                  ("conflicting", "The school reports low participation in recent activities. "
                   "The school reports regular participation in recent activities. "
                   "Reports about participation conflict and remain unresolved."))
        for expected, text in values:
            c = controlled_episode(run=False)
            c.run_month()
            c.notes = [replace(n, text=text) if n.event_month == 1 else n for n in c.notes]
            c.run_month()
            self.assertEqual(c.extraction_attempts[-1]["result"], expected)
            self.assertFalse(c.failures)
            e = c.snapshots[1].estimated_student_states[2]
            self.assertEqual(e.last_observation_month, 0)
            self.assertTrue(dict(e.observation_uncertainty)["missing_current_signal"])
            self.assertEqual(e.condition_probabilities,
                             controlled_episode(omit=True).snapshots[1].students[2].condition_probabilities)

    def test_delayed_note_uses_source_time_and_never_rewrites_original_action(self):
        c = standard_controller(limit=6, budget=0)
        c.initialize()
        delayed = [replace(n, available_from_month=2) for n in c.notes]
        c.notes = list(delayed)
        c.run_month()
        historical = asdict(c.snapshots[0])
        self.assertFalse(c.extractor.received)
        self.assertTrue(all(not e.evidence_ids for e in c.snapshots[0].estimated_student_states))
        c.notes = delayed  # fixture: no new reports, only the original delayed ones
        state = c.prepare_decision_snapshot(2)
        self.assertEqual(len(c.extractor.received), 6)
        self.assertTrue(all(n.event_month == 0 and cutoff == 2 for n, cutoff in c.extractor.received))
        self.assertTrue(all(e.last_observation_month == 0 for e in state.estimated_student_states))
        self.assertTrue(all(dict(e.observation_uncertainty)["missing_current_signal"]
                            for e in state.estimated_student_states))
        self.assertEqual(asdict(c.snapshots[0]), historical)
        c.prepare_decision_snapshot(2)
        self.assertEqual(len(c.extractor.received), 6)
        self.assertTrue(any(s["reason"] == "not_yet_available" for s in c.note_selection))

    def test_hidden_truth_cannot_change_selection_or_ordinary_input(self):
        left = standard_controller()
        left.initialize()
        right = deepcopy(left)
        for sid in right.environment._conditions:
            right.environment._conditions[sid] = StudentCondition.WITHDRAWN
        self.assertEqual(left.prepare_decision_snapshot(1), right.prepare_decision_snapshot(1))
        self.assertEqual(left.note_selection, right.note_selection)
        self.assertEqual(left.extractor.received, right.extractor.received)

    def test_future_snapshot_is_rejected_before_extraction_or_mutation(self):
        c = standard_controller()
        c.initialize()
        with self.assertRaisesRegex(ValueError, "cutoff mismatch"):
            c.prepare_decision_snapshot(2)
        self.assertFalse(c.extractor.received)
        self.assertFalse(c.estimates)
        self.assertFalse(c.processed)

    def test_all_modes_preserve_atomic_resource_invariants(self):
        for mode in ("oracle", "structured", "b_matched", "llm_notes", "noisy_notes"):
            c = standard_controller(mode).run_episode()
            self.assertTrue(validate_feedback_episode(c))
            admissions = [a.student_id for record in c.environment.records for a in record.allocation.assignments]
            self.assertEqual(len(admissions), len(set(admissions)))
            self.assertLessEqual(len(admissions), 2)  # two whole five-appointment programmes
            self.assertTrue(all(r.remaining_budget >= 0 for r in c.environment.records))
            for state, record in zip(c.snapshots, c.environment.records):
                validate_allocation(state, record.allocation.assignments)
                self.assertTrue(all(next(s for s in state.students if s.student_id == a.student_id).eligible
                                    for a in record.allocation.assignments))

    def test_duplicates_cached_extraction_and_repeated_runs(self):
        class DuplicatingExtractor:
            def extract(self, note, cutoff):
                batch = FixtureObservationExtractor().extract(note, cutoff)
                return replace(batch, facts=batch.facts * 2)

        left, right = standard_controller().run_episode(), standard_controller().run_episode()
        duplicate = standard_controller(extractor=DuplicatingExtractor()).run_episode()
        for name in ("notes", "batches", "snapshots", "risks", "extraction_attempts", "note_selection",
                     "decision_diagnostics"):
            self.assertEqual(getattr(left, name), getattr(right, name))
        self.assertEqual(left.snapshots, duplicate.snapshots)
        self.assertEqual([d["admitted_ids"] for d in left.decisions], [d["admitted_ids"] for d in right.decisions])
        self.assertEqual([r.remaining_budget for r in left.environment.records],
                         [r.remaining_budget for r in right.environment.records])
        extractor = counted_extractor()
        original = standard_controller(extractor=extractor).run_episode()
        cached = standard_controller(extractor=extractor).run_episode()
        self.assertEqual(original.snapshots, cached.snapshots)
        self.assertGreater(original.extraction_diagnostics()["actual_model_invocations"], 0)
        diagnostics = cached.extraction_diagnostics()
        self.assertEqual(diagnostics["actual_model_invocations"], 0)
        self.assertEqual(diagnostics["cache_hits"], diagnostics["extractor_attempts"])
        count = len(cached.batches)
        cached.process_new_observations(4)
        self.assertEqual(len(cached.batches), count)

    def test_saved_actionable_noisy_episode_replays_without_model(self):
        c = standard_controller("noisy_notes", extractor=counted_extractor())
        # A per-student channel must survive manifest round-trip too.
        sid = "SYN00001"
        c.note_quality_by_student[sid] = NoteQuality(omission_probability=1)
        c.run_episode()
        with tempfile.TemporaryDirectory() as directory:
            source, replay = Path(directory) / "source", Path(directory) / "replay"
            save_episode(c, source)
            result = replay_feedback_episode(source, replay)
            self.assertTrue(result["snapshots_allocations_resources_and_truth_match"])
            self.assertEqual(result["real_llm_calls"], 0)
            self.assertEqual((source / "note_selection.jsonl").read_text(),
                             (replay / "note_selection.jsonl").read_text())

    def test_nonvacuous_matched_snapshot_equality_omission_and_zero_attempts(self):
        config = load_config()
        config["scenario"].update(num_students=3, num_mentors=1, horizon=3,
            monthly_admissions=1, monthly_appointments=5, budget=10, fairness_min_access=0)
        config["evaluation"].update(live_seeds=[42], monitoring_notes_per_month=3)
        config["notes"] = {}
        config["primary_notes_true"] = {}
        config["primary_notes_false"] = {}

        def factory(*args, **kwargs):
            c = make_controller(*args, **kwargs)
            c.observation_model = MonitoringFixture(True)
            return c

        with tempfile.TemporaryDirectory() as directory, patch(
                "src.evaluation.research_experiments.make_controller", side_effect=factory):
            perfect = live_snapshot_comparisons(directory, config, CountingExtractor())
            self.assertTrue(all(r["status"] == "EXERCISED" and r["extractor_attempts"] > 0 for r in perfect))
            self.assertTrue(all(r["belief_l1"] == 0 and not r["mentor_changed"] for r in perfect))
            omission = live_snapshot_comparisons(directory, config, CountingExtractor(omit=True))
            self.assertTrue(any(r["belief_l1"] > 0 and r["risk_difference"] != 0 for r in omission))
            self.assertTrue(any(r["mentor_changed"] for r in omission))
            config["evaluation"]["monitoring_notes_per_month"] = 0
            empty = live_snapshot_comparisons(directory, config, CountingExtractor())
            self.assertTrue(all(r["status"] == "UNAVAILABLE / NOT EXERCISED" for r in empty))
            self.assertTrue(all(r["belief_l1"] is None and r["mentor_changed"] is None for r in empty))


if __name__ == "__main__":
    unittest.main()

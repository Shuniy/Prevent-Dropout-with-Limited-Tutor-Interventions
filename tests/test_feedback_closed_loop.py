"""Sequential allocation, independent feasibility checks and forbidden-access tests."""

from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.intervention.feedback_notes import NoteQuality
from src.intervention.observation_extractor import (
    FixtureObservationExtractor, LLMObservationExtractor, gold_payload,
)
from src.school.closed_loop_controller import ClosedLoopCMDPController
from src.school.cmdp_scenarios import build_school
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.constraints import validate_allocation
from src.school.fairness_planner import FairnessPlanner
from src.school.feedback_experiments import save_episode
from src.school.feedback_validation import FixedMonitoringRecords
from src.school.feedback_replay import replay_feedback_episode
from src.observations.observable_events import ObservableEvent, EnrollmentRecord, Note
from src.school.observation_model import ObservationConfig, SyntheticObservationModel
from src.school.scenario_config import ScenarioConfig
from src.school.student_condition import StudentCondition as S


def setup(mode="llm_notes", *, policy=None, config=None, **kwargs):
    config = config or ScenarioConfig(num_students=6, num_mentors=1, horizon=3,
                                      monthly_admissions=1, monthly_appointments=5, budget=10)
    school = build_school(config)
    controller = ClosedLoopCMDPController(school.create_cmdp_environment(config=config),
        policy or ConstrainedAllocationPlanner(), mode=mode,
        extractor=FixtureObservationExtractor(), **kwargs)
    return controller, school


def feedback_demonstration(new_evidence):
    config = ScenarioConfig(num_students=3, num_mentors=1, horizon=3,
                            monthly_admissions=1, monthly_appointments=5, budget=15, seed=42)
    controller, _ = setup(config=config)
    controller.observation_model = FixedMonitoringRecords(new_evidence)
    return controller.run_episode()


def counted_extractor():
    def generate(messages, schema):
        return gold_payload(Note(**json.loads(messages[1]["content"])["note"]))

    return LLMObservationExtractor(Mock(model="test", generate=Mock(side_effect=generate)))


class ClosedLoopFeedbackTests(unittest.TestCase):
    def test_llm_calls_only_for_admitted_programmes_and_not_monthly_monitoring(self):
        for mode in ("llm_notes", "noisy_notes"):
            with self.subTest(mode=mode):
                controller, _ = setup(mode=mode, observation_config=ObservationConfig(
                    missing_probability=0, delay_probability=0))
                controller.extractor = counted_extractor()
                controller.initialize()
                controller.prepare_decision_snapshot(1)
                self.assertEqual(controller.extractor.client.generate.call_count, 0)
                controller.run_episode()
                admitted = {(d["month"], sid) for d in controller.decisions for sid in d["admitted_ids"]}
                self.assertEqual(len(admitted), 2)
                self.assertEqual(controller.extractor.calls, len(admitted))
                sent = [json.loads(call.args[0][1]["content"])["note"]
                        for call in controller.extractor.client.generate.call_args_list]
                self.assertEqual({(n["event_month"], n["student_id"]) for n in sent}, admitted)
                self.assertTrue(all(n["note_type"] == "programme" and n["mentor_id"] for n in sent))
                self.assertEqual(len(controller.extraction_attempts), len(admitted))
                self.assertEqual(len(controller.estimates), 6)
                self.assertEqual(len(controller.batches), 6 * 4)
                controller.process_new_observations(4)
                self.assertEqual(controller.extractor.calls, len(admitted))

    def test_no_llm_calls_without_interventions(self):
        config = ScenarioConfig(num_students=6, num_mentors=1, horizon=2,
                                monthly_admissions=1, monthly_appointments=5, budget=10)
        for overrides in ({"budget": 0}, {"num_mentors": 0}, {"monthly_admissions": 0}):
            with self.subTest(overrides=overrides):
                controller, _ = setup(config=replace(config, **overrides))
                controller.extractor = counted_extractor()
                controller.run_episode()
                self.assertEqual(controller.extractor.client.generate.call_count, 0)
                self.assertFalse(controller.failures)
                self.assertTrue(controller.batches)
                self.assertEqual(len(controller.estimates), config.num_students)

    def test_note_limit_applies_to_programmes_and_preserves_routine_monitoring(self):
        config = ScenarioConfig(num_students=6, num_mentors=1, horizon=2,
                                monthly_admissions=2, monthly_appointments=10, budget=20)
        for limit in (0, 1):
            with self.subTest(limit=limit):
                controller, _ = setup(config=config, max_notes_per_month=limit,
                    observation_config=ObservationConfig(missing_probability=0, delay_probability=0))
                controller.extractor = counted_extractor()
                controller.run_episode()
                admissions = sum(len(d["admitted_ids"]) for d in controller.decisions)
                self.assertEqual(admissions, 4)
                self.assertEqual(controller.extractor.calls, limit * config.horizon)
                monitoring = [n for n in controller.notes if n.note_type == "monitoring"]
                self.assertEqual(len(monitoring), config.num_students * (config.horizon + 1) - admissions)
                matched, _ = setup(mode="b_matched", config=config, max_notes_per_month=limit,
                    observation_config=controller.observation_model.config)
                matched.run_episode()
                self.assertEqual(matched.notes, controller.notes)
                self.assertEqual(matched.snapshots, controller.snapshots)

    def test_delayed_programme_note_is_called_once_only_after_availability(self):
        controller, _ = setup(observation_config=ObservationConfig(
            missing_probability=0, delay_probability=1),
            note_quality=NoteQuality(delay_probability=1))
        controller.extractor = counted_extractor()
        controller.run_episode()
        # Month 1's intervention becomes available at terminal cutoff 4;
        # month 2's is still unavailable until cutoff 5.
        self.assertEqual(controller.extractor.calls, 1)
        call = controller.extractor.client.generate.call_args
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(context["note"]["event_month"], 1)
        self.assertEqual(context["as_of_month"], 4)
        controller.process_new_observations(4)
        self.assertEqual(controller.extractor.calls, 1)
        controller.process_new_observations(5)
        self.assertEqual(controller.extractor.calls, 2)

    def test_new_monitoring_note_changes_untreated_students_next_allocation(self):
        updated, unchanged = feedback_demonstration(True), feedback_demonstration(False)
        first, second, third = sorted(updated.estimates)
        self.assertEqual(updated.decisions[0]["admitted_ids"], (first,))
        self.assertEqual(updated.decisions[0]["admitted_ids"], unchanged.decisions[0]["admitted_ids"])
        self.assertEqual(updated.evaluator_truth[1], unchanged.evaluator_truth[1])
        self.assertEqual(unchanged.decisions[1]["admitted_ids"], (second,))
        self.assertEqual(updated.decisions[1]["admitted_ids"], (third,))
        self.assertFalse(updated.snapshots[1].students[2].programme_months)
        self.assertGreater(updated.decisions[1]["benefits"][third], updated.decisions[1]["benefits"][second])
        self.assertTrue(any(note.student_id == third and note.note_type == "monitoring"
                            and note.event_month == 1 for note in updated.notes))
        prior = next(r for r in updated.risks if r.student_id == third and r.as_of_month == 1)
        next_risk = next(r for r in updated.risks if r.student_id == third and r.as_of_month == 2)
        self.assertNotEqual(prior.input_estimate_id, next_risk.input_estimate_id)
        self.assertNotEqual(prior.probability, next_risk.probability)

    def test_episode_preserves_source_records_constraints_and_one_programme(self):
        controller, school = setup()
        students, mentors = [asdict(s) for s in school.students], [asdict(m) for m in school.mentors]
        controller.run_episode()
        self.assertEqual(len(controller.snapshots), 3)
        self.assertEqual(controller.snapshots[-1].month, 3)
        self.assertEqual(max(r.as_of_month for r in controller.risks), 4)
        self.assertEqual([asdict(s) for s in school.students], students)
        self.assertEqual([asdict(m) for m in school.mentors], mentors)
        admitted = [sid for d in controller.decisions for sid in d["admitted_ids"]]
        self.assertEqual(len(admitted), len(set(admitted)))
        for state, record in zip(controller.snapshots, controller.environment.records):
            validate_allocation(state, record.allocation.assignments)
            self.assertGreaterEqual(record.remaining_budget, 0)
            state.validate_estimates()
            self.assertEqual(state.observation_mode, "estimated_state")
            self.assertFalse(hasattr(state, "_conditions"))
        self.assertTrue(any(n.programme_id is not None for n in controller.notes))

    def test_hidden_state_changes_with_fixed_authorized_records_do_not_change_decision_input(self):
        controller, _ = setup()
        controller.initialize()
        state = controller.prepare_decision_snapshot(1)
        serialized = json.dumps(asdict(state), sort_keys=True)
        sid = state.students[0].student_id
        # Deliberate evaluator-only mutation to attempt a forbidden access.
        controller.environment._conditions[sid] = S.WITHDRAWN
        registry = tuple(r for r in controller.registry if r.event_month == 0)
        again = controller.environment.operational_snapshot(registry,
            estimates=state.estimated_student_states, risks=state.risk_estimates)
        self.assertEqual(serialized, json.dumps(asdict(again), sort_keys=True))

    def test_changing_notes_does_not_change_current_transition_with_fixed_action(self):
        left, _ = setup()
        right, _ = setup()
        left.initialize()
        right.initialize()
        left_state = left.prepare_decision_snapshot(1)
        right.notes = [replace(n, text="There is insufficient evidence about participation.") for n in right.notes]
        right_state = right.prepare_decision_snapshot(1)
        self.assertNotEqual(left_state.students[0].condition_probabilities,
                            right_state.students[0].condition_probabilities)
        allocation = left.allocate(left_state)
        left_record, right_record = left.environment.step(allocation), right.environment.step(allocation)
        self.assertEqual(left_record.conditions, right_record.conditions)

    def test_fairness_freezes_observed_uncertain_denominators(self):
        controller, _ = setup(mode="structured", policy=FairnessPlanner(minimum_access=.5),
            observation_config=ObservationConfig(missing_probability=1))
        controller.run_episode()
        window = controller.policy.windows[0]
        cohorts = window.cohorts
        self.assertEqual(sum(len(c.student_ids) for c in cohorts), 6)
        self.assertTrue(any(c.condition_at_start == "uncertain" and c.student_ids for c in cohorts))
        for c in cohorts:
            self.assertTrue(set(c.student_ids) <= set(controller.estimates))
        for snapshot, record in zip(controller.snapshots, controller.environment.records):
            validate_allocation(snapshot, record.allocation.assignments)
        self.assertEqual(len(window.recipients), 2)

    def test_stale_risk_or_estimate_is_rejected_by_both_planners(self):
        controller, _ = setup()
        controller.initialize()
        state = controller.prepare_decision_snapshot(1)
        stale = replace(state.risk_estimates[0], input_estimate_id="stale")
        bad = replace(state, risk_estimates=(stale, *state.risk_estimates[1:]))
        for planner in (ConstrainedAllocationPlanner(), FairnessPlanner()):
            with self.assertRaisesRegex(ValueError, "stale"):
                planner.plan(bad)

    def test_structured_and_matched_modes_share_estimator_and_solver_when_content_matches(self):
        config = ObservationConfig(missing_probability=0, delay_probability=0)
        structured, _ = setup(mode="structured", observation_config=config)
        matched, _ = setup(mode="b_matched", observation_config=config)
        extracted, _ = setup(mode="llm_notes", observation_config=config)
        for controller in (structured, matched, extracted):
            controller.run_episode()
        self.assertEqual(structured.snapshots, matched.snapshots)
        self.assertEqual(matched.snapshots, extracted.snapshots)
        self.assertEqual([d["admitted_ids"] for d in structured.decisions],
                         [d["admitted_ids"] for d in extracted.decisions])

    def test_persisted_controller_traces_exclude_evaluator_truth_and_do_not_overwrite(self):
        controller, _ = setup()
        controller.run_episode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode"
            save_episode(controller, path)
            self.assertTrue((path / "evaluator_only/truth_trajectories.jsonl").exists())
            for filename in ("decision_snapshots", "mentor_notes", "extracted_observations"):
                for record in (path / f"{filename}.jsonl").read_text().splitlines():
                    self.assertNotIn('"conditions"', record)
                    self.assertNotIn('"true_condition"', record)
            self.assertEqual(len((path / "decision_snapshots.jsonl").read_text().splitlines()), 3)
            with self.assertRaises(FileExistsError):
                save_episode(controller, path)

    def test_unavailable_extractor_keeps_prediction_and_records_failures(self):
        controller, _ = setup(observation_config=ObservationConfig(
            missing_probability=0, delay_probability=0))
        controller.extractor = counted_extractor()
        controller.extractor.client.generate.side_effect = RuntimeError("Ollama unavailable")
        controller.run_episode()
        self.assertEqual(len(controller.failures), 2)
        programme_ids = {n.note_id for n in controller.notes if n.note_type == "programme"}
        self.assertEqual({f["note_id"] for f in controller.failures}, programme_ids)
        self.assertTrue(controller.batches)
        self.assertFalse(any(b.note_id in programme_ids for b in controller.batches))
        self.assertEqual(len(controller.extraction_attempts), 2)
        controller.process_new_observations(4)
        self.assertEqual(controller.extractor.calls, 2)
        self.assertEqual(len(controller.environment.records), 3)

    def test_saved_extractions_replay_exact_decisions_without_llm(self):
        controller, _ = setup()
        controller.extractor = counted_extractor()
        controller.run_episode()
        with tempfile.TemporaryDirectory() as directory:
            source, replay = Path(directory) / "original", Path(directory) / "replay"
            save_episode(controller, source)
            result = replay_feedback_episode(source, replay)
            self.assertEqual(result["real_llm_calls"], 0)
            self.assertTrue(result["snapshots_allocations_resources_and_truth_match"])


if __name__ == "__main__":
    unittest.main()

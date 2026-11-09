"""Offline regressions for experimental contracts, not treatment efficacy."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.school.baseline_policy import BASELINES, BaselinePolicy
from src.school.closed_loop_controller import ClosedLoopCMDPController
from src.school.cmdp_scenarios import build_environment
from src.school.feedback_validation import validate_feedback_episode
from src.school.scenario_config import ScenarioConfig
from src.intervention.observation_extractor import FixtureObservationExtractor
from src.evaluation.research_experiments import load_config, make_policy as research_policy
from src.school.cmdp_experiments import run_experiments
from src.school.fairness_planner import FairnessPlanner
from src.school.robust_fair_planner import FairRobustPlanner
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.feedback_experiments import save_episode
from src.school.feedback_replay import replay_feedback_episode
from src.school.state_estimator import StudentStateEstimator
from src.school.observation_model import ObservationConfig
from src.school.uncertainty_scenarios import UncertaintyScenarioConfig
from src.intervention.feedback_notes import NoteQuality
from src.evaluation.research_experiments import freeze, aggregate
from src.evaluation.research_experiments import run_one, make_controller
from src.evaluation.provenance import active_directory, verify_versions
from src.school.student_condition import StudentCondition
from src.observations.observable_events import ObservableEvent
import numpy as np


class SharedPipelineTests(unittest.TestCase):
    def test_every_baseline_uses_common_information_and_resources(self):
        config = ScenarioConfig(num_students=6, num_mentors=2, horizon=3,
                                monthly_admissions=1, monthly_appointments=5, budget=10)
        for mode in ('structured', 'b_matched', 'llm_notes', 'noisy_notes'):
            initial = []
            for name in BASELINES:
                with self.subTest(mode=mode, policy=name):
                    controller = ClosedLoopCMDPController(build_environment(config),
                        BaselinePolicy(name, seed=91), mode=mode,
                        extractor=FixtureObservationExtractor()).run_episode()
                    self.assertTrue(validate_feedback_episode(controller))
                    initial.append(controller.snapshots[0])
                    self.assertEqual(initial[-1].observation_mode, 'estimated_state')
                    self.assertTrue(controller.fairness_rows)
                    self.assertTrue(all(not d['allocation']['solver_settings'] for d in controller.decisions))
                    if name == 'wait':
                        self.assertTrue(all(not d['admitted_ids'] for d in controller.decisions))
            self.assertTrue(all(s == initial[0] for s in initial))

    def test_random_repeat_and_missing_severity(self):
        config = ScenarioConfig(num_students=6, horizon=3, budget=10)
        runs = [ClosedLoopCMDPController(build_environment(config), BaselinePolicy('random', seed=7))
                .run_episode() for _ in range(2)]
        self.assertEqual(runs[0].decisions, runs[1].decisions)
        state = build_environment(config).observe(fully_observed=False)
        self.assertEqual([s.student_id for s in BaselinePolicy('severity').rank_students(state)],
                         sorted(s.student_id for s in state.students if s.eligible))

    def test_authorized_observations_change_severity_without_truth_access(self):
        config = ScenarioConfig(num_students=2, horizon=1, budget=5)
        snapshots, ranked = [], []
        for low_id in ('SYN00001', 'SYN00002'):
            c = ClosedLoopCMDPController(build_environment(config), BaselinePolicy('severity'))
            c.initialize()
            c.events = [ObservableEvent(sid, sid, 0, 1,
                'low_participation' if sid == low_id else 'regular_participation')
                for sid in ('SYN00001', 'SYN00002')]
            state = c.prepare_decision_snapshot(1)
            ranked.append(c.policy.rank_students(state)[0].student_id)
            snapshots.append(state)
            # Changing evaluator-only truth cannot change already authorized input.
            c.environment._conditions = {sid: StudentCondition.WITHDRAWN for sid in c.environment._conditions}
            again = c.environment.operational_snapshot(tuple(r for r in c.registry if r.event_month == 0),
                estimates=state.estimated_student_states, risks=state.risk_estimates)
            self.assertEqual(state, again)
        self.assertEqual(ranked, ['SYN00001', 'SYN00002'])


class ReplayTests(unittest.TestCase):
    def test_research_group_specific_missingness_replays(self):
        config = load_config()
        config['scenario'].update(num_students=12, num_mentors=2, horizon=3, budget=10,
                                  monthly_admissions=1, monthly_appointments=5)
        config['primary_notes_true']['omission_probability'] = 1
        config['primary_notes_false']['omission_probability'] = 0
        c = make_controller(config, 'FairRobust', 'd_matched', 42).run_episode()
        self.assertEqual({q.omission_probability for q in c.note_quality_by_student.values()}, {0, 1})
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source'
            save_episode(c, source)
            result = replay_feedback_episode(source, Path(directory)/'replay')
            self.assertTrue(result['evidence_processing_history_match'])

    def test_all_policy_types_and_nondefault_inputs_replay(self):
        config = ScenarioConfig(num_students=6, num_mentors=2, horizon=3,
                                monthly_admissions=1, monthly_appointments=5, budget=10)
        policies = [*(BaselinePolicy(name, seed=97) for name in BASELINES),
            ConstrainedAllocationPlanner(time_limit=11),
            FairnessPlanner(minimum_access=.7, window_months=2),
            FairnessPlanner(enabled=False, minimum_access=.7, window_months=2),
            FairRobustPlanner(minimum_access=.6, window_months=2,
                uncertainty_config=UncertaintyScenarioConfig(.43, 1.8, 5))]
        for policy in policies:
            with self.subTest(policy=type(policy).__name__, name=getattr(policy, 'name', None)), \
                    tempfile.TemporaryDirectory() as directory:
                estimator = StudentStateEstimator(prior=(.6,.3,.1,0),
                    observation_config=ObservationConfig(missing_probability=.4))
                controller = ClosedLoopCMDPController(build_environment(config), policy,
                    mode='noisy_notes', extractor=FixtureObservationExtractor(), estimator=estimator,
                    note_quality_by_student={'SYN00001': NoteQuality(omission_probability=1)},
                    max_monitoring_notes_per_month=2).run_episode()
                source = Path(directory)/'source'
                save_episode(controller, source)
                with patch('src.intervention.ollama_client.OllamaClient.generate', side_effect=AssertionError('LLM called')):
                    a = replay_feedback_episode(source, Path(directory)/'a')
                    b = replay_feedback_episode(source, Path(directory)/'b')
                self.assertEqual(a['deterministic_digest'], b['deterministic_digest'])
                self.assertIn('fairness_windows', a['checked_records'])

    def test_tampered_and_historical_records_are_rejected(self):
        c = ClosedLoopCMDPController(build_environment(ScenarioConfig(num_students=2, horizon=2)),
                                     BaselinePolicy('wait')).run_episode()
        for field in ('scenario', 'replay_contract_version'):
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory)/'source'
                save_episode(c, source)
                path = source/'experiment_config.json'
                manifest = json.loads(path.read_text())
                if field == 'scenario':
                    manifest[field]['seed'] += 1
                else:
                    del manifest[field]
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'integrity|historical'):
                    replay_feedback_episode(source, Path(directory)/'replay')
                self.assertFalse((Path(directory)/'replay/replay_result.json').exists())

    def test_independent_planner_estimator_and_environment_matrices(self):
        from src.school.transition_model import P_WAIT, programme_matrix
        config = ScenarioConfig(num_students=3, horizon=2, effect_strength=.4)
        estimator = StudentStateEstimator(wait_matrix=programme_matrix(.2), treatment_matrix=programme_matrix(.6))
        c = ClosedLoopCMDPController(build_environment(config),
            ConstrainedAllocationPlanner(wait_matrix=programme_matrix(.3), treatment_matrix=programme_matrix(.8)),
            estimator=estimator, wait_matrix=P_WAIT, treatment_matrix=programme_matrix(.9)).run_episode()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source'
            save_episode(c, source)
            self.assertTrue(replay_feedback_episode(source, Path(directory)/'replay')['evidence_processing_history_match'])


class ProvenanceTests(unittest.TestCase):
    def test_same_label_cannot_mix_different_execution_settings(self):
        config = load_config()
        config['scenario'].update(num_students=6, num_mentors=2, horizon=3, budget=10,
                                  monthly_admissions=1, monthly_appointments=5)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = freeze(root, configuration=config)
            run_one(root, config, manifest, 'development', 'FairPoint', 'b_matched', 42, budget=5)
            run_one(root, config, manifest, 'development', 'FairPoint', 'b_matched', 43, budget=10)
            with self.assertRaisesRegex(ValueError, 'incompatible execution settings'):
                aggregate(root)

    def test_amendments_preserve_original_manifest_and_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('src.evaluation.research_experiments.fingerprint', return_value={'docs/research_evaluation_protocol.md': 'first'}):
                first = freeze(root)
                original = (root/'configuration_manifest.json').read_bytes()
                protocol = (root/'research_evaluation_protocol_frozen.md').read_bytes()
                self.assertEqual(first, freeze(root))
            with patch('src.evaluation.research_experiments.fingerprint', return_value={'docs/research_evaluation_protocol.md': 'second'}):
                with self.assertRaises(ValueError):
                    freeze(root)
                second = freeze(root, 'Correct execution settings')
            self.assertEqual(original, (root/'configuration_manifest.json').read_bytes())
            self.assertEqual(protocol, (root/'research_evaluation_protocol_frozen.md').read_bytes())
            self.assertEqual(second['predecessor'], first['input_digest'])
            self.assertNotEqual(first['input_digest'], second['input_digest'])
            with patch('src.evaluation.research_experiments.fingerprint', return_value={'docs/research_evaluation_protocol.md': 'third'}):
                third = freeze(root, 'Second correction')
            self.assertEqual(third['predecessor'], second['input_digest'])
            self.assertEqual(verify_versions(root)['verified_versions'], 3)
            (active_directory(root)/'research_evaluation_protocol_frozen.md').write_text('corrupt')
            with self.assertRaisesRegex(ValueError, 'corrupted'):
                verify_versions(root)

    def test_aggregation_rejects_mixed_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'episodes/old').mkdir(parents=True)
            (root/'episodes/old/summary.json').write_text(json.dumps({'input_digest': 'old'}))
            with patch('src.evaluation.research_experiments.checked_manifest', return_value={'input_digest': 'new'}):
                with self.assertRaisesRegex(ValueError, 'incompatible'):
                    aggregate(root)

    def test_cache_failure_and_heldout_amendment(self):
        config = load_config()
        config['scenario'].update(num_students=6, num_mentors=2, horizon=3, budget=10,
                                  monthly_admissions=1, monthly_appointments=5)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = freeze(root, configuration=config)
            first = run_one(root, config, manifest, 'evaluation', 'FairRobust', 'b_matched', 1000)
            version = active_directory(root)
            before = {str(p.relative_to(version)): p.read_bytes() for p in version.rglob('*') if p.is_file()}
            with patch('src.evaluation.research_experiments.make_controller', side_effect=AssertionError('cache missed')):
                self.assertEqual(first, run_one(root, config, manifest, 'evaluation', 'FairRobust', 'b_matched', 1000))
            updated = json.loads(json.dumps(config))
            updated['uncertainty']['radius'] = .44
            with self.assertRaises(ValueError):
                freeze(root, configuration=updated)
            amendment = freeze(root, 'Declared uncertainty sensitivity', configuration=updated)
            self.assertEqual(before, {str(p.relative_to(version)): p.read_bytes() for p in version.rglob('*') if p.is_file()})
            self.assertNotEqual(first['input_digest'], amendment['input_digest'])
            with patch.object(ClosedLoopCMDPController, 'run_episode', side_effect=RuntimeError('fixture failure')):
                with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                    run_one(root, updated, amendment, 'evaluation', 'FairRobust', 'b_matched', 1000)
            current = active_directory(root)
            self.assertFalse(list(current.glob('episodes/*/summary.json')))
            self.assertEqual(len(list(current.glob('episodes/*/failure.json'))), 1)
            aggregate(root)
            status = json.loads((current/'aggregation_status.json').read_text())
            self.assertFalse(status['primary_complete'])
            self.assertTrue(status['incomplete_or_failed'])
            self.assertEqual(verify_versions(root)['verified_versions'], 2)
            (version/first['trace_path']).write_bytes(b'corruption')
            with self.assertRaisesRegex(ValueError, 'corrupted'):
                verify_versions(root)


class ControlsTests(unittest.TestCase):
    def test_named_fair_research_policies_reject_disabled_constraints(self):
        config = load_config()
        config['scenario']['fairness_enabled'] = False
        for name in ('FairPoint', 'FairRobust'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'fairness_enabled'):
                research_policy(config, name)
        self.assertIsInstance(research_policy(config, 'ResourceOnlyPoint'), ConstrainedAllocationPlanner)

    def test_enabled_fairness_changes_zero_benefit_assignment(self):
        state = build_environment(ScenarioConfig(num_students=2, num_mentors=1,
            horizon=1, budget=5, monthly_admissions=1)).observe()
        for cls in (FairnessPlanner, FairRobustPlanner):
            kwargs = dict(minimum_access=1, wait_matrix=np.eye(4), treatment_matrix=np.eye(4))
            self.assertEqual(len(cls(enabled=True, **kwargs).plan(state).assignments), 1)
            self.assertFalse(cls(enabled=False, **kwargs).plan(state).assignments)

    def test_free_positive_effect_control_is_allowed_by_runner(self):
        config = ScenarioConfig(num_students=6, num_mentors=2, horizon=3, budget=0,
            cost_per_appointment=0, monthly_admissions=1, monthly_appointments=5)
        with tempfile.TemporaryDirectory() as directory, patch(
                'src.school.cmdp_environment.keyed_uniform', return_value=.975), patch(
                'src.school.cmdp_experiments.save_reports'):
            output = run_experiments(config, output=Path(directory)/'free',
                policies=('wait', 'need_priority'), development_seed_count=1, stage='development')
            rows = [json.loads(line) for line in (output/'episodes.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['programmes'], 0)
            self.assertGreater(rows[1]['programmes'], 0)
            self.assertTrue(all(r['spending'] == 0 for r in rows))

    def test_zero_effect_and_no_feasible_service_are_distinct(self):
        base = ScenarioConfig(num_students=6, num_mentors=2, horizon=3, budget=0,
                              monthly_admissions=1, monthly_appointments=5)
        for config in (base, replace(base, cost_per_appointment=0, monthly_appointments=4),
                       replace(base, cost_per_appointment=0, monthly_admissions=0),
                       replace(base, cost_per_appointment=0, effect_strength=0)):
            runs = [ClosedLoopCMDPController(build_environment(config), BaselinePolicy(name)).run_episode()
                    for name in BASELINES]
            self.assertTrue(all(r.evaluator_truth == runs[0].evaluator_truth for r in runs))
            for run in runs:
                self.assertTrue(validate_feedback_episode(run))
                self.assertEqual(run.environment.records[-1].remaining_budget, 0)
                if config.effect_strength:
                    self.assertFalse(any(d['admitted_ids'] for d in run.decisions))


if __name__ == '__main__':
    unittest.main()

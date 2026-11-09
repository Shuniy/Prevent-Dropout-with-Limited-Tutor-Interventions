"""Adversarial offline regressions for final Phase 3 artifact contracts."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.evaluation import provenance, research_experiments as experiments
from src.evaluation.research_report import generate_report
from src.intervention.observation_extractor import (LLMObservationExtractor,
    FixtureObservationExtractor, RecordedOutcomeExtractor, gold_payload)
from src.intervention.ollama_client import OllamaClient
from src.school import feedback_replay
from src.school.feedback_experiments import save_episode, run_feedback_experiments
from src.evaluation.report_artifacts import verify_reports
from src.evaluation.cached_observation_extractor import CachedObservationExtractor
from src.evaluation.extraction_evaluation import _note, build_benchmark


class RepairFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'research'
        self.config = experiments.load_config()
        self.config['scenario'].update(num_students=6, num_mentors=2, horizon=3,
            budget=10, monthly_admissions=1, monthly_appointments=5)
        self.config['evaluation'].update(development_seeds=[11], evaluation_seeds=[101, 102],
            secondary_seeds=[101], live_seeds=[101])
        self.manifest = experiments.freeze(self.root, configuration=self.config)
        self.version = provenance.active_directory(self.root)

    def run_cell(self, policy='FairPoint', seed=101, mode='d_matched', phase='evaluation', **options):
        return experiments.run_one(self.root, self.config, self.manifest,
            phase, policy, mode, seed, **options)

    def primary(self):
        for seed in self.config['evaluation']['evaluation_seeds']:
            for name in ('FairPoint', 'FairRobust'):
                self.run_cell(name, seed)

    def status(self):
        experiments.aggregate(self.root)
        return json.loads((self.version/'aggregation_status.json').read_text())

    def report(self):
        return generate_report(self.version)

    def episode(self, summary):
        return (self.version/summary['trace_path']).parent

    def rewrite(self, episode, filename, mutate):
        path = episode/filename
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value))
        (episode/'artifact_integrity.json').unlink()
        provenance.seal_directory(episode)


def inventory(path):
    return {p.relative_to(path).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


class ReportIntegrityTests(RepairFixture):
    def test_verification_is_independent_of_current_factories_and_source_checkout(self):
        self.run_cell()
        experiments.aggregate(self.root)
        with patch.object(experiments, 'make_policy', side_effect=AssertionError('current factory used')), patch.object(
                provenance, 'source_fingerprints', return_value={'changed_checkout': 'different'}):
            self.assertTrue(provenance.verify_versions(self.root)['fully_verified'])

    def test_replaced_convenience_alias_cannot_hide_changed_table(self):
        experiments.aggregate(self.root)
        alias = self.version/'episode_results.csv'
        alias.unlink()
        alias.write_text('retention_rate\n0.123456\n')
        with self.assertRaises(ValueError):
            provenance.verify_versions(self.root)

    def test_finalized_report_and_sources_verify(self):
        row = self.run_cell()
        report = self.report()
        result = provenance.verify_versions(self.root)
        self.assertTrue(result['fully_verified'])
        self.assertEqual(result['verified_report_generations'], 1)
        manifest = json.loads((report.parent/'report_manifest.json').read_text())
        self.assertEqual(manifest['input_digest'], self.manifest['input_digest'])
        source, = manifest['contributing_episodes']
        self.assertEqual(source['episode_identity'], row['episode_identity'])
        self.assertEqual(source['summary_identity'], provenance.digest(row))
        self.assertIn('research_results.md', manifest['artifacts'])
        self.assertTrue(any(name.startswith('figures/') for name in manifest['artifacts']))

    def test_numerical_csv_change_rejected(self):
        self.primary()
        path = self.report().parent/'primary_policy_comparison.csv'
        data = path.read_text()
        self.assertIn('0.9166666666666667', data)
        path.write_text(data.replace('0.9166666666666667', '0.1111111111111111', 1))
        with self.assertRaisesRegex(ValueError, 'corrupted artifact'):
            provenance.verify_versions(self.root)

    def test_deleted_figure_rejected(self):
        path = self.report()
        next((path.parent/'figures').glob('*.png')).unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            provenance.verify_versions(self.root)

    def test_unexpected_file_including_nested_seal_name_rejected(self):
        path = self.report()
        (path.parent/'figures/artifact_integrity.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            provenance.verify_versions(self.root)

    def test_substituted_symlink_is_not_an_artifact(self):
        path = self.report().parent/'episode_results.csv'
        outside = self.root/'same_bytes.csv'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            provenance.verify_versions(self.root)

    def test_completed_episode_corruption_still_rejected(self):
        summary = self.run_cell()
        self.report()
        (self.episode(summary)/'trace.json.gz').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'corrupted artifact'):
            provenance.verify_versions(self.root)

    def test_new_generation_and_amendment_preserve_all_prior_bytes(self):
        self.run_cell()
        first = self.report()
        before = inventory(first.parent)
        self.run_cell('FairRobust')
        second = self.report()
        self.assertNotEqual(first.parent, second.parent)
        self.assertEqual(before, inventory(first.parent))
        previous_version = inventory(self.version)
        updated = deepcopy(self.config)
        updated['uncertainty']['radius'] = .44
        amended = experiments.freeze(self.root, 'Test-only amendment', configuration=updated)
        self.assertEqual(amended['predecessor'], self.manifest['input_digest'])
        self.assertEqual(previous_version, inventory(self.version))
        self.assertEqual(provenance.verify_versions(self.root)['verified_report_generations'], 2)

    def test_deleted_generation_is_detected_by_registry(self):
        report = self.report()
        shutil.rmtree(report.parent)
        with self.assertRaisesRegex(ValueError, 'report generation'):
            provenance.verify_versions(self.root)

    def test_interrupted_render_cannot_finalize(self):
        with patch('src.evaluation.research_report._figures', side_effect=OSError('render interrupted')):
            with self.assertRaisesRegex(OSError, 'render interrupted'):
                self.report()
        self.assertEqual(verify_reports(self.version), 0)
        self.assertFalse((self.version/'current_report.json').exists())

    def test_source_mismatch_even_with_new_report_seal_is_rejected(self):
        report = self.report()
        manifest = report.parent/'report_manifest.json'
        value = json.loads(manifest.read_text())
        value['input_digest'] = '0'*64
        manifest.write_text(json.dumps(value))
        (report.parent/'artifact_integrity.json').unlink()
        provenance.seal_directory(report.parent)
        with self.assertRaisesRegex(ValueError, 'identity'):
            provenance.verify_versions(self.root)

    def test_legacy_scope_is_explicit_and_not_retrofitted(self):
        legacy = deepcopy(self.manifest)
        legacy['manifest_version'] = 3
        legacy.pop('primary_evaluation')
        legacy.pop('report_contract_version')
        legacy['input_digest'] = provenance.digest({k: v for k, v in legacy.items()
            if k not in ('input_digest', 'frozen_at_utc')})
        target = self.version.with_name(legacy['input_digest'])
        self.version.rename(target)
        for directory in (self.root, target):
            (directory/'configuration_manifest.json').write_text(json.dumps(legacy))
        (self.root/'current_version.json').write_text(json.dumps({'input_digest': legacy['input_digest']}))
        before = inventory(target)
        result = provenance.verify_versions(self.root)
        self.assertFalse(result['fully_verified'])
        self.assertEqual(result['status'], 'historical_partial')
        command = [sys.executable, 'scripts/verify_experiment_records.py', str(self.root)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertEqual(subprocess.run(command+['--allow-historical'], capture_output=True).returncode, 0)
        with self.assertRaisesRegex(ValueError, 'historical'):
            generate_report(target)
        with self.assertRaises(ValueError):
            experiments.freeze(self.root, configuration=self.config)
        experiments.freeze(self.root, 'New contracts; preserve historical evidence', configuration=self.config)
        self.assertEqual(before, inventory(target))


class PrimaryCompletionTests(RepairFixture):
    def test_supported_sensitivity_overrides_keep_valid_reconstruction(self):
        for setting, options in (('effect_test', {'effect': .4}),
                                 ('radius_test', {'radius': .44}),
                                 ('missingness_test', {'missingness': .4})):
            self.run_cell('FairRobust', setting=setting, **options)
        self.assertEqual(self.status()['actual_primary_episodes'], 0)
        self.assertTrue(provenance.verify_versions(self.root)['fully_verified'])

    def test_partially_specified_extractor_cannot_enter_aggregation(self):
        summary = self.run_cell()
        self.rewrite(self.episode(summary), 'summary.json',
                     lambda r: r.update(extractor_identity={'adapter': 'historical'}))
        with self.assertRaisesRegex(ValueError, 'historical or partially'):
            self.status()

    def test_frozen_configuration_refuses_credentials_without_persisting_them(self):
        for key, value in (('api_key', 'NEVER_SAVE'),
                           ('base_url', 'http://user:NEVER_SAVE@host')):
            config = deepcopy(self.config)
            config['llm'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                experiments.freeze(self.root, 'Do not retain credentials', configuration=config)
        self.assertNotIn('NEVER_SAVE', ''.join(p.read_text() for p in self.version.glob('*.json') if p.is_file()))

    def test_unknown_execution_options_cannot_leak_into_attempt_records(self):
        with self.assertRaisesRegex(ValueError, 'allowlisted'):
            self.run_cell(api_key='NEVER_SAVE')
        self.assertFalse(list(self.version.glob('episodes/*')))

    def test_effective_controller_drift_cannot_count_as_primary(self):
        original = experiments.make_controller

        def drifted(config, name, mode, seed, **options):
            return original(config, name, mode, seed, **{**options, 'budget': 5})

        with self.assertRaisesRegex(ValueError, 'effective|configuration'):
            with patch.object(experiments, 'make_controller', side_effect=drifted):
                self.primary()
            self.status()

    def test_zero_episodes_is_exploratory(self):
        status = self.status()
        self.assertFalse(status['primary_complete'])
        self.assertEqual(status['actual_primary_episodes'], 0)
        self.assertEqual(status['expected_primary_episodes'], 4)
        self.assertEqual(len(status['missing_primary_cells']), 4)
        self.assertIn('INCOMPLETE / EXPLORATORY', self.report().read_text())

    def test_only_point_has_no_completed_primary_declaration(self):
        self.run_cell()
        status = self.status()
        self.assertFalse(status['primary_complete'])
        self.assertEqual(status['actual_primary_episodes'], 1)
        report = self.report().read_text()
        self.assertIn('Validated primary episodes: 1 / 4', report)
        self.assertFalse((self.version/'primary_complete.json').exists())

    def test_one_pair_keeps_subset_intervals_out_of_primary_table(self):
        self.run_cell()
        self.run_cell('FairRobust')
        status = self.status()
        self.assertEqual(status['completed_paired_seeds'], 1)
        self.assertFalse(status['primary_complete'])
        self.assertEqual((self.version/'primary_policy_comparison.csv').read_text(), 'status\nnot_executed\n')
        self.assertIn('conditional_on_completed_subset', (self.version/'exploratory_primary_comparison.csv').read_text())

    def test_unequal_policy_seed_sets_produce_labeled_subset(self):
        self.run_cell()
        self.run_cell('FairRobust')
        self.run_cell(seed=102)
        self.assertEqual(self.status()['completed_paired_seeds'], 1)
        self.assertIn('INCOMPLETE / EXPLORATORY', self.report().read_text())

    def test_failed_robust_cell_remains_failed_and_missing(self):
        self.run_cell()
        with patch.object(experiments, 'score_episode', side_effect=RuntimeError('failed primary cell')):
            with self.assertRaises(RuntimeError):
                self.run_cell('FairRobust')
        status = self.status()
        self.assertFalse(status['primary_complete'])
        self.assertEqual(status['failed_primary_cells'], [{'policy': 'FairRobust', 'seed': 101, 'status': 'failed'}])
        self.assertIn(['FairRobust', 101], status['missing_primary_cells'])
        self.assertIn('FAILED / INCOMPLETE', self.report().read_text())

    def test_complete_primary_matrix_allows_publication(self):
        self.primary()
        status = self.status()
        self.assertTrue(status['primary_complete'])
        self.assertEqual(status['actual_primary_episodes'], 4)
        report = self.report().read_text()
        self.assertIn('COMPLETE PRIMARY EVALUATION', report)
        self.assertIn('The prespecified primary estimate is', report)
        self.assertTrue((self.version/'primary_complete.json').is_file())

    def test_incompatible_identity_rejected(self):
        summary = self.run_cell()
        self.rewrite(self.episode(summary), 'summary.json', lambda r: r.update(input_digest='0'*64))
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            self.status()

    def test_duplicate_cells_rejected(self):
        summary = self.run_cell()
        shutil.copytree(self.episode(summary), self.version/'episodes/duplicate')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.status()

    def test_malformed_seed_rejected(self):
        summary = self.run_cell()
        self.rewrite(self.episode(summary), 'summary.json', lambda r: r.update(seed='101'))
        with self.assertRaises(ValueError):
            self.status()

    def test_secondary_development_and_other_settings_never_count(self):
        self.run_cell(phase='development')
        self.run_cell('FairRobust', phase='secondary')
        self.run_cell(seed=102, setting='budget_control')
        self.run_cell('FairRobust', seed=102, mode='structured')
        status = self.status()
        self.assertEqual(status['actual_primary_episodes'], 0)
        self.assertEqual(len(status['excluded_episodes']), 4)

    def test_nondefault_budget_cannot_complete_primary(self):
        for seed in (101, 102):
            for policy in ('FairPoint', 'FairRobust'):
                self.run_cell(policy, seed, budget=5)
        status = self.status()
        self.assertEqual(status['actual_primary_episodes'], 0)
        self.assertEqual(len(status['invalid_primary_cells']), 4)

    def test_unrelated_failure_does_not_block_complete_primary(self):
        self.primary()
        with patch.object(experiments, 'score_episode', side_effect=RuntimeError('secondary failed')):
            with self.assertRaises(RuntimeError):
                self.run_cell(phase='secondary')
        self.assertTrue(self.status()['primary_complete'])

    def test_duplicate_frozen_seeds_rejected(self):
        self.config['evaluation']['evaluation_seeds'] = [101, 101]
        with self.assertRaisesRegex(ValueError, 'unique integer'):
            experiments.validate_config(self.config)


class PersistenceTests(RepairFixture):
    def test_replay_sealing_failure_never_publishes_success(self):
        summary = self.run_cell()
        source = self.episode(summary)/'replay'
        destination = self.root/'failed-seal-replay'
        with patch.object(feedback_replay, 'seal_directory', side_effect=OSError('replay seal failed')):
            with self.assertRaisesRegex(OSError, 'replay seal failed'):
                feedback_replay.replay_feedback_episode(source, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(list(self.root.glob('.failed/*/failure.json')))
        self.assertFalse(list(self.root.glob('.failed/*/replay_result.json')))

    def test_exceptions_at_each_episode_stage_have_no_success_marker(self):
        injections = [
            ('make_controller', RuntimeError('construction')),
            ('ClosedLoopCMDPController.run_episode', RuntimeError('simulation')),
            ('score_episode', RuntimeError('scoring')),
            ('save_trace', OSError('trace writing')),
            ('gzip.open', OSError('compressed writing')),
            ('write_json', TypeError('serialization')),
            ('seal_directory', OSError('sealing')),
        ]
        for index, (name, error) in enumerate(injections):
            with self.subTest(stage=name), patch('src.evaluation.research_experiments.'+name, side_effect=error):
                with self.assertRaises(type(error)):
                    self.run_cell(seed=500+index)
        self.assertFalse(list(self.version.glob('episodes/*/summary.json')))
        failures = list(self.version.glob('episodes/*/failure.json'))
        self.assertEqual(len(failures), len(injections))
        for path in failures:
            failure = json.loads(path.read_text())
            self.assertEqual(failure['status'], 'failed')
            self.assertTrue(failure['error'])
            self.assertTrue(failure['error_type'])
            self.assertIn('identity', failure)
        self.assertTrue(provenance.verify_versions(self.root)['fully_verified'])

    def test_publication_failure_preserves_previous_episode_and_report(self):
        completed = self.run_cell()
        report = self.report()
        before, reports_before = inventory(self.episode(completed)), inventory(report.parent)
        original_publish = provenance.publish_directory
        def failed_final_publication(stage, destination):
            if destination.parent == self.version/'episodes':
                self.assertTrue((stage/'artifact_integrity.json').exists())
                raise OSError('atomic rename failed')
            return original_publish(stage, destination)
        with patch.object(provenance, 'publish_directory', side_effect=failed_final_publication):
            with self.assertRaisesRegex(OSError, 'atomic rename failed'):
                self.run_cell('FairRobust')
        self.assertEqual(before, inventory(self.episode(completed)))
        self.assertEqual(reports_before, inventory(report.parent))
        self.assertEqual(len(list(self.version.glob('episodes/*/summary.json'))), 1)
        self.assertEqual(len(list(self.version.glob('episodes/*/failure.json'))), 1)

    def test_failed_identity_cannot_be_silently_retried(self):
        with patch.object(experiments, 'score_episode', side_effect=RuntimeError('first attempt')):
            with self.assertRaises(RuntimeError):
                self.run_cell()
        with patch.object(experiments, 'make_controller', side_effect=AssertionError('retried')):
            with self.assertRaises(FileExistsError):
                self.run_cell()

    def test_explicit_default_cannot_silently_retry_the_same_effective_execution(self):
        with patch.object(experiments, 'score_episode', side_effect=RuntimeError('failed effective identity')):
            with self.assertRaises(RuntimeError):
                self.run_cell()
        with self.assertRaises(FileExistsError):
            self.run_cell(budget=self.config['scenario']['budget'])

    def test_completed_episode_cache_is_immutable(self):
        summary = self.run_cell()
        before = inventory(self.episode(summary))
        with patch.object(experiments, 'make_controller', side_effect=AssertionError('cache missed')):
            self.assertEqual(summary, self.run_cell())
        self.assertEqual(before, inventory(self.episode(summary)))
        provenance.verify_directory(self.episode(summary))

    def test_unpublished_staging_does_not_enter_aggregation_or_verification(self):
        path = self.version/'episodes/.staging/interrupted'
        path.mkdir(parents=True)
        (path/'summary.json').write_text('{broken unfinished bytes')
        self.assertEqual(self.status()['complete_episodes'], 0)
        self.assertTrue(provenance.verify_versions(self.root)['fully_verified'])

    def test_replay_publication_failure_and_duplicate_handling(self):
        summary = self.run_cell()
        source = self.episode(summary)/'replay'
        target = self.root/'replay'
        original = inventory(source)
        with patch.object(provenance, 'publish_directory', side_effect=OSError('replay publication')):
            with self.assertRaisesRegex(OSError, 'replay publication'):
                feedback_replay.replay_feedback_episode(source, target)
        self.assertFalse(target.exists())
        self.assertEqual(original, inventory(source))
        self.assertTrue(list(self.root.glob('.failed/*/failure.json')))
        result = feedback_replay.replay_feedback_episode(source, target)
        self.assertEqual(result['real_llm_calls'], 0)
        provenance.verify_directory(target, 'record_integrity.json')
        before = inventory(target)
        with self.assertRaises(FileExistsError):
            feedback_replay.replay_feedback_episode(source, target)
        self.assertEqual(before, inventory(target))

    def test_save_serialization_failure_is_private(self):
        controller = experiments.make_controller(self.config, 'FairPoint', 'd_matched', 101).run_episode()
        destination = self.root/'save-failed'
        with patch('src.school.feedback_experiments.write_jsonl', side_effect=TypeError('JSON failed')):
            with self.assertRaisesRegex(TypeError, 'JSON failed'):
                save_episode(controller, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(list(self.root.glob('.failed/*/failure.json')))


class ReproducedDefects(RepairFixture):
    def test_A_finalized_aggregate_tampering_is_detected(self):
        self.run_cell()
        experiments.aggregate(self.root)
        path = self.version/'episode_results.csv'
        path.write_text(path.read_text().replace('0.8333333333333334', '0.123456789') + '\n')
        with self.assertRaises(ValueError):
            provenance.verify_versions(self.root)

    def test_B_wrong_information_mode_cannot_complete_primary(self):
        for seed in (101, 102):
            for name in ('FairPoint', 'FairRobust'):
                self.run_cell(name, seed, mode='b_matched')
        self.assertFalse(self.status()['primary_complete'])

    def test_B_subset_report_is_visibly_exploratory(self):
        self.run_cell()
        self.run_cell('FairRobust')
        experiments.aggregate(self.root)
        path = generate_report(self.version)
        report = path.read_text()
        self.assertIn('INCOMPLETE / EXPLORATORY', report)
        self.assertNotIn('The prespecified primary estimate is', report)

    def test_C_scoring_failure_has_diagnostics(self):
        with patch.object(experiments, 'score_episode', side_effect=RuntimeError('scorecard injected')):
            with self.assertRaisesRegex(RuntimeError, 'scorecard injected'):
                self.run_cell()
        failures = list(self.version.glob('episodes/*/failure.json'))
        self.assertEqual(len(failures), 1)
        self.assertIn('scorecard injected', failures[0].read_text())
        self.assertFalse(list(self.version.glob('episodes/*/summary.json')))

    def test_C_sealing_failure_cannot_publish_success(self):
        with patch.object(experiments, 'seal_directory', side_effect=OSError('seal injected')):
            with self.assertRaisesRegex(OSError, 'seal injected'):
                self.run_cell()
        self.assertFalse(list(self.version.glob('episodes/*/summary.json')))
        self.assertTrue(list(self.version.glob('episodes/*/failure.json')))

    def test_C_late_replay_mismatch_does_not_publish_destination(self):
        controller = experiments.make_controller(self.config, 'FairPoint', 'd_matched', 101).run_episode()
        source, target = self.root/'original', self.root/'replayed'
        save_episode(controller, source)
        original_read = feedback_replay.read_jsonl

        def changed_read(path):
            rows = original_read(path)
            if path.name == 'final_beliefs.jsonl' and source not in path.parents:
                return rows + [{'injected': 'late mismatch'}]
            return rows

        with patch.object(feedback_replay, 'read_jsonl', side_effect=changed_read):
            with self.assertRaisesRegex(ValueError, 'final_beliefs mismatch'):
                feedback_replay.replay_feedback_episode(source, target)
        self.assertFalse(target.exists())


class ExtractorReproductions(unittest.TestCase):
    def test_feedback_metadata_agrees_with_actual_execution_identity(self):
        from src.school.scenario_config import ScenarioConfig
        extractor = LLMObservationExtractor(OllamaClient(temperature=.4))
        with tempfile.TemporaryDirectory() as directory, patch(
                'src.school.feedback_experiments.plot_episode'), patch.object(
                extractor.client, 'generate', side_effect=AssertionError('live model called')):
            output = Path(directory)/'feedback'
            run_feedback_experiments(ScenarioConfig(num_students=2, num_mentors=1, horizon=1, budget=5),
                output=output, modes=('structured',), policies=('resource',), extractor=extractor)
            record = json.loads((output/'experiment_config.json').read_text())
            self.assertEqual(record['llm_options']['temperature'], .4)
            self.assertEqual(record['llm_options']['temperature'], record['extractor_identity']['temperature'])

    def test_unknown_backend_implementation_is_explicitly_partial(self):
        class OtherBackend(OllamaClient):
            pass
        identity = provenance.extractor_identity(LLMObservationExtractor(OtherBackend()))
        self.assertIn('OtherBackend', identity['client_adapter'])
        self.assertEqual(identity['configuration_status'], 'partial_unsupported_adapter')
        with self.assertRaises(ValueError):
            provenance.validate_extractor_identity(identity)

    def test_D_endpoint_is_part_of_execution_identity(self):
        a = LLMObservationExtractor(OllamaClient(base_url='http://host-a:11434'))
        b = LLMObservationExtractor(OllamaClient(base_url='http://host-b:11434'))
        self.assertNotEqual(provenance.extractor_identity(a), provenance.extractor_identity(b))

    def test_identical_configuration_is_stable_without_network(self):
        with patch('src.intervention.ollama_client.urlopen', side_effect=AssertionError('network')):
            a = LLMObservationExtractor(OllamaClient(base_url='HTTP://HOST-A:80/'))
            b = LLMObservationExtractor(OllamaClient(base_url='http://host-a'))
            self.assertEqual(provenance.extractor_identity(a), provenance.extractor_identity(b))
            provenance.validate_extractor_identity(provenance.extractor_identity(a))

    def test_digest_and_available_execution_options_invalidate_identity(self):
        baseline = provenance.extractor_identity(LLMObservationExtractor(OllamaClient()))
        for options in ({'model_digest': 'weights-a'}, {'num_ctx': 4096}, {'temperature': .5},
                        {'timeout': 12}, {'model': 'different-tag'}):
            with self.subTest(options=options):
                self.assertNotEqual(baseline, provenance.extractor_identity(LLMObservationExtractor(OllamaClient(**options))))
        a = provenance.extractor_identity(LLMObservationExtractor(OllamaClient(model_digest='weights-a')))
        b = provenance.extractor_identity(LLMObservationExtractor(OllamaClient(model_digest='weights-b')))
        self.assertNotEqual(a, b)

    def test_prompt_schema_and_validation_fingerprints_are_present(self):
        baseline = provenance.extractor_identity(None)
        with patch('src.intervention.observation_extractor.SYSTEM_PROMPT', 'new prompt'):
            self.assertNotEqual(baseline, provenance.extractor_identity(None))
        with patch('src.intervention.observation_extractor.EXTRACTION_SCHEMA', {'type': 'null'}):
            self.assertNotEqual(baseline, provenance.extractor_identity(None))
        self.assertEqual(len(baseline['validation_code_sha256']), 64)
        self.assertEqual(len(baseline['client_code_sha256']), 64)

    def test_fixture_recorded_and_real_identities_are_distinct(self):
        fixture = provenance.extractor_identity(FixtureObservationExtractor())
        other_fixture = provenance.extractor_identity(FixtureObservationExtractor({'different': 'fixture'}))
        recorded = provenance.extractor_identity(RecordedOutcomeExtractor([], []))
        real = provenance.extractor_identity(LLMObservationExtractor(OllamaClient()))
        self.assertEqual(len({provenance.digest(i) for i in (fixture, other_fixture, recorded, real)}), 4)

    def test_credentials_query_and_arbitrary_configuration_are_never_serialized(self):
        a = LLMObservationExtractor(OllamaClient(base_url='https://user:password@PRIVATE.example/prefix?api_key=secret#token'))
        a.configuration = {'api_key': 'NEVER_SAVE', 'authorization': 'Bearer confidential',
                           'model_metadata': {'unrelated_token': 'NEVER_SAVE'}}
        identity = provenance.extractor_identity(a)
        encoded = json.dumps(identity)
        for sensitive in ('user', 'password', 'secret', 'token', 'PRIVATE.example', '/prefix', 'NEVER_SAVE', 'confidential'):
            self.assertNotIn(sensitive, encoded)
        b = LLMObservationExtractor(OllamaClient(base_url='https://different:credentials@private.example/prefix'))
        self.assertEqual(identity, provenance.extractor_identity(b))

    def test_unavailable_digest_and_historical_identity_are_explicit(self):
        identity = provenance.extractor_identity(LLMObservationExtractor(OllamaClient()))
        self.assertIsNone(identity['model_digest'])
        self.assertEqual(identity['model_identity_limitation'], 'mutable_tag_without_weight_digest')
        for bad in ({}, {'adapter': 'old'}, {**identity, 'identity_version': 1},
                    {**identity, 'configuration_status': 'partial_unsupported_adapter'}):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'historical or partially'):
                provenance.validate_extractor_identity(bad)

    def test_real_cache_changes_with_endpoint_and_settings(self):
        note = _note(build_benchmark()[0])
        client = OllamaClient(base_url='http://first')
        extractor = LLMObservationExtractor(client)
        with patch.object(client, 'generate', return_value=gold_payload(note)) as generate:
            extractor.extract(note, 3)
            extractor.extract(note, 3)
            self.assertEqual(generate.call_count, 1)
            client.base_url = 'http://second'
            extractor.extract(note, 3)
            client.temperature = .4
            extractor.extract(note, 3)
            self.assertEqual(generate.call_count, 3)

    def test_persistent_cache_has_sanitized_execution_identity(self):
        note = _note(build_benchmark()[0])
        metadata = {'models': [{'name': 'qwen3.5:latest', 'digest': 'installed-weights',
                               'api_key': 'NEVER_SAVE'}]}
        with tempfile.TemporaryDirectory() as directory, patch(
                'src.evaluation.cached_observation_extractor.urlopen',
                side_effect=lambda *a, **k: io.BytesIO(json.dumps(metadata).encode())), patch(
                'src.intervention.ollama_client.OllamaClient.generate', return_value=gold_payload(note)) as generate:
            extractor = CachedObservationExtractor(directory,
                base_url='https://user:password@private.example/prefix?token=secret')
            extractor.configuration['api_key'] = 'NEVER_SAVE'
            extractor.extract(note, 3)
            extractor.extract(note, 3)
            extractor.client.base_url = 'http://different-endpoint'
            extractor.extract(note, 3)
            self.assertEqual(generate.call_count, 2)
            encoded = json.dumps(extractor.configuration) + ''.join(p.read_text() for p in Path(directory).glob('*.json'))
            for sensitive in ('password', 'NEVER_SAVE', 'private.example', 'token=secret'):
                self.assertNotIn(sensitive, encoded)
            self.assertEqual(extractor.configuration['model_digest'], 'installed-weights')


if __name__ == '__main__':
    unittest.main()

"""Held-out language boundaries, downstream decisions and frozen experiments."""
from dataclasses import asdict,replace
from pathlib import Path
import tempfile
import unittest

from src.evaluation.phase5_language import (build_language_benchmark,validate_partitions,evaluate_language,
    matched_snapshot_evaluation,active_programme_language_example,gold_canonical_text)
from src.evaluation.phase5_experiments import (load_configuration,paired_report,make_controller,four_scorecards,
    compatibility_audit,run_cell)
from src.intervention.observation_extractor import FixtureObservationExtractor,validate_extraction,gold_payload
from src.school.delivery_contracts import WeeklyNote,DeliveryAction
from src.school.delivery_config import DeliveryConfig
from src.school.phase5_delivery import save_phase5_episode,replay_phase5_episode
from src.school.delivery_experiments import normalized


class LanguageTests(unittest.TestCase):
    def test_scenario_paraphrase_and_template_partitions(self):
        cases=build_language_benchmark()
        validate_partitions(cases)
        self.assertEqual([sum(c['split']==s for c in cases) for s in ('development','validation','test')],[16,12,20])
        for field in ('scenario_id','paraphrase_group','template_family'):
            bad=[dict(c) for c in cases]
            bad[-1][field]=bad[0][field]
            with self.assertRaisesRegex(ValueError,'leakage'):
                validate_partitions(bad)

    def test_gold_is_text_supported_not_hidden_truth(self):
        for c in build_language_benchmark():
            self.assertNotIn('true_condition',str(c))
            if c['gold']:
                for f in c['gold']['observations']:
                    self.assertEqual(c['note']['text'][f['start_offset']:f['end_offset']],f['evidence'])
                    self.assertEqual(f['source_month'],c['annotation']['source_week'])
        transport=next(c for c in build_language_benchmark() if c['category']=='transport_cost_report')
        self.assertEqual(transport['annotation']['out_of_schema_construct'],'reported_transport_cost_difficulty')
        self.assertFalse(transport['gold']['observations'])

    def test_missing_and_heldout_are_misses_not_correct_abstentions(self):
        report=evaluate_language()
        metric=report['splits']['test']['methods']['deterministic_grammar']['metrics']
        self.assertEqual(metric['micro']['tp'],0)
        self.assertGreater(metric['micro']['fn'],0)
        self.assertEqual(metric['micro']['recall'],0)
        self.assertIsNone(metric['micro']['precision'])
        self.assertEqual(report['llm']['status'],'unexecuted')

    def test_missing_live_model_is_unexecuted_without_fixture_substitution(self):
        from unittest.mock import patch
        from src.intervention.observation_extractor import LLMObservationExtractor
        from src.intervention.ollama_client import OllamaClient
        client=OllamaClient(model='deliberately_unavailable')
        with patch.object(client,'generate',side_effect=RuntimeError('Ollama HTTP 404')):
            report=evaluate_language(live_extractor=LLMObservationExtractor(client))
        self.assertEqual(report['llm']['status'],'unexecuted_model_unavailable')
        self.assertTrue(all(v['methods']['prompted_llm']['metrics'] is None for v in report['splits'].values()))
        self.assertTrue(all(r['status']!='accepted' for v in report['splits'].values()
                            for r in v['methods']['prompted_llm']['records']))

    def test_available_but_invalid_live_outputs_are_executed_failures(self):
        from unittest.mock import patch
        from src.intervention.observation_extractor import LLMObservationExtractor
        from src.intervention.ollama_client import OllamaClient
        client=OllamaClient(model='invalid-output-fixture')
        with patch.object(client,'generate',return_value={}):
            report=evaluate_language(live_extractor=LLMObservationExtractor(client))
        self.assertEqual(report['llm']['status'],'executed')
        self.assertGreater(report['splits']['test']['methods']['prompted_llm']['metrics']['failure_rate_all_eligible'],0)

    def test_unsupported_semantics_and_spans_quarantined(self):
        text='The school reports regular participation in recent activities.'
        note=WeeklyNote('n','s',0,1,text,('e',))
        payload=gold_payload(note)
        payload['observations'][0]['value']='low'
        with self.assertRaisesRegex(ValueError,'unsupported assertion'):
            validate_extraction(payload,note,1)
        payload=gold_payload(note);payload['observations'][0]['end_offset']-=1
        with self.assertRaisesRegex(ValueError,'span'):
            validate_extraction(payload,note,1)

    def test_negation_conflict_and_unknown_are_separate(self):
        cases=build_language_benchmark()
        for label,status,condition in (('denial','reported','absent'),('disagreement','conflicting','unknown'),
                                        ('insufficient','insufficient_evidence','unknown')):
            c=next(c for c in cases if c['category']==label)
            note=WeeklyNote(**{**c['weekly_note'],'source_event_ids':tuple(c['weekly_note']['source_event_ids'])})
            batch=FixtureObservationExtractor().extract(note,1)
            self.assertEqual(batch.facts[0].assertion_status,status)
            self.assertEqual(batch.facts[0].condition_status,condition)

    def test_delayed_date_not_refreshed_to_receipt(self):
        c=next(c for c in build_language_benchmark() if c['category']=='delayed_source')
        self.assertEqual(c['gold']['observations'][0]['source_month'],0)
        self.assertEqual(c['as_of_month'],3)
        note=WeeklyNote('n','s',0,3,gold_canonical_text(c),('e',))
        with self.assertRaises(ValueError):
            FixtureObservationExtractor().extract(note,2)
        self.assertEqual(FixtureObservationExtractor().extract(note,3).facts[0].source_month,0)

    def test_actual_snapshot_extraction_and_zero_attempt_unavailable(self):
        empty=matched_snapshot_evaluation([])
        self.assertEqual(empty['status'],'unavailable_zero_extraction_attempts')
        case=next(c for c in build_language_benchmark() if c['category']=='participation_ledger')
        report=matched_snapshot_evaluation([case])
        self.assertGreater(report['attempts'],0)
        self.assertGreater(report['cases'][0]['belief_l1'],0)
        self.assertTrue(all(a['constraint_valid'] for a in report['cases'][0]['arms'].values()))

    def test_actual_session_language_can_change_later_feasible_decision(self):
        report=active_programme_language_example()
        self.assertEqual(report['gold_cutoff2_review'],'cancel')
        self.assertEqual(report['extracted_cutoff2_review'],'continue')
        self.assertTrue(report['later_assignment_disagreement'])

    def test_extraction_cannot_change_fixed_action_transition(self):
        config=DeliveryConfig(num_students=6,horizon_weeks=6,sessions_required=2)
        a,p=make_controller(config,'test',100,'wait',information='structured_observable')
        b,_=make_controller(config,'test',100,'wait',information='heldout_style')
        a.prepare_decision_snapshot();b.prepare_decision_snapshot()
        a.environment.step(DeliveryAction());b.environment.step(DeliveryAction())
        self.assertEqual(a.environment.evaluator_truth,b.environment.evaluator_truth)
        self.assertEqual(a.environment.exogenous_draws,b.environment.exogenous_draws)

    def test_group_missing_and_heldout_closed_loop_replay(self):
        for information in ('group_dependent','heldout_style','corrupted_language','random_missing'):
            c,p=make_controller(DeliveryConfig(num_students=6,horizon_weeks=6,sessions_required=2),
                'test',100,'point',information=information)
            c.run_episode()
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'episode'
                save_phase5_episode(c,p,output,protocol_text='frozen test')
                self.assertEqual(replay_phase5_episode(output)['status'],'exact_replay_verified')


class ResearchTests(unittest.TestCase):
    def test_adverse_matrix_uses_existing_contract_and_changes_fixed_action_outcome(self):
        from src.evaluation.phase5_experiments import adverse_effect_config
        from src.school.transition_model import sample_condition
        from src.school.student_condition import StudentCondition as C
        base=DeliveryConfig();adverse=adverse_effect_config(base)
        self.assertGreater(adverse.weekly_tutoring_matrix[2][3],base.weekly_wait_matrix[2][3])
        self.assertEqual(sample_condition(C.DISENGAGED,base.weekly_wait_matrix,.94),C.DISENGAGED)
        self.assertEqual(sample_condition(C.DISENGAGED,adverse.treatment_matrix,.94),C.WITHDRAWN)

    def primary_rows(self):
        from src.evaluation.provenance import digest
        config=load_configuration();base=DeliveryConfig(**config['delivery'])
        return config,[dict(seed=seed,policy=policy,information='group_dependent',setting='primary',
            population_seed=config['phase5']['primary_population_seed'],
            configuration_identity=digest(asdict(replace(base,seed=seed))),actual_support_offers=1,
            compatibility_audit={'exercised_design':True})
            for seed in config['phase5']['heldout_world_seeds'] for policy in ('fair_point','fair_robust')]

    def test_complete_frozen_primary_matrix_is_verified(self):
        from src.evaluation.phase5_experiments import verify_primary_design
        config,rows=self.primary_rows()
        self.assertEqual(verify_primary_design(rows,config)['paired_worlds'],30)

    def test_incomplete_wrong_or_unexercised_primary_cannot_verify(self):
        from src.evaluation.phase5_experiments import verify_primary_design
        config,rows=self.primary_rows()
        cases=[rows[:-1],[*rows,rows[0]]]
        for change in (dict(setting='exploratory'),dict(information='structured_observable'),
                       dict(population_seed=999),dict(configuration_identity='wrong'),dict(actual_support_offers=0)):
            cases.append([{**rows[0],**change},*rows[1:]])
        for changed in cases:
            with self.subTest(changed=changed[0]):
                with self.assertRaises(ValueError):
                    verify_primary_design(changed,config)

    def test_frozen_seed_partitions_and_sample_size(self):
        config=load_configuration()
        self.assertEqual(len(config['phase5']['heldout_world_seeds']),30)
        self.assertEqual(config['delivery']['horizon_weeks'],12)
        self.assertEqual(config['delivery']['num_students'],48)
        self.assertEqual(config['delivery']['fairness_grouping_attribute'],'sex_source')
        self.assertEqual(config['phase5']['heldout_world_seeds'][0],2000)

    def test_unexercised_v1_population_is_rejected_before_allocation(self):
        c,p=make_controller(DeliveryConfig(),'test',55000,'fair_point',information='group_dependent')
        audit=compatibility_audit(c.prepare_decision_snapshot(),c.environment.config)
        self.assertEqual(audit['feasible_students'],0)
        self.assertFalse(audit['exercised_design'])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'unexercised population'):
                run_cell(c.environment.config,[2000],'test',55000,('fair_point',),'group_dependent',
                    Path(temp)/'never_publish','test protocol',require_nonvacuous=True)
            self.assertFalse((Path(temp)/'never_publish').exists())

    def test_amended_population_exercises_both_supported_audit_groups(self):
        config=DeliveryConfig(**load_configuration()['delivery'])
        c,p=make_controller(config,'validation',44000,'fair_point',information='group_dependent')
        audit=compatibility_audit(c.prepare_decision_snapshot(),config)
        self.assertTrue(audit['exercised_design'])
        self.assertEqual(set(audit['feasible_students_by_audited_group']),{'F','M'})
        self.assertTrue(audit['shared_need_strata'])

    def test_zero_offer_reports_cannot_claim_exercised_comparison(self):
        rows=[dict(seed=seed,policy=policy,retention_rate=.8,worst_group_retention=.7,
            normalized_shortfall=0.,offer_rate=0.,completion_rate=0.,cost=0.,access_gap=None,
            solver_failures=0,incomplete_stages=0,extraction_failures=0,actual_support_offers=0,
            compatibility_audit={'exercised_design':False})
            for seed in (1,2) for policy in ('fair_point','fair_robust')]
        self.assertEqual(paired_report(rows)['exercise_status'],'not_fully_exercised')

    def test_paired_episodes_not_students(self):
        rows=[dict(seed=seed,policy=policy,retention_rate=retention,worst_group_retention=retention,
            normalized_shortfall=0.,offer_rate=.5,completion_rate=.25,cost=10.,access_gap=None,
            solver_failures=0,incomplete_stages=0,extraction_failures=0)
            for seed in (1,2,3) for policy,retention in (('fair_point',.5),('fair_robust',.6))]
        report=paired_report(rows)
        self.assertEqual(report['outcomes']['retention_rate']['n'],3)
        self.assertAlmostEqual(report['outcomes']['retention_rate']['mean_difference_pp'],10.)
        self.assertEqual(report['outcomes']['access_gap']['status'],'unavailable_in_some_worlds')

    def test_four_scorecards_remain_separate(self):
        c,p=make_controller(DeliveryConfig(num_students=6,horizon_weeks=6,sessions_required=2),
            'validation',100,'fair_point',information='group_dependent')
        c.run_episode()
        cards=four_scorecards(c,p)
        self.assertEqual(set(cards),{'extraction','estimation_prediction','allocation','simulated_effectiveness'})
        self.assertEqual(cards['simulated_effectiveness']['n'],6)
        self.assertEqual(cards['simulated_effectiveness']['reentry_events'],0)
        self.assertEqual(cards['allocation']['overbooking_checks'],'passed_independent_event_reconstruction')


if __name__=='__main__':
    unittest.main()

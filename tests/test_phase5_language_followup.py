"""Explicit mock inference regressions; these are not real-model accuracy evidence."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.evaluation.phase5_language_followup import (build_followup_corpus,evaluate_followup,
    validate_corpus,verify_language_report,note_from_case,run_language_followup)
from src.evaluation.phase5_language_decisions import (boundary_comparison,boundary_controller,
    replay_boundary,FollowupInformationController)
from src.intervention.followup_extractor import (PromptedFollowupExtractor,
    LegacyDeterministicExtractor)
from src.school.followup_notes import FollowupWeeklyNote
from src.intervention.observation_extractor import gold_payload,validate_extraction,validate_batch
from src.intervention.ollama_client import OllamaClient
from src.school.delivery_config import DeliveryConfig
from src.school.delivery_policy import WeeklyDeliveryPolicy
from src.school.phase5_delivery import population_environment,save_phase5_episode,replay_phase5_episode


class MockInferenceClient:
    """Software-only mock over development rules; never counted as real inference."""
    execution_configuration=dict(model='mock',temperature=0,timeout_seconds=1)
    def __init__(self,outputs=None):
        self.outputs=list(outputs) if outputs is not None else None
    def generate(self,messages,schema):
        if self.outputs is not None:
            result=self.outputs.pop(0)
            if isinstance(result,Exception):
                raise result
            return result
        values=json.loads(messages[-1]['content'])
        note=FollowupWeeklyNote(values['note_id'],values['student_id'],values['source_week'],
            values['available_week'],values['text'],('mock-source',))
        return gold_payload(note)


def mock_extractor(outputs=None,retries=0):
    return PromptedFollowupExtractor(MockInferenceClient(outputs),retries=retries,inference_kind='mock_software_regression')


class FollowupLanguageTests(unittest.TestCase):
    def setUp(self):
        self.case=build_followup_corpus()[0];self.note=note_from_case(self.case)

    def test_successful_prompted_extraction_is_explicitly_mocked(self):
        extractor=mock_extractor();batch=extractor.extract(self.note,1)
        self.assertEqual(batch.facts[0].value,'regular')
        self.assertEqual(extractor.calls,1);self.assertEqual(extractor.responses,1)
        self.assertEqual(extractor.audit_records[-1]['configuration']['inference_kind'],'mock_software_regression')
        self.assertIn('latency_seconds',extractor.audit_records[-1]['attempts'][0])
        self.assertFalse(LegacyDeterministicExtractor().extract(self.note,1).facts)

    def test_invalid_schema_and_privileged_fields_are_quarantined(self):
        for payload in ({},dict(dropout_probability=.2),self.case['gold']|dict(eligibility=True)):
            extractor=mock_extractor([payload])
            with self.assertRaisesRegex(ValueError,'quarantined'):
                extractor.extract(self.note,1)
            self.assertEqual(extractor.responses,1)
            self.assertEqual(extractor.audit_records[-1]['status'],'quarantined')
            self.assertEqual(extractor.audit_records[-1]['attempts'][0]['raw_output'],payload)

    def test_unsupported_claim_and_incorrect_span_rejected(self):
        for change in (dict(value='low'),dict(end_offset=len(self.note.text)-1),dict(source_month=1)):
            payload=deepcopy(self.case['gold']);payload['observations'][0].update(change)
            with self.assertRaisesRegex(ValueError,'quarantined'):
                mock_extractor([payload]).extract(self.note,1)

    def test_identity_and_future_timing_rejected(self):
        payload=deepcopy(self.case['gold']);payload['student_id']='someone_else'
        with self.assertRaisesRegex(ValueError,'identity'):
            mock_extractor([payload]).extract(self.note,1)
        extractor=mock_extractor()
        for note,cutoff in ((replace(self.note,available_week=3),1),(self.note,0)):
            with self.assertRaisesRegex(ValueError,'not available'):
                extractor.extract(note,cutoff)
        self.assertEqual(extractor.calls,0)

    def test_retry_audit_counts_every_request_without_fallback(self):
        extractor=mock_extractor([RuntimeError('unavailable'),self.case['gold']],retries=1)
        self.assertTrue(extractor.extract(self.note,1).facts)
        self.assertEqual((extractor.calls,extractor.responses),(2,1))
        self.assertEqual([r['status'] for r in extractor.audit_records[-1]['attempts']],['backend_failure','accepted'])
        extractor=mock_extractor([{},{}],retries=1)
        with self.assertRaises(ValueError):
            extractor.extract(self.note,1)
        self.assertEqual(extractor.calls,2)

    def test_unavailable_backend_has_no_accuracy_or_fake_success(self):
        extractor=mock_extractor([RuntimeError('Ollama HTTP 404')])
        report=evaluate_followup([self.case],extractor)
        self.assertEqual(report['llm']['status'],'unexecuted_model_unavailable')
        self.assertEqual(report['llm']['model_responses'],0)
        self.assertIsNone(report['splits']['development']['methods']['prompted_llm']['metrics'])
        self.assertEqual(report['splits']['development']['methods']['prompted_llm']['records'][0]['status'],'quarantined')

    def test_zero_attempts_and_not_requested_are_distinct(self):
        self.assertEqual(evaluate_followup([],mock_extractor())['llm']['status'],'unexecuted_zero_attempts')
        self.assertEqual(evaluate_followup([self.case])['llm']['status'],'unexecuted_not_requested')
        extractor=mock_extractor();extractor.extract(self.note,1)
        self.assertEqual(evaluate_followup([],extractor)['llm']['status'],'unexecuted_zero_attempts')

    def test_each_split_requires_its_own_model_response_for_accuracy(self):
        validation=next(c for c in build_followup_corpus() if c['split']=='validation')
        report=evaluate_followup([self.case,validation],mock_extractor([self.case['gold'],RuntimeError('unavailable')]))
        self.assertIsNotNone(report['splits']['development']['methods']['prompted_llm']['metrics'])
        self.assertIsNone(report['splits']['validation']['methods']['prompted_llm']['metrics'])
        self.assertEqual(report['splits']['validation']['methods']['prompted_llm']['inference']['status'],'unexecuted_model_unavailable')

    def test_mock_cannot_claim_to_be_real_inference(self):
        with self.assertRaisesRegex(ValueError,'mocks must be labelled'):
            PromptedFollowupExtractor(MockInferenceClient())

    def test_actual_client_invalid_json_response_is_recorded(self):
        from io import BytesIO
        client=OllamaClient(model='mocked-http-response')
        raw={'message':{'content':'{invalid json'},'done_reason':'stop'}
        with patch('src.intervention.ollama_client.urlopen',return_value=BytesIO(json.dumps(raw).encode())):
            with self.assertRaises(ValueError):
                client.generate([], {})
        self.assertTrue(client.response_received);self.assertEqual(client.last_raw_output,'{invalid json')

    def test_unknown_and_conflict_are_not_precise_condition_updates(self):
        cases=build_followup_corpus()
        for category,status in (('unknown','insufficient_evidence'),('conflict','conflicting')):
            case=next(c for c in cases if c['split']=='development' and c['category']==category)
            batch=mock_extractor().extract(note_from_case(case),1)
            self.assertEqual(batch.facts[0].assertion_status,status)
            self.assertEqual(batch.facts[0].value,'unknown')
        c=boundary_controller('prompted_llm',mock_extractor());c.run_week()
        target=next(n for n in c.notes if n.observation_contract and n.student_id=='fictional-00')
        text='The mentor reports participation is regular. The mentor reports participation is low. Accounts of participation conflict and are not reconciled.'
        c.notes=[replace(n,text=text) if n.note_id==target.note_id else n for n in c.notes]
        state=c.prepare_decision_snapshot()
        self.assertTrue(dict(state.students[0].estimate.uncertainty)['condition_conflict'])
        self.assertFalse(c.policy.plan(state).cancel_programme_ids)

    def test_external_annotation_contract_and_partition_leakage(self):
        cases=build_followup_corpus();validate_corpus(cases)
        self.assertTrue(all(c['annotation']['reviewer_status']=='unreviewed_synthetic' for c in cases))
        bad=deepcopy(cases);bad[-1]['paraphrase_group']=bad[0]['paraphrase_group']
        with self.assertRaisesRegex(ValueError,'leakage'):
            validate_corpus(bad)
        bad=deepcopy(cases);bad[0]['annotation']['reviewer_status']='reviewed_external'
        with self.assertRaisesRegex(ValueError,'reviewer identity'):
            validate_corpus(bad)
        bad=deepcopy(cases);bad[0]['annotation']['exact_evidence_spans']=[]
        with self.assertRaisesRegex(ValueError,'evidence span'):
            validate_corpus(bad)

    def test_gold_annotations_do_not_expand_entailment_rules(self):
        case=next(c for c in build_followup_corpus() if c['category']=='difficulty' and c['split']=='test')
        # This meaningful but unsupported sentence remains a miss under v2 rules.
        with self.assertRaisesRegex(ValueError,'unsupported assertion'):
            validate_extraction(case['gold'],note_from_case(case),1)
        report=evaluate_followup([case],mock_extractor())
        self.assertEqual(report['splits']['test']['methods']['prompted_llm']['metrics']['micro']['recall'],0)

    def test_recorded_benchmark_replays_without_model_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            extractor=mock_extractor();report=run_language_followup(temp,extractor)
            calls=extractor.calls
            cases=json.loads((Path(temp)/'frozen_corpus.json').read_text())
            saved=json.loads((Path(temp)/'extraction_report.json').read_text())
            self.assertEqual(verify_language_report(cases,saved)['live_requests'],0)
            self.assertEqual(extractor.calls,calls)
            self.assertEqual(report['independent_human_validation'],'incomplete')
            self.assertEqual(report['llm']['status'],'executed_mock_software_regression')

    def test_supported_mock_extracted_fact_changes_future_feasible_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            report=boundary_comparison(temp,mock_extractor)
            gold=report['arms']['note_content_gold'];llm=report['arms']['prompted_llm']
            self.assertEqual(gold['snapshot']['cancellations'],llm['snapshot']['cancellations'])
            self.assertTrue(report['comparisons']['existing_deterministic']['continuation_cancellation_changed'])
            self.assertTrue(report['comparisons']['existing_deterministic']['later_allocation_changed'])
            self.assertFalse(report['comparisons']['prompted_llm']['decision_difference_is_improvement'])
            self.assertEqual(llm['inference']['status'],'executed_mock_software_regression')
            self.assertEqual(replay_boundary(Path(temp)/'prompted_llm')['status'],'exact_replay_verified')

    def test_backend_failure_cannot_change_matched_pre_note_prefix(self):
        control=boundary_controller('existing_deterministic')
        model=boundary_controller('prompted_llm',mock_extractor([RuntimeError('unavailable')]))
        control.run_week();model.run_week()
        self.assertEqual(control.snapshots[0],model.snapshots[0])
        self.assertEqual(control.decisions[0],model.decisions[0])
        self.assertEqual(model.extractor.calls,0)
        model.run_week()
        self.assertEqual(model.extractor.calls,1)
        self.assertEqual(model.extractor.responses,0)
        focal=[a for a in model.attempts if a['note_type']=='mentor' and a['student_id']=='fictional-00']
        self.assertEqual(focal[0]['status'],'quarantined')

    def test_source_closed_loop_uses_own_notes_and_exact_recorded_replay(self):
        cfg=DeliveryConfig(num_students=12,horizon_weeks=6,sessions_required=5)
        for arm in ('note_content_gold','existing_deterministic','missing_notes','prompted_llm'):
            env,pop=population_environment(cfg,population_mode='source_held_out',split='test',population_seed=55000)
            c=FollowupInformationController(env,WeeklyDeliveryPolicy(cfg,'point'),language_condition=arm,
                extractor=mock_extractor() if arm=='prompted_llm' else None).run_episode()
            c.validate()
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'episode';save_phase5_episode(c,pop,path,protocol_text='language v2 software test')
                self.assertEqual(replay_phase5_episode(path)['status'],'exact_replay_verified')


if __name__=='__main__':
    unittest.main()

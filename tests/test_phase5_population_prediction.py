"""Scientific invariants for source sampling and separate event-risk inference."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from src.school.population_sampling import (load_source_pool, sample_population,
    population_validation, PopulationGeneratorConfig)
from src.school.delivery_config import DeliveryConfig
from src.school.delivery_contracts import DeliveryAction, SupportOffer
from src.school.delivery_policy import WeeklyDeliveryPolicy
from src.school.phase5_delivery import (population_environment, PredictionController,
    save_phase5_episode,replay_phase5_episode,TrainedRiskPriorityPolicy)
from src.school.delivery_experiments import synthetic_environment,normalized,episode_payload
from src.school.trained_withdrawal_risk import (decision_features,fit_model,
    TrainedWithdrawalRiskModel,NUMERIC,REFERENCE)
from src.evaluation.phase5_prediction_evaluation import (generate_reference_labels,
    analytical_event_probability,withdrawal_event,evaluate_predictor)
from src.school.student_condition import StudentCondition as C
from src.school.transition_model import keyed_uniform


def controller(split='train',population_seed=10,world_seed=1,**kwargs):
    config=DeliveryConfig(num_students=12,horizon_weeks=6,sessions_required=2,seed=world_seed,**kwargs)
    env,p=population_environment(config,population_mode='source_held_out',split=split,population_seed=population_seed)
    return PredictionController(env,WeeklyDeliveryPolicy(config,'random')),p


class PopulationTests(unittest.TestCase):
    def test_partition_and_manifest_isolation(self):
        pool=load_source_pool()
        self.assertEqual(len(pool.rows),674)
        groups=[{r['linkage_group_id'] for r in pool.partition(s)} for s in ('train','validation','test')]
        self.assertFalse(groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])

    def test_reproducible_and_distinct_cohorts(self):
        a=sample_population('train',20,9)
        self.assertEqual(a,sample_population('train',20,9))
        self.assertNotEqual(a,sample_population('train',20,10))

    def test_replacement_is_explicit(self):
        p=sample_population('test',500,9)
        self.assertTrue(p.with_replacement)
        self.assertLess(len({l.source_anchor for l in p.lineage}),len(p.lineage))
        self.assertEqual(population_validation(p)['impossible_combinations'],0)

    def test_context_and_missingness_inheritance(self):
        p=sample_population('train',470,9)
        report=population_validation(p)
        self.assertGreater(report['missingness']['math_grade1_0_20']['sampled'],0)
        for row,student in zip(p.profiles,p.students()):
            row=dict(row)
            self.assertIsNone(student.financial_need_verified)
            self.assertEqual(row['observed_school_dropout'],'')
            self.assertEqual(student.math_grade1_0_20,None if not row['math_grade1_0_20'] else int(row['math_grade1_0_20']))

    def test_population_rng_cannot_advance_transition_stream(self):
        before=keyed_uniform(19,'agent-00000',2,'weekly_environment_transition/v1')
        sample_population('train',20,777)
        self.assertEqual(before,keyed_uniform(19,'agent-00000',2,'weekly_environment_transition/v1'))

    def test_lineage_not_in_public_inputs_or_student_schema(self):
        c,p=controller()
        state=c.prepare_decision_snapshot()
        public=json.dumps(asdict(state))
        self.assertFalse(any(l.source_anchor in public or l.linkage_group in public for l in p.lineage))
        for key in ('source_anchor','linkage_group','population_seed','observed_school_dropout'):
            self.assertNotIn(key,asdict(p.students()[0]))

    def test_missing_required_context_is_rejected_without_imputation(self):
        pool=load_source_pool()
        row=dict(pool.rows[0]); row['age_years']=''
        from src.school.population_sampling import validate_source_row
        with self.assertRaisesRegex(ValueError,'missing required'):
            validate_source_row(row)

    def test_forged_group_split_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            import csv
            pool=load_source_pool(); rows=[dict(r) for r in pool.rows]
            rows[1]['linkage_group_id']=rows[0]['linkage_group_id']
            rows[1]['split']='test' if rows[0]['split']!='test' else 'train'
            for name,columns in (('source.csv',list(rows[0])),('splits.csv',['student_id','linkage_group_id','split','anchor_subject'])):
                with (Path(temp)/name).open('w') as stream:
                    writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore'); writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'crosses splits'):
                load_source_pool(Path(temp)/'source.csv',Path(temp)/'splits.csv')

    def test_legacy_fixture_adapter_is_identical(self):
        config=DeliveryConfig()
        a,p=population_environment(config)
        b=synthetic_environment(config)
        self.assertIsNone(p)
        ca=PredictionController(a,WeeklyDeliveryPolicy(config,'wait')).run_episode()
        cb=PredictionController(b,WeeklyDeliveryPolicy(config,'wait')).run_episode()
        self.assertEqual(normalized(episode_payload(ca)),normalized(episode_payload(cb)))

    def test_test_episode_exact_population_replay(self):
        c,p=controller('test',77,900)
        c.run_episode()
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'episode'
            save_phase5_episode(c,p,output,protocol_text='test protocol')
            self.assertEqual(replay_phase5_episode(output)['status'],'exact_replay_verified')
            with self.assertRaises(FileExistsError):
                save_phase5_episode(c,p,output,protocol_text='test protocol')


class RiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train=[];cls.validation=[]
        for split,seeds,target in (('train',range(10,14),cls.train),('validation',range(30,34),cls.validation)):
            for seed in seeds:
                c,p=controller(split,100+seed,seed)
                target.extend(generate_reference_labels(c,p))
        cls.model,cls.training_report=fit_model(cls.train,cls.validation,hyperparameters=(1.,))

    def features(self):
        return self.train[0].features

    def predict(self,f=None,**kwargs):
        f=self.features() if f is None else f
        return self.model.predict(f,expected_estimate_id=kwargs.pop('estimate',f.estimate_id),
            expected_model_version=kwargs.pop('model',self.model.version),**kwargs)

    def test_labels_are_offline_not_features(self):
        f=self.features()
        self.assertEqual(tuple(dict(f.numeric)),NUMERIC)
        for field in ('withdrawal_event','source_anchor','linkage_group','world_seed','branch_identity'):
            self.assertNotIn(field,asdict(f))
        with self.assertRaisesRegex(ValueError,'schema'):
            from src.school.trained_withdrawal_risk import _numeric
            _numeric(replace(f,numeric=(*f.numeric,('withdrawal_event',1.))))

    def test_test_data_cannot_fit_or_select(self):
        with self.assertRaisesRegex(ValueError,'test prohibited'):
            fit_model([replace(self.train[0],split='test')],self.validation)

    def test_world_and_source_group_leakage_rejected(self):
        for change in (dict(world_seed=self.train[0].world_seed),dict(linkage_group=self.train[0].linkage_group)):
            rows=[replace(self.validation[0],**change),*self.validation[1:]]
            with self.assertRaisesRegex(ValueError,'leakage'):
                fit_model(self.train,rows)

    def test_preprocessing_is_training_only(self):
        shifted=[replace(r,features=replace(r.features,support_type='validation_only_category')) for r in self.validation]
        other,_=fit_model(self.train,shifted,hyperparameters=(1.,))
        for name in ('medians','scales','minimum','maximum','categories','coefficients','intercept'):
            self.assertEqual(other.artifact[name],self.model.artifact[name])
        self.assertNotIn('validation_only_category',other.artifact['categories'])

    def test_stale_estimate_and_model_rejected(self):
        with self.assertRaisesRegex(ValueError,'stale'):
            self.predict(estimate='old')
        with self.assertRaisesRegex(ValueError,'version'):
            self.predict(model='old')

    def test_probability_replay_is_identical(self):
        p=self.predict()
        self.assertTrue(0<=p.probability<=1)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model.json';self.model.save(path)
            loaded=TrainedWithdrawalRiskModel.load(path)
            self.assertEqual(p,loaded.predict(self.features(),expected_estimate_id=self.features().estimate_id,
                                             expected_model_version=loaded.version))

    def test_unavailable_ood_and_missing(self):
        f=self.features()
        for change,reason in ((dict(enrolled=False),'not_currently_enrolled'),(dict(horizon=0),'terminal_cutoff_not_applicable'),
                              (dict(horizon=9),'unsupported_horizon'),(dict(regime_identity='wrong'),'reference_regime_mismatch')):
            p=self.predict(replace(f,**change))
            self.assertIsNone(p.probability);self.assertEqual(p.unavailable_reason,reason)
        self.assertTrue(self.predict(replace(f,support_type='never_seen')).ood_reasons)
        altered=replace(f,numeric=tuple((k,None if k=='source_age' else v) for k,v in f.numeric))
        self.assertIn('source_age',self.predict(altered).missing_features)
        with self.assertRaises(FileNotFoundError):
            TrainedWithdrawalRiskModel.load('/tmp/no-phase5-model-artifact.json')

    def test_nonfinite_input_abstains(self):
        f=self.features()
        f=replace(f,numeric=tuple((k,float('nan') if k=='entropy' else v) for k,v in f.numeric))
        # Fingerprints also reject nonfinite JSON, so malformed inputs fail closed.
        with self.assertRaises(ValueError):
            self.predict(f)

    def test_horizon_truncates_and_future_sources_rejected(self):
        c,p=controller()
        s=c.prepare_decision_snapshot().students[0]
        self.assertEqual(decision_features(s,cutoff_week=1,remaining_weeks=2,config=c.environment.config).horizon,2)
        with self.assertRaisesRegex(ValueError,'future'):
            decision_features(replace(s,estimate=replace(s.estimate,last_observation_week=1)),
                cutoff_week=1,remaining_weeks=6,config=c.environment.config)

    def test_hidden_truth_cannot_change_online_features(self):
        c,p=controller();state=c.prepare_decision_snapshot();s=state.students[0]
        before=decision_features(s,cutoff_week=state.week,remaining_weeks=state.weeks_remaining,config=c.environment.config)
        c.environment._conditions={sid:C.DISENGAGED for sid in c.environment._conditions}
        after=decision_features(s,cutoff_week=state.week,remaining_weeks=state.weeks_remaining,config=c.environment.config)
        self.assertEqual(before,after)

    def test_first_passage_handles_reentry(self):
        self.assertTrue(withdrawal_event([C.WITHDRAWN,C.STABLE]))
        c,p=controller()
        s=c.prepare_decision_snapshot().students[0]
        matrix=((0.,0.,0.,1.),)*3+((1.,0.,0.,0.),)
        # Production v1 explicitly disallows re-entry. Exercise first-passage
        # arithmetic with a minimal future-world stub, without weakening it.
        from types import SimpleNamespace
        config=SimpleNamespace(weekly_wait_matrix=matrix,treatment_matrix=matrix,
            attendance_probability=1.,delivery_probability=1.,cancellation_probability=0.)
        self.assertAlmostEqual(analytical_event_probability(s,config,2),1.)

    def test_hand_computable_reference_labels(self):
        immediate=((0.,0.,0.,1.),)*4
        c,p=controller(weekly_wait_matrix=immediate,weekly_tutoring_matrix=immediate)
        labels=generate_reference_labels(c,p)
        self.assertEqual(len(labels),12)
        self.assertTrue(all(r.withdrawal_event for r in labels))
        self.assertTrue(all(r.analytical_target_matched==1. for r in labels))

    def test_reference_obligation_changes_labels_without_new_offers(self):
        identity=tuple(tuple(float(i==j) for j in range(4)) for i in range(4))
        immediate=((0.,0.,0.,1.),)*4
        c,p=controller(acceptance_probability=1.,attendance_probability=1.,delivery_probability=1.,cancellation_probability=0.,
            weekly_wait_matrix=immediate,weekly_tutoring_matrix=identity)
        c.run_week()
        labels=generate_reference_labels(c,p,horizon=1,landmark_weeks=(2,))
        self.assertTrue(labels)
        self.assertTrue(all(dict(r.features.numeric)['active_programme'] for r in labels))
        self.assertTrue(all(not r.withdrawal_event for r in labels))
        self.assertTrue(all(r.analytical_target_matched==0. for r in labels))

    def test_reference_continues_existing_commitments_and_preserves_factual_world(self):
        identity=tuple(tuple(float(i==j) for j in range(4)) for i in range(4))
        c,p=controller(acceptance_probability=1.,attendance_probability=1.,delivery_probability=1.,cancellation_probability=0.,
            weekly_wait_matrix=identity,weekly_tutoring_matrix=identity)
        c.run_week()
        labels=generate_reference_labels(c,p,landmark_weeks=(2,))
        self.assertTrue(labels)
        self.assertTrue(all(not r.withdrawal_event for r in labels))
        self.assertTrue(any(dict(r.features.numeric)['active_programme'] for r in labels))
        self.assertTrue(any(e.kind=='session_delivered' and e.source_week==2 for e in c.environment.events))

    def test_heldout_outcome_metrics_use_actual_events(self):
        c,p=controller('test',501,501)
        labels=generate_reference_labels(c,p)
        report=evaluate_predictor(self.model,labels,self.training_report['constant_by_horizon'])
        self.assertEqual(report['landmark_counts'],len(labels))
        self.assertEqual(report['pooled_descriptive']['trained']['events'],sum(r.withdrawal_event for r in labels))

    def test_trained_priority_and_predictions_replay(self):
        c,p=controller('test',510,510)
        c=PredictionController(c.environment,TrainedRiskPriorityPolicy(c.environment.config,self.model),trained_model=self.model).run_episode()
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'episode'
            save_phase5_episode(c,p,output,protocol_text='risk baseline test')
            self.assertEqual(replay_phase5_episode(output)['status'],'exact_replay_verified')


if __name__=='__main__':
    unittest.main()

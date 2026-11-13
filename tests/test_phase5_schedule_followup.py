"""Schedule information, supported laws and split-isolated model selection."""
from dataclasses import asdict,replace
import json
from pathlib import Path
import tempfile
import unittest

from src.evaluation.provenance import digest
from src.evaluation.phase5_prediction_evaluation import generate_reference_labels,evaluate_predictor
from src.school.delivery_config import DeliveryConfig
from src.school.delivery_contracts import Programme,ScheduledSession
from src.school.delivery_policy import WeeklyDeliveryPolicy
from src.school.phase5_delivery import (PredictionController,population_environment,save_phase5_episode,
    replay_phase5_episode,TrainedRiskPriorityPolicy)
from src.school.trained_withdrawal_risk import (decision_features,fit_model,TrainedWithdrawalRiskModel,
    FEATURE_SCHEMA,NUMERIC,regime_fingerprint)
from src.school.population_sampling import population_validation


def source_controller(split,seed,*,cadence=1):
    cfg=DeliveryConfig(num_students=16,horizon_weeks=8,sessions_required=5,session_cadence_weeks=cadence,seed=seed)
    env,pop=population_environment(cfg,population_mode='source_held_out',split=split,population_seed=1000+seed)
    return PredictionController(env,WeeklyDeliveryPolicy(cfg,'random')),pop


class ScheduleModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train=[];cls.validation=[]
        for split,seeds,rows in (('train',range(50,54),cls.train),('validation',range(70,74),cls.validation)):
            for seed in seeds:
                c,pop=source_controller(split,seed);rows.extend(generate_reference_labels(c,pop))
        cls.model,cls.selection=fit_model(cls.train,cls.validation,hyperparameters=(1.,))

    def predict(self,features):
        return self.model.predict(features,expected_estimate_id=features.estimate_id,expected_model_version=self.model.version)

    def test_identical_counts_different_future_timing_are_distinguishable(self):
        c,_=source_controller('train',50,cadence=2);s=c.prepare_decision_snapshot().students[0]
        s=replace(s,estimate=replace(s.estimate,as_of_week=3),waiting_weeks=0)
        def feature(start):
            sessions=tuple(ScheduledSession(str(i),w,'DELIVERED' if i==0 else 'RESERVED')
                for i,w in enumerate(c.environment.config.schedule(start)))
            p=Programme('p',s.student_id,'mentor',start,1,'ACTIVE',sessions)
            return decision_features(replace(s,programmes=(p,)),cutoff_week=3,remaining_weeks=8,config=c.environment.config)
        a,b=feature(1),feature(2)
        self.assertEqual(dict(a.numeric)['reserved_sessions'],dict(b.numeric)['reserved_sessions'])
        self.assertEqual(dict(a.numeric)['delivered_sessions'],dict(b.numeric)['delivered_sessions'])
        self.assertNotEqual(a.numeric,b.numeric)
        self.assertEqual([dict(a.numeric)[f'scheduled_session_week_{i}'] for i in range(4)],[1,0,1,0])
        self.assertEqual([dict(b.numeric)[f'scheduled_session_week_{i}'] for i in range(4)],[0,1,0,1])
        self.assertFalse(a.schedule_issues or b.schedule_issues)

    def test_future_realization_is_rejected_not_encoded(self):
        c,_=source_controller('train',50);c.run_week();state=c.prepare_decision_snapshot()
        s=next(s for s in state.students if any(p.status=='ACTIVE' for p in s.programmes))
        p=next(p for p in s.programmes if p.status=='ACTIVE')
        self.assertTrue(any(w>=state.week and status=='RESERVED' for w,status in [(a.week,a.status) for a in p.sessions]))
        p=replace(p,sessions=tuple(replace(a,status='DELIVERED') if a.week>=state.week else a for a in p.sessions))
        with self.assertRaisesRegex(ValueError,'future session realization'):
            decision_features(replace(s,programmes=(p,)),cutoff_week=state.week,remaining_weeks=state.weeks_remaining,config=c.environment.config)

    def test_duration_and_cadence_change_reference_identity_and_abstain(self):
        c,_=source_controller('train',50);state=c.prepare_decision_snapshot();s=state.students[0]
        for cfg in (replace(c.environment.config,sessions_required=2),replace(c.environment.config,session_cadence_weeks=2)):
            f=decision_features(s,cutoff_week=1,remaining_weeks=8,config=cfg)
            p=self.predict(f);self.assertIsNone(p.probability)
            self.assertEqual(p.unavailable_reason,'reference_regime_mismatch')
            with self.assertRaisesRegex(ValueError,'incompatible'):
                TrainedRiskPriorityPolicy(cfg,self.model)

    def test_non_cadenced_schedule_is_unavailable(self):
        c,_=source_controller('train',50);c.run_week();state=c.prepare_decision_snapshot()
        s=next(s for s in state.students if any(p.status=='ACTIVE' for p in s.programmes));p=s.programmes[0]
        p=replace(p,sessions=(*p.sessions[:-1],replace(p.sessions[-1],week=8)))
        f=decision_features(replace(s,programmes=(p,)),cutoff_week=2,remaining_weeks=7,config=c.environment.config)
        self.assertIn('unsupported_programme_schedule',f.schedule_issues)
        self.assertEqual(self.predict(f).unavailable_reason,'unsupported_programme_schedule')

    def test_schema_model_version_and_old_artifact_rejected(self):
        f=self.train[0].features
        self.assertEqual(self.predict(replace(f,schema='authorized_weekly_features/v1')).unavailable_reason,'invalid_features')
        with self.assertRaisesRegex(ValueError,'version'):
            self.model.predict(f,expected_estimate_id=f.estimate_id,expected_model_version='different')
        artifact={k:v for k,v in self.model.artifact.items() if k!='model_version'}
        artifact.update(contract='trained_withdrawal_model/v1',schema='authorized_weekly_features/v1')
        with self.assertRaisesRegex(ValueError,'version/hash'):
            TrainedWithdrawalRiskModel(artifact | dict(model_version=digest(artifact)))

    def test_training_only_preprocessing_and_coefficients(self):
        rows=[replace(r,features=replace(r.features,numeric=tuple((k,1e6 if k=='source_age' else v) for k,v in r.features.numeric)))
              for r in self.validation]
        model,_=fit_model(self.train,rows,hyperparameters=(1.,))
        for key in ('medians','scales','minimum','maximum','coefficients','categories','training_schedule_patterns'):
            self.assertEqual(model.artifact[key],self.model.artifact[key])

    def test_calibration_and_selection_worlds_are_validation_only(self):
        p=self.selection['provenance']
        self.assertFalse(set(p['calibration_worlds'])&set(p['selection_worlds']))
        self.assertEqual(set(p['calibration_worlds']+p['selection_worlds']),set(p['validation_worlds']))
        self.assertFalse(set(p['training_worlds'])&set(p['validation_worlds']))
        self.assertFalse(set(p['training_groups'])&set(p['validation_groups']))

    def test_test_labels_cannot_enter_calibration_or_selection(self):
        for train,validation in (([replace(self.train[0],split='test')],self.validation),
                                  (self.train,[replace(self.validation[0],split='test')])):
            with self.assertRaisesRegex(ValueError,'test prohibited'):
                fit_model(train,validation)
        c,pop=source_controller('test',90);rows=generate_reference_labels(c,pop)
        before=json.dumps(self.model.artifact,sort_keys=True)
        evaluate_predictor(self.model,rows,self.selection['constant_by_horizon'])
        self.assertEqual(before,json.dumps(self.model.artifact,sort_keys=True))

    def test_missing_features_and_unseen_schedule_are_reported(self):
        f=self.train[0].features
        f=replace(f,numeric=tuple((k,None if k=='source_age' else v) for k,v in f.numeric),support_type='unseen')
        prediction=self.predict(f)
        self.assertIn('source_age',prediction.missing_features)
        self.assertIn('unknown_category:support_type',prediction.ood_reasons)
        f=replace(f,numeric=tuple((k,1. if k in ('active_programme','scheduled_session_week_0','scheduled_session_week_3')
            else 0. if k.startswith('scheduled_session_week_') else v) for k,v in f.numeric))
        self.assertEqual(self.predict(f).unavailable_reason,'unsupported_schedule_pattern')

    def test_lineage_and_truth_do_not_cross_feature_boundary(self):
        c,pop=source_controller('test',90);state=c.prepare_decision_snapshot();s=state.students[0]
        before=decision_features(s,cutoff_week=1,remaining_weeks=8,config=c.environment.config)
        c.environment._conditions.clear();c.environment.exogenous_draws.append(dict(future='private'))
        self.assertEqual(before,decision_features(s,cutoff_week=1,remaining_weeks=8,config=c.environment.config))
        text=json.dumps(asdict(before))
        for key in ('source_anchor','linkage_group','true_condition','world_seed','withdrawal_event','counterfactual'):
            self.assertNotIn(key,text)
        with self.assertRaisesRegex(ValueError,'one-to-one'):
            population_validation(replace(pop,lineage=pop.lineage[:-1]))

    def test_exact_model_prediction_and_episode_replay(self):
        c,pop=source_controller('test',90)
        c=PredictionController(c.environment,TrainedRiskPriorityPolicy(c.environment.config,self.model),trained_model=self.model).run_episode()
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'episode';save_phase5_episode(c,pop,output,protocol_text='schedule v2 regression')
            self.assertEqual(replay_phase5_episode(output)['status'],'exact_replay_verified')
            self.model.save(Path(temp)/'model.json')
            model=TrainedWithdrawalRiskModel.load(Path(temp)/'model.json')
            f=self.train[0].features
            self.assertEqual(self.predict(f),model.predict(f,expected_estimate_id=f.estimate_id,expected_model_version=model.version))

    def test_reference_law_material_behaviors_are_fingerprinted(self):
        cfg=DeliveryConfig()
        for change in (dict(sessions_required=2),dict(session_cadence_weeks=2),dict(cancellation_probability=.5),
                       dict(delivery_probability=.5),dict(attendance_probability=.5),dict(acceptance_probability=.5),
                       dict(terminate_on_withdrawal=False),dict(effect_strength=0)):
            self.assertNotEqual(regime_fingerprint(cfg),regime_fingerprint(replace(cfg,**change)))
        self.assertEqual(regime_fingerprint(cfg),regime_fingerprint(replace(cfg,budget=100,num_students=100)))


if __name__=='__main__':
    unittest.main()

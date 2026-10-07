"""Generated data: consistency, lineage, nulls and consumer boundaries."""
from dataclasses import FrozenInstanceError, replace
import unittest

from src.data.contracts import *
from src.data.access import authorized_measurement


def estimate():
    return EstimatedStudentState('SYN00001','estimate-v1',1,
        (EstimateField('attendance',.6,.5,.7,1,False,'unknown',('obs1',),'fraction'),),
        UpdateProvenance(None,'updater-v1','conservative-v1',('obs1',),(),'No prediction applied','Measured attendance',()))


def risk():
    return RiskEstimate('SYN00001','estimate-v1',1,None,'unavailable',
        'any_simulated_withdrawal_while_currently_enrolled',4,
        'existing_commitments_no_new_scarce_offers','unfitted','uncalibrated','fixture-feature-hash',
        'not_fitted',False,None,None,None)


class Contracts(unittest.TestCase):
    def test_all_required_contracts_exported(self):
        names={'StudentContext','EnvironmentState','Observation','ExtractedObservationBatch',
            'EstimatedStudentState','RiskEstimate','DecisionInput','SupportOffer','Acceptance',
            'Delivery','Completion','Outcome','ResourceLedger','EpisodeRecord'}
        self.assertTrue(names<=json_schemas()['$defs'].keys())
        for definition in json_schemas()['$defs'].values():
            self.assertFalse(definition['additionalProperties'])
            self.assertEqual(set(definition['properties']),set(definition['required']))

    def test_valid_event_and_decision_roundtrip(self):
        amount=ResourceAmount(1,1,20,.2)
        offer=SupportOffer('offer1','SYN00001','tutor1','mentor1',0,0,amount)
        acceptance=Acceptance('accept1','SYN00001','tutor1','mentor1',0,0,amount,'offer1',True)
        delivery=Delivery('deliver1','SYN00001','tutor1','mentor1',1,1,amount,'accept1',1,True)
        completion=Completion('complete1','SYN00001','tutor1','mentor1',1,1,amount,'offer1',1,'completed')
        commitment=ResourceCommitment('commit1','SYN00001','tutor1','mentor1',1,4,'reserved',amount)
        ledger=ResourceLedger(1,'scenario_currency',ResourceAmount(10,10,200,2),amount,(commitment,),(),ResourceAmount(0,0,0,0))
        student=DecisionStudent('SYN00001',estimate(),risk(),(offer,acceptance,delivery,completion),0,'eligible',('obs1',))
        decision=DecisionInput(VERSION,1,(student,),ledger)
        self.assertEqual(DecisionInput.from_dict(decision.to_dict()),decision)
        with self.assertRaises(FrozenInstanceError): decision.students[0].waiting_weeks=10
        with self.assertRaises(TypeError): decision.students[0]=student
        with self.assertRaises(ValueError): DecisionInput.from_dict({**decision.to_dict(),'hidden_hazard':.8})

    def test_stale_risk_and_identity_rejected(self):
        for changed in (replace(risk(),estimate_version='old'),replace(risk(),as_of_time=0),replace(risk(),student_id='OTHER')):
            with self.assertRaises(ValueError): DecisionStudent('SYN00001',estimate(),changed,(),0,'unknown',())

    def test_invalid_risk_target_probabilities_and_horizon(self):
        for kwargs in ({'predicted_simulated_withdrawal_risk':1.1,'status':'available'},
            {'predicted_simulated_withdrawal_risk':float('nan'),'status':'available'},
            {'predicted_simulated_withdrawal_risk':0,'status':'unavailable'},
            {'predicted_simulated_withdrawal_risk':.2,'status':'available','horizon_steps':0},
            {'lower':.1,'upper':.3}, {'target':'real_school_dropout'},
            {'reference_support_regime':'arbitrary_future_treatment'}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError,TypeError)): replace(risk(),**kwargs)

    def test_withdrawn_risk_not_zero(self):
        e=replace(estimate(),fields=(EstimateField('enrolled',False,None,None,1,False,'unknown',('e',),'boolean'),))
        with self.assertRaises(ValueError): DecisionStudent('SYN00001',e,risk(),(),0,'unknown',())
        DecisionStudent('SYN00001',e,replace(risk(),status='not_applicable'),(),0,'unknown',())

    def test_future_and_evaluator_events_forbidden(self):
        amount=ResourceAmount(0,0,0,0)
        future=SupportOffer('x','SYN00001','t','m',2,2,amount)
        outcome=Outcome('x','SYN00001','t','m',1,1,amount,'simulated_withdrawal',True,True)
        for event in (future,outcome):
            with self.assertRaises((ValueError,TypeError)): DecisionStudent('SYN00001',estimate(),risk(),(event,),0,'unknown',())

    def test_observation_range_types_units_and_forbidden_fields(self):
        o=authorized_measurement('s','attendance',.6,1,1,'attendance_register','obs1')
        for kwargs in ({'value':True},{'value':60},{'value':float('inf')},{'units':'percent'},
            {'field':'hidden_hazard'},{'field':'G3'},{'field':'predicted_risk'},{'source_time':2},
            {'status':'missing'},{'source_time':-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises((TypeError,ValueError)): replace(o,**kwargs)

    def test_evidence_linked_numeric_and_qualitative_batches(self):
        o=authorized_measurement('s','attendance',.6,1,2,'register','obs1')
        a=EvidenceAssertion('assert1',o,0,9,'3 of 5 ok','quantitative',None,3,5)
        batch=ExtractedObservationBatch('note1','s','3 of 5 ok',1,2,'structured-v1',(a,))
        self.assertEqual(ExtractedObservationBatch.from_dict(batch.to_dict()),batch)
        for kwargs in ({'note_text':'wrong text'},{'student_id':'other'},{'assertions':(a,a)}, {'available_at':0}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): replace(batch,**kwargs)
        qualitative=EvidenceAssertion('q',replace(o,value=None,status='unknown',missingness='not_measured'),0,9,'Improving','qualitative','improving',None,None)
        ExtractedObservationBatch('n','s','Improving',1,2,'template-v1',(qualitative,))
        with self.assertRaises(ValueError): replace(qualitative,observation=o)
        with self.assertRaises(ValueError): replace(a,numerator=4)

    def test_qualitative_pending_support_is_a_status_not_a_numeric_barrier(self):
        o=Observation('pending','s','support_status','pending',1,2,'reported','mentor_note','none','workflow_category')
        a=EvidenceAssertion('pending-assertion',o,0,7,'Pending','qualitative','unknown',None,None)
        batch=ExtractedObservationBatch('pending-note','s','Pending',1,2,'template-v1',(a,))
        self.assertEqual(batch.assertions[0].observation.value,'pending')
        with self.assertRaises(ValueError): replace(a,kind='quantitative')

    def test_unknowns_not_zero_and_no_extra_extractor_risk(self):
        with self.assertRaises(TypeError): UnknownFields(0,None,None,None,None)
        with self.assertRaises(ValueError): EstimatedStudentState.from_dict({**estimate().to_dict(),'predicted_risk':.4})
        with self.assertRaises(TypeError): replace(estimate(),fields=list(estimate().fields))

    def test_interval_and_future_freshness(self):
        with self.assertRaises(ValueError): replace(estimate().fields[0],lower=.9,upper=.8)
        with self.assertRaises(ValueError): replace(estimate(),as_of_time=0)



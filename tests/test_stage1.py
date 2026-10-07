"""Stage 1 gate: source fidelity, lineage, nulls, leakage and immutable contracts."""
import copy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.data.contracts import *
from src.data.access import (PolicyStore, ContextStore, EnvironmentStore, EvaluatorStore,
    reset_observations, model_features, authorized_measurement)
from src.data.ingestion import read_csv, sha, validate_and_adapt
from src.data.stage1 import PROJECT, preflight, load_tables, build, verify, INPUT_PATHS
from src.data.provenance import GENERATOR_ASSUMPTIONS


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


class DataGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=PROJECT/'configs/stage1_inputs.v1.json'
        _,cls.paths=preflight(PROJECT,cls.config)
        cls.tables=load_tables(cls.paths)
        cls.contexts,cls.fixtures,cls.states,cls.outcomes,cls.report=validate_and_adapt(cls.tables)
        cls.tmp=tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.tmp.cleanup)
        cls.output=Path(cls.tmp.name)/'v1'
        build(PROJECT,cls.config,cls.output)

    def test_source_and_lineage_counts(self):
        self.assertEqual(len(self.contexts),674); self.assertEqual(len(self.fixtures),2000)
        self.assertEqual(self.report['represented_fixture_anchors'],615)
        self.assertEqual(self.report['represented_fixture_groups'],604)
        self.assertEqual(self.report['primary_split_counts'],{'train':388,'validation':125,'test':136})
        self.assertEqual(len(EvaluatorStore(self.output).load_subject_references()),1044)

    def test_all_original_subject_cells_preserved(self):
        actual={r['record_id']:r for r in EvaluatorStore(self.output).load_subject_references()}
        for subject,prefix in [('raw_portuguese','POR'),('raw_math','MAT')]:
            for i,row in enumerate(self.tables[subject],1):
                self.assertEqual({k:actual[f'{prefix}{i:04d}'][k] for k in row},row)

    def test_math_only_outcomes_fixed_and_missing_enrichment_preserved(self):
        records={r['record_id']:r for r in self.tables['subject_records_reference']}
        outcomes={r['student_id']:r for r in self.outcomes}
        for c in self.contexts:
            row=outcomes[c.lineage.student_id]
            if c.lineage.anchor_subject=='math':
                original=records[c.lineage.student_id]
                self.assertEqual(int(row['math_final_grade_0_20']),int(original['G3']))
                self.assertEqual(int(row['math_grade2_0_20']),int(original['G2']))
                self.assertEqual(int(row['math_total_absences_count']),int(original['absences']))
            elif c.lineage.link_status!='one_to_one':
                self.assertIsNone(c.context.math_grade1_0_20)
                self.assertEqual(row['math_final_grade_0_20'],'')

    def test_unknowns_and_strict_category_types(self):
        for c in self.contexts+self.fixtures:
            self.assertTrue(all(v is None for v in c.unknown.to_dict().values()))
        for kwargs in ({'age_years':'18'},{'age_years':True},{'travel_time_category':5},
                       {'school_id':'OTHER'},{'mother_education_code':34},{'math_grade1_0_20':21}):
            with self.subTest(kwargs=kwargs),self.assertRaises((TypeError,ValueError)): replace(self.contexts[0].context,**kwargs)

    def test_corrupt_lineage_and_derived_fields_fail(self):
        for table,field,value in [('synthetic_student_population','split','test'),
            ('synthetic_student_population','mother_education_code','0'),
            ('student_dataset','disadvantage_proxy_count','3'),
            ('student_dataset','income_amount','0'),('subject_records_reference','G3','19'),
            ('student_dataset','linkage_group_id','0'*20)]:
            changed=copy.deepcopy(self.tables); changed[table][0][field]=value
            with self.subTest(table=table,field=field),self.assertRaises((TypeError,ValueError)): validate_and_adapt(changed)

    def test_duplicate_ids_and_raw_invalid_categories_fail(self):
        changed=copy.deepcopy(self.tables); changed['student_dataset'][1]['student_id']=changed['student_dataset'][0]['student_id']
        with self.assertRaises(ValueError): validate_and_adapt(changed)
        changed=copy.deepcopy(self.tables); changed['raw_math'][0]['traveltime']='0'
        with self.assertRaises(ValueError): validate_and_adapt(changed)

    def test_policy_store_does_not_open_other_roles(self):
        opened=[]; original=Path.open
        def tracked(p,*args,**kwargs):
            opened.append(p)
            if any(part in ('environment','evaluator','context') for part in p.parts):
                raise AssertionError('Forbidden consumer read')
            return original(p,*args,**kwargs)
        with patch.object(Path,'open',tracked):
            rows=PolicyStore(self.output).load_reset('test','fixture')
            self.assertEqual(len(rows),400)
        self.assertEqual(len(opened),1)
        for key in ('hidden_hazard','G2','G3','response_tendency','source_row','split','sex_source'):
            with self.subTest(key=key),self.assertRaises(AttributeError): getattr(rows[0],key)
        for name in ('load_historical_outcomes','load_fixture','load_static_fixture_diagnostics'):
            with self.assertRaises(AttributeError): getattr(PolicyStore(self.output),name)

    def test_metadata_and_math_never_become_score_features(self):
        record=reset_observations(self.contexts[0])
        for name in ('student_id','source_row','split','linkage_group_id','sex_source','math_grade1_0_20','G3','observed_school_dropout'):
            with self.subTest(name=name),self.assertRaises(ValueError): model_features(record,(name,))
            with self.assertRaises(ValueError): reset_observations(self.contexts[0],(name,))
        self.assertEqual(set(model_features(record)),{'anchor_grade1_0_20','past_failures_count','study_time_category'})
        with self.assertRaises(TypeError): model_features(record)['anchor_grade1_0_20']=20

    def test_hidden_mutation_cannot_change_observation_serialization(self):
        before=reset_observations(self.fixtures[0]).to_json()
        changed=replace(self.states[0],attendance=.5,engagement=.1,response_tendency=.01,financial_barrier=not self.states[0].financial_barrier)
        self.assertNotEqual(changed,self.states[0])
        self.assertEqual(before,reset_observations(self.fixtures[0]).to_json())
        # Stronger disk-level check: replace hidden/evaluator tables, hold policy facts fixed.
        isolated=Path(self.tmp.name)/'mutated'
        shutil.copytree(self.output,isolated)
        serialized=[r.to_json() for r in PolicyStore(isolated).load_reset('test')]
        for role in ('environment','evaluator'):
            for p in (isolated/'data'/role).glob('*.jsonl'): p.write_text('{"G3":0,"hidden_hazard":0.99,"future_outcome":true}\n')
        self.assertEqual(serialized,[r.to_json() for r in PolicyStore(isolated).load_reset('test')])

    def test_generated_state_withheld_until_observed(self):
        record=reset_observations(self.fixtures[0])
        dynamic=[o for o in record.observations if o.field in DYNAMIC_FIELDS]
        self.assertTrue(all(o.value is None and o.status=='withheld' for o in dynamic))
        observed=authorized_measurement(record.student_id,'attendance',.6,1,2,'dated_register','new-obs')
        self.assertEqual(observed.value,.6)
        with self.assertRaises(ValueError): PolicyReset(record.student_id,(replace(observed,available_at=0,source_time=0),))

    def test_policy_path_injection_and_symlink_rejected(self):
        for split,cohort in [('test','../evaluator'),('../../evaluator','primary'),('train','simulator_hidden_truth')]:
            with self.assertRaises(ValueError): PolicyStore(self.output).load_reset(split,cohort)
        fake=Path(self.tmp.name)/'symlink'; (fake/'data/policy').mkdir(parents=True)
        (fake/'data/policy/primary_test.jsonl').symlink_to(self.output/'data/evaluator/student_outcomes_reference.jsonl')
        with self.assertRaises(ValueError): PolicyStore(fake).load_reset('test')

    def test_forbidden_serialized_fact_and_extra_field_rejected(self):
        record=reset_observations(self.contexts[0]).to_dict()
        record['observations'][0]['field']='G3'
        with self.assertRaises((ValueError,TypeError)): PolicyReset.from_dict(record)
        record=reset_observations(self.contexts[0]).to_dict(); record['source_row']=1
        with self.assertRaises(ValueError): PolicyReset.from_dict(record)

    def test_environment_never_loads_static_future_draw(self):
        rows=EnvironmentStore(self.output).load_fixture('train')
        self.assertEqual(len(rows),1200)
        self.assertNotIn('dropout_draw_at_static_annual_hazard_assumed',rows[0].to_dict())
        self.assertNotIn('constant_weekly_hazard_assumed',rows[0].to_dict())

    def test_provenance_covers_every_input_column_contract_field_parameter(self):
        rows=read_csv(self.output/'provenance_register.v2.csv'); indexed={(r['table'],r['field']):r for r in rows}
        self.assertEqual(len(indexed),len(rows))
        for table,values in self.tables.items():
            for name in values[0]: self.assertIn((table,name),indexed)
        for contract,schema in json_schemas()['$defs'].items():
            for name in schema['properties']: self.assertIn((contract,name),indexed)
        def leaves(value,prefix):
            if isinstance(value,dict):
                for k,v in value.items(): yield from leaves(v,prefix+'.'+k)
            else: yield prefix
        for name,spec in GENERATOR_ASSUMPTIONS.items():
            for field in leaves(spec['value'],name): self.assertIn(('fixture_parameters',field),indexed)
        self.assertEqual(indexed['student_dataset','school_id']['source_derivation'],'school')

    def test_relocated_repeat_build_is_identical_and_preserves_inputs(self):
        root=Path(self.tmp.name)/'relocated'
        for p in self.paths.values():
            dest=root/p.relative_to(PROJECT); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dest)
        hashes={str(p):sha(p) for p in root.rglob('*') if p.is_file()}
        generated=root/'outputs/old'; generated.mkdir(parents=True); (generated/'junk.csv').write_text('G3\n0\n')
        out=Path(self.tmp.name)/'v2'; build(root,self.config,out)
        a=json.loads((self.output/'COMPLETED.json').read_text()); b=json.loads((out/'COMPLETED.json').read_text())
        self.assertEqual(a,b)
        self.assertEqual(hashes,{p:sha(p) for p in hashes})
        self.assertEqual(verify(out)['artifacts_verified'],len(a['artifacts']))

    def test_missing_modified_inputs_fail_before_writes(self):
        config=json.loads(self.config.read_text()); config['inputs'][0]['sha256']='0'*64
        bad=Path(self.tmp.name)/'bad-config.json'; bad.write_text(json.dumps(config))
        out=Path(self.tmp.name)/'not-created/v1'
        with self.assertRaises(ValueError): build(PROJECT,bad,out)
        self.assertFalse(out.parent.exists())
        with self.assertRaises(ValueError): build(Path(self.tmp.name),self.config,out)
        self.assertFalse(out.parent.exists())

    def test_existing_outputs_and_baseline_writes_rejected(self):
        with self.assertRaises(ValueError): build(PROJECT,self.config,self.output)
        with self.assertRaises(ValueError): preflight(PROJECT,self.config,PROJECT/'student_cmdp_study/new_stage1')


if __name__=='__main__':
    unittest.main()

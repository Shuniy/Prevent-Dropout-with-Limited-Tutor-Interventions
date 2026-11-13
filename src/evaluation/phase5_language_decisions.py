"""Matched snapshots and own-trajectory closed loops for language follow-up v2."""
from dataclasses import asdict,replace
import json
from pathlib import Path

from .provenance import (digest,runtime_identity,source_fingerprints,write_exclusive,
    staged_artifacts,seal_directory,verify_directory)
from ..intervention.feedback_notes import PHRASES,MENTOR_PHRASES
from ..intervention.observation_extractor import (CONCEPTS,FixtureObservationExtractor,
    RecordedOutcomeExtractor,gold_payload,validate_extraction,source_spans)
from ..intervention.followup_extractor import LegacyDeterministicExtractor
from ..school.followup_notes import FollowupWeeklyNote
from ..school.delivery_contracts import WeeklyNote
from ..school.phase5_delivery import PredictionController,phase5_payload
from ..school.delivery_experiments import normalized,synthetic_environment,scorecard
from ..school.delivery_policy import WeeklyDeliveryPolicy
from ..school.delivery_resources import validate_offers
from ..school.state_estimator import StudentStateEstimator


ARMS=('structured_available','note_content_gold','existing_deterministic','prompted_llm','missing_notes','corrupted_notes')
RENDERINGS={
 ('participation','reported','unknown','present','regular','unknown','unknown'):'The mentor reports participation is regular.',
 ('participation','reported','unknown','present','low','unknown','unknown'):'The mentor reports participation is low.',
 ('participation','reported','unknown','absent','no_contact','unknown','unknown'):'The teacher reports no recent contact with the learner.',
 ('academic_difficulty','reported','unknown','present','difficulty','unresolved','unknown'):'The learner reports assignments are difficult to complete.',
 ('participation','insufficient_evidence','unknown','unknown','unknown','unknown','unknown'):'Information about participation is insufficient.',
 ('participation','conflicting','unknown','unknown','unknown','unknown','unknown'):'Accounts of participation conflict and are not reconciled.',
}


def note_from_record(record):
    values={k:v for k,v in record.items() if k!='creation_time'}
    values['source_event_ids']=tuple(values['source_event_ids'])
    return (FollowupWeeklyNote if 'evidence_contract' in values else WeeklyNote)(**values)


def render_followup(note):
    """Renderer takes only current public prose, never private simulated state.

    Gold is an explicit renderer annotation from the original observable facts;
    it is not an LLM result or an independent human annotation.
    """
    phrases={**PHRASES,**MENTOR_PHRASES}
    pieces=[];facts=[];offset=0
    for span in source_spans(note.text):
        meaning=phrases.get(span['text'])
        text=RENDERINGS.get(meaning,span['text'])
        pieces.append(text)
        if meaning is not None:
            facts.append(dict(zip(CONCEPTS,meaning)) | dict(numeric_value=None,unit=None,evidence=text,
                start_offset=offset,end_offset=offset+len(text),source_month=note.source_week))
        offset+=len(text)+1
    result=FollowupWeeklyNote(**asdict(note),evidence_contract='development_sentence_entailment/v2')
    result=replace(result,text=' '.join(pieces))
    return result,dict(student_id=note.student_id,note_id=note.note_id,observations=facts)


class RendererGoldExtractor:
    calls=0
    def __init__(self,annotations):
        self.annotations=annotations
    def extract(self,note,as_of_time):
        if note.note_id not in self.annotations:
            raise ValueError('missing explicit renderer annotation')
        return validate_extraction(self.annotations[note.note_id],note,as_of_time)


class FollowupStateEstimator(StudentStateEstimator):
    """Map validated v2 facts to existing signal likelihoods, retaining evidence.

    The legacy estimator still uses exact canonical prose. This explicit adapter
    adds only development-approved sentences; it never receives an LLM risk or
    hidden state, and does not invent a new measurement likelihood.
    """
    @property
    def configuration(self):
        return super().configuration | dict(condition_evidence_contract='validated_sentence_semantics/v2')

    @staticmethod
    def _signal_for_fact(fact,reverse):
        import re
        from ..intervention.followup_extractor import RULES
        from ..intervention.feedback_notes import SIGNAL_PHRASES
        canonical=StudentStateEstimator._signal_for_fact(fact,reverse)
        if canonical is not None:
            return canonical
        meanings={PHRASES[phrase]:signal for signal,phrase in SIGNAL_PHRASES.items()}
        semantics=tuple(getattr(fact,k) for k in CONCEPTS)
        if any(re.fullmatch(pattern,fact.evidence) and expected==semantics for pattern,expected in RULES):
            return meanings.get(semantics)
        return None


class FollowupInformationController(PredictionController):
    def __init__(self,*args,language_condition='existing_deterministic',extractor=None,**kwargs):
        if language_condition not in ARMS:
            raise ValueError('unknown language condition')
        if language_condition=='prompted_llm' and extractor is None:
            raise ValueError('prompted arm requires actual or explicitly recorded inference; no fallback')
        self.language_condition=language_condition
        self.rendered_gold={};self._rendered_notes=set()
        if extractor is None:
            extractor=(RendererGoldExtractor(self.rendered_gold) if language_condition=='note_content_gold'
                else FixtureObservationExtractor() if language_condition=='structured_available'
                else LegacyDeterministicExtractor())
        super().__init__(*args,extractor=extractor,**kwargs)
        env=self.environment
        self.estimator=FollowupStateEstimator(wait_matrix=env.config.weekly_wait_matrix,
            treatment_matrix=env.config.treatment_matrix,action_contract='weekly_delivered_v1',
            observation_config=env.observation_config)

    def _before_render(self,note):
        return note

    def _transformable(self,note):
        return True

    def _generate_notes(self):
        recorded=self.recorded_notes;self.recorded_notes=None
        try:
            super()._generate_notes()
        finally:
            self.recorded_notes=recorded
        result=[]
        for note in self.notes:
            if note.note_id not in self._rendered_notes:
                note=self._before_render(note)
                if self._transformable(note) and self.language_condition!='structured_available':
                    if self.language_condition=='missing_notes':
                        self._rendered_notes.add(note.note_id)
                        continue
                    note,payload=render_followup(note)
                    if self.language_condition=='corrupted_notes':
                        note=replace(note,text='The filing cabinet needs repair.')
                        payload=dict(student_id=note.student_id,note_id=note.note_id,observations=[])
                else:
                    payload=gold_payload(note)
                self.rendered_gold[note.note_id]=payload
                self._rendered_notes.add(note.note_id)
            if recorded is not None and recorded.get(note.note_id)!=note:
                raise ValueError('follow-up note generation differs from recorded own-trajectory note')
            result.append(note)
        self.notes=result


def decision_record(controller,state,action):
    validate_offers(state,action,controller.environment.config)
    return normalized(dict(week=state.week,beliefs={s.student_id:s.estimate.condition_probabilities for s in state.students},
        risks={s.student_id:s.risk.probability for s in state.students},
        offers=action.offers,cancellations=action.cancel_programme_ids,reviews=action.continuation_reviews,
        constraint_valid=True,authorized_history=state.authorized_event_ids,ledger=state.ledger))


def compare_decisions(gold,other):
    return dict(belief_l1=sum(sum(abs(a-b) for a,b in zip(v,other['beliefs'][sid])) for sid,v in gold['beliefs'].items()),
        risk_l1=sum(abs(v-other['risks'][sid]) for sid,v in gold['risks'].items()),
        allocation_changed=gold['offers']!=other['offers'],
        continuation_cancellation_changed=gold['cancellations']!=other['cancellations'],
        decision_difference_is_improvement=False)


class LanguageBoundaryController(FollowupInformationController):
    """A declared controlled signal fixture, not sampled population evidence."""
    def _before_render(self,note):
        from ..school.delivery_acceptance import LOW,VAGUE
        if not note.programme_id:
            return replace(note,text=LOW if note.source_week==0 or (
                note.source_week==1 and note.student_id!='fictional-00') else VAGUE)
        return note

    def _transformable(self,note):
        return bool(note.observation_contract and note.student_id=='fictional-00' and note.source_week==1)


class FocalSessionExtractor:
    """Controlled experiment: vary extraction only for the focal mentor note.

    Every other note uses the common canonical information control, including
    the pre-decision prefix. A failed focal request supplies no replacement.
    The separate source-held-out LLM arm evaluates all its own-trajectory notes.
    """
    def __init__(self,extractor):
        self.extractor=extractor
        self.client=extractor.client

    @property
    def calls(self):
        return self.extractor.calls

    @property
    def responses(self):
        return self.extractor.responses

    @property
    def audit_records(self):
        return self.extractor.audit_records

    @property
    def inference_kind(self):
        return self.extractor.inference_kind

    @property
    def configuration(self):
        return self.extractor.configuration | dict(inference_scope='controlled_focal_actual_session_note_only')

    def extract(self,note,as_of_time):
        if note.observation_contract and note.student_id=='fictional-00' and note.source_week==1:
            return self.extractor.extract(note,as_of_time)
        return FixtureObservationExtractor().extract(note,as_of_time)


def boundary_controller(arm,extractor=None,recorded_notes=None):
    from ..school.delivery_config import DeliveryConfig
    from ..school.delivery_environment import WeeklyDeliveryEnvironment
    from ..school.delivery_acceptance import _mentors
    from ..school.observation_model import ObservationConfig
    config=DeliveryConfig(num_students=3,num_mentors=1,horizon_weeks=8,
        weekly_mentor_hours=1,weekly_session_capacity=1,max_concurrent_students=1,
        acceptance_probability=1,attendance_probability=1,delivery_probability=1,
        cancellation_probability=0,budget=11,seed=41)
    original=synthetic_environment(config)
    session='41:fictional-00:weekly-programme:1:session:1'
    env=WeeklyDeliveryEnvironment(original.profiles,_mentors(config),config,
        initial_conditions=original.initial_conditions,
        observation_config=ObservationConfig(missing_probability=0,delay_probability=0),
        mentor_signal_overrides=((session,'regular_participation'),))
    if arm=='prompted_llm' and extractor is not None and not isinstance(extractor,RecordedOutcomeExtractor):
        extractor=FocalSessionExtractor(extractor)
    return LanguageBoundaryController(env,WeeklyDeliveryPolicy(config,'point',continuation_margin=.01),
        language_condition=arm,extractor=extractor,recorded_notes=recorded_notes)


def save_boundary(controller,path):
    controller.validate()
    payload=phase5_payload(controller)
    manifest=dict(contract='language_controlled_boundary/replay/v2',arm=controller.language_condition,
        runtime=runtime_identity(),source_fingerprints=source_fingerprints(),payload_identity=digest(payload))
    with staged_artifacts(path,identity=manifest) as stage:
        write_exclusive(stage/'manifest.json',manifest)
        write_exclusive(stage/'episode.json',payload)
        write_exclusive(stage/'scorecard.json',normalized(scorecard(controller)))
        write_exclusive(stage/'world.json',normalized(dict(truth=controller.environment.evaluator_truth,
            draws=controller.environment.exogenous_draws)))
        seal_directory(stage)


def replay_boundary(path,*,on_verified_controller=None):
    path=Path(path);verify_directory(path)
    manifest=json.loads((path/'manifest.json').read_text())
    payload=json.loads((path/'episode.json').read_text());weekly=payload['weekly']
    runtime=runtime_identity()
    if (manifest['contract']!='language_controlled_boundary/replay/v2' or digest(payload)!=manifest['payload_identity']
            or manifest['source_fingerprints']!=source_fingerprints() or any(
                manifest['runtime'][k]!=runtime[k] for k in ('python','implementation','dependencies'))):
        raise ValueError('controlled language replay requires recorded source/runtime/input')
    notes={n['note_id']:note_from_record(n) for n in weekly['notes']}
    c=boundary_controller(manifest['arm'],RecordedOutcomeExtractor(weekly['extraction_attempts'],weekly['extracted_batches']),notes).run_episode()
    c.validate()
    if (phase5_payload(c)!=payload or normalized(scorecard(c))!=json.loads((path/'scorecard.json').read_text())
            or normalized(dict(truth=c.environment.evaluator_truth,draws=c.environment.exogenous_draws))!=json.loads((path/'world.json').read_text())):
        raise ValueError('controlled language exact replay mismatch')
    if on_verified_controller is not None:
        on_verified_controller(c)
    return dict(status='exact_replay_verified',live_requests=0)


def boundary_comparison(output,extractor_factory=None):
    arms={};controllers={}
    for arm in ARMS:
        if arm=='prompted_llm' and extractor_factory is None:
            arms[arm]=dict(status='unexecuted_not_requested');continue
        c=boundary_controller(arm,extractor_factory() if arm=='prompted_llm' else None).run_episode()
        c.validate();controllers[arm]=c
        path=Path(output)/arm;save_boundary(c,path)
        replay=replay_boundary(path)
        arms[arm]=dict(status='executed',snapshot=decision_record(c,c.snapshots[1],c.decisions[1]),
            later_offers=normalized([a.offers for a in c.decisions[2:]]),
            continuation_reviews=normalized([a.continuation_reviews for a in c.decisions]),
            final_scorecard=normalized(scorecard(c)),replay=replay)
        if arm=='prompted_llm':
            arms[arm]['inference']=dict(request_attempts=c.extractor.calls,model_responses=c.extractor.responses,
                status='unexecuted_model_unavailable' if c.extractor.responses==0 else
                'executed_mock_software_regression' if c.extractor.inference_kind=='mock_software_regression' else 'executed_real_model')
    # All arms share a factual pre-note prefix, including first-week decisions.
    first=next(iter(controllers.values()))
    if any(c.snapshots[0]!=first.snapshots[0] or c.decisions[0]!=first.decisions[0]
           or c.environment.evaluator_truth[:2]!=first.environment.evaluator_truth[:2] for c in controllers.values()):
        raise AssertionError('language matched-history prefix changed')
    gold=arms['note_content_gold']
    comparisons={name:compare_decisions(gold['snapshot'],entry['snapshot']) | dict(
        later_allocation_changed=gold['later_offers']!=entry['later_offers'])
        for name,entry in arms.items() if 'snapshot' in entry}
    if not (comparisons['existing_deterministic']['continuation_cancellation_changed']
            and comparisons['existing_deterministic']['later_allocation_changed']):
        raise AssertionError('supported factual information did not change an actionable future decision')
    report=dict(contract='language_downstream_boundary/v2',arms=arms,comparisons=comparisons,
        matched_history='same authorized prefix, policy and resources at week 2; only focal note information changes',
        closed_loop='each arm emits its own later notes and decisions using shared keyed exogenous mechanisms',
        limitation='controlled engineering positive case; no empirical or population causal improvement claim')
    write_exclusive(Path(output)/'boundary_report.json',report)
    return report

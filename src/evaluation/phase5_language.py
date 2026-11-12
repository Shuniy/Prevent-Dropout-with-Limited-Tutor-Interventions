"""Frozen, separately authored prose benchmark; no prompt or grammar tuning.

Gold below is authored from note meaning, not from gold_payload or simulator
truth. It is a small synthetic challenge set, NOT independent human annotation.
Unseen language may correctly trigger abstention, but that still loses recall.
"""
from collections import Counter
from dataclasses import asdict, replace
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.stats import rankdata

from .extraction_evaluation import evaluate_records, run_comparator
from .provenance import digest, extractor_identity
from ..intervention.observation_extractor import CONCEPTS, FixtureObservationExtractor, validate_batch
from ..school.delivery_contracts import WeeklyNote


# Seven-concept annotations declared independently of production phrase tables.
SEMANTICS = {
    'regular':('participation','reported','unknown','present','regular','unknown','unknown'),
    'difficulty':('academic_difficulty','reported','unknown','present','difficulty','unresolved','unknown'),
    'low':('participation','reported','unknown','present','low','unknown','unknown'),
    'no_contact':('participation','reported','unknown','absent','no_contact','unknown','unknown'),
    'partial':('participation','reported','improved','present','unknown','partially_resolved','unknown'),
    'negation':('academic_difficulty','reported','unknown','absent','unknown','unknown','unknown'),
    'unknown':('participation','insufficient_evidence','unknown','unknown','unknown','unknown','unknown'),
    'conflict':('participation','conflicting','unknown','unknown','unknown','unknown','unknown'),
    'pending':('support_barrier','reported','unchanged','present','unknown','unresolved','pending'),
    'completed':('mentoring_support','observed','unknown','present','unknown','unknown','completed'),
}

# Each tuple is a distinct scenario, never a paraphrase distributed across splits.
# Empty annotations explicitly mean no assertion within the narrow output schema.
CASES = {
 'development':[
    ('school_form','routine','The school reports regular participation in recent activities.','regular'),
    ('school_form','assignments','The student reports difficulty completing assignments.','difficulty'),
    ('school_form','poor_contact','The school reports no recent contact with the student.','no_contact'),
    ('school_form','participation','The school reports low participation in recent activities.','low'),
    ('school_form','qualified_gain','The student reports greater participation, but progress is not yet consistent.','partial'),
    ('school_form','denial','The student denies difficulty completing assignments.','negation'),
    ('school_form','insufficient','There is insufficient evidence about participation.','unknown'),
    ('school_form','disagreement','Reports about participation conflict and remain unresolved.','conflict'),
    ('school_form','transport_pending','The student reports that transport remains a barrier; the support application is pending.','pending'),
    ('school_form','delivered_course','The student completed the scheduled mentoring appointments.','completed'),
    ('development_memo','financial_inference','A worn backpack cannot establish household income.',None),
    ('development_memo','causal_speculation','Perhaps tutoring prevented a future departure, but there is no evidence for that claim.',None),
    ('development_memo','offered_not_delivered','An invitation was sent; no mentoring meeting has happened.',None),
    ('development_memo','irrelevant','The noticeboard needs repainting before the festival.',None),
    ('development_memo','unquantified','The student feels somewhat better; no attendance count is available.',None),
    ('development_memo','cancelled','Support was cancelled before the first appointment.',None),
 ],
 'validation':[
    ('validation_handover','lesson_pattern','Staff handover: participation has been regular across the recent lessons.','regular'),
    ('validation_handover','unfinished_tasks','The learner says completing the assigned work is difficult.','difficulty'),
    ('validation_handover','quiet_lessons','Colleagues report little participation in recent lessons.','low'),
    ('validation_handover','unreached','The office reports that recent attempts to contact the learner have failed.','no_contact'),
    ('validation_handover','uncertain_progress','A small improvement is reported, although participation remains inconsistent.','partial'),
    ('validation_handover','negative_report','The learner says there is no difficulty finishing assignments.','negation'),
    ('validation_handover','no_evidence','We lack enough information to describe participation.','unknown'),
    ('validation_handover','conflicting_accounts','Staff accounts disagree about participation and have not been reconciled.','conflict'),
    ('validation_admin','refusal','The optional support offer was declined; this says nothing about educational progress.',None),
    ('validation_admin','missed_visit','The scheduled mentor appointment was missed, so no educational response was observed.',None),
    ('validation_admin','future_availability','An update exists but will only be released next week.','unknown'),
    ('validation_admin','private_finances','No verified income information is held by the school.',None),
 ],
 'test':[
    ('test_correspondence','teacher_letter','Dear coordinator, our staff describe the pupil as taking part steadily in the recent classroom activities.','regular'),
    ('test_correspondence','student_letter','I am writing because getting the set assignments finished is difficult for me.','difficulty'),
    ('test_ledger','participation_ledger','Recent activity log: staff describe participation as low.','low'),
    ('test_ledger','unanswered_ledger','Contact log: school staff have had no recent contact with this pupil.','no_contact'),
    ('test_reflective','uneven_recovery','In the learner account, joining in is better than before, though the change is still patchy.','partial'),
    ('test_colloquial','explicit_denial','Finishing the assignments is not a problem for me, the student says.','negation'),
    ('test_reflective','uncertain_contact','Nobody has enough evidence to say how participation is going.','unknown'),
    ('test_correspondence','unresolved_dispute','Two staff accounts of participation contradict each other, and neither has been verified over the other.','conflict'),
    ('test_ledger','delayed_source','On 1 January 2026, school staff recorded low participation in classroom activities.','low'),
    ('test_colloquial','continuing_barrier','The student says the bus problem is still there and the request for help is waiting for approval.','pending'),
    ('test_ledger','appointments_complete','Delivery register: all of the scheduled mentoring appointments were completed.','completed'),
    ('test_correspondence','missed_session','The mentor arrived, but the pupil did not attend the scheduled appointment.',None),
    ('test_colloquial','accepted_only','Yes to the offer, the pupil said, but the first appointment is still in the future.',None),
    ('test_reflective','cancelled_support','The remaining sessions were cancelled, without any evidence about educational improvement.',None),
    ('test_reflective','transport_cost_report','The family said they could not afford bus transport this week.',None),
    ('test_colloquial','unsupported_poverty','An observer guessed that the family must be poor because the pupil looked tired.',None),
    ('test_correspondence','causal_claim','Someone credited tutoring for preventing dropout, but supplied no outcome evidence.',None),
    ('test_ledger','irrelevant_prose','Room booking: the library table was moved beside the window.',None),
    ('test_reflective','future_note','The participation report has not yet been made available.','unknown'),
    ('test_colloquial','unmeasured_gain','Things are better, said the pupil, without specifying participation, grades, or attendance.',None),
 ]}


def build_language_benchmark():
    cases=[]
    for split,rows in CASES.items():
        for i,(style,scenario,text,label) in enumerate(rows):
            case_id=f'{split}-{i:03d}'
            source_week,available,cutoff=0,1,1
            if scenario=='delayed_source':
                available,cutoff=3,3
            if scenario in ('future_note','future_availability'):
                available,cutoff=3,1
            note=WeeklyNote(case_id,case_id+'-student',source_week,available,text,(case_id+'-event',))
            gold=[]
            if label is not None:
                # Exact gold spans are saved even for temporally unavailable
                # notes, but the scoring contract excludes their unavailable facts.
                start=0
                gold=[{**dict(zip(CONCEPTS,SEMANTICS[label])),
                    'numeric_value':None,'unit':None,'evidence':text,'start_offset':start,'end_offset':len(text),
                    'source_month':source_week}]
            eligible=available<=cutoff and source_week<cutoff
            legacy=dict(note_id=note.note_id,student_id=note.student_id,mentor_id=None,programme_id=None,
                note_type='monitoring',event_month=source_week,creation_time=note.creation_time,
                available_from_month=available,text=text,source_event_ids=list(note.source_event_ids))
            if scenario=='delayed_source':
                legacy['creation_time']='2026-01-15T12:00:00+00:00'
            cases.append(dict(case_id=case_id,split=split,category=scenario,style=style,
                scenario_id=case_id+'-scenario',paraphrase_group=case_id+'-scenario',template_family=style,
                source_anchor=None,note=legacy,weekly_note=asdict(note),as_of_month=cutoff,eligible=eligible,
                gold=dict(student_id=note.student_id,note_id=note.note_id,observations=gold) if eligible else None,
                annotation=dict(version='note_content_gold/v1',origin='single_synthetic_author_no_human_review',
                    reviewed=False,disagreements=None,assertion_polarity='negated' if label=='negation' else 'unresolved' if label=='conflict' else 'unspecified',
                    source_week=source_week,availability_week=available,source_anchor=None,
                    source_calendar_date='2026-01-01',note_creation_time=legacy['creation_time'],
                    out_of_schema_construct='reported_transport_cost_difficulty' if scenario=='transport_cost_report'
                        else 'support_accepted_not_delivered' if scenario=='accepted_only'
                        else 'session_missed' if scenario=='missed_session'
                        else 'support_cancelled' if scenario=='cancelled_support' else None,
                    limitation='narrow production schema; out-of-schema constructs retained separately; income unknown')))
    validate_partitions(cases)
    return cases


def validate_partitions(cases):
    for key in ('scenario_id','paraphrase_group','template_family','source_anchor'):
        owner={}
        for case in cases:
            value=case[key]
            if value is None:
                continue
            if value in owner and owner[value]!=case['split']:
                raise ValueError('language partition leakage: '+key)
            owner[value]=case['split']


def evaluate_language(cases=None,*,live_extractor=None):
    cases=build_language_benchmark() if cases is None else cases
    validate_partitions(cases)
    output=dict(contract='independent_style_challenge/v1',corpus_hash=digest(cases),
        annotation_limit='single synthetic author; no independent human review or real mentor corpus',
        independence='scenario/template families disjoint; same author and narrow semantic schema remain shared',
        llm=dict(status='unexecuted',reason='live inference not explicitly enabled; no fixture substitution'),
        extractor=extractor_identity(FixtureObservationExtractor()),splits={})
    for split in ('development','validation','test'):
        rows=[c for c in cases if c['split']==split]
        methods={}
        for name,method in (('structured_form_control','gold_reference'),('deterministic_grammar','exact_rule')):
            started=perf_counter()
            records=run_comparator(rows,method)
            methods[name]=dict(metrics=evaluate_records(rows,records),records=records,
                runtime=dict(model_calls=0,latency_seconds=perf_counter()-started,cost=None,retries=0),
                by_style={s:evaluate_records([c for c in rows if c['style']==s],records) for s in sorted({c['style'] for c in rows})},
                by_scenario={c['category']:evaluate_records([c],records) for c in rows})
        if live_extractor is not None:
            started=perf_counter()
            calls_before=getattr(live_extractor,'calls',0)
            records=run_comparator(rows,'real_llm',live_extractor)
            methods['prompted_llm']=dict(metrics=evaluate_records(rows,records),records=records,
                runtime=dict(model_calls=getattr(live_extractor,'calls',0)-calls_before,
                    latency_seconds=perf_counter()-started,cost=None,retries=0),identity=extractor_identity(live_extractor))
            output['llm']=dict(status='executed',identity=extractor_identity(live_extractor))
        output['splits'][split]=dict(n=len(rows),methods=methods)
    if live_extractor is not None:
        live_records=[r for v in output['splits'].values() for r in v['methods']['prompted_llm']['records']]
        attempted=[r for r in live_records if r['status']!='rejected_before_inference']
        # A returned but invalid payload is an executed extraction failure. If
        # every attempted request failed at the backend, no model evaluation
        # was executed, including the common missing-model HTTP 404 case.
        unavailable=lambda r:any(marker in r.get('error','') for marker in ('Ollama unavailable','Ollama HTTP '))
        if attempted and all(unavailable(r) and r.get('raw_output') is None for r in attempted):
            output['llm']['status']='unexecuted_model_unavailable'
            for v in output['splits'].values():
                v['methods']['prompted_llm']['metrics']=None
    return output


def gold_canonical_text(case):
    """Evaluation-only semantic bridge, with no access to simulator state.

    The historical filter only understands canonical sentences. Gold is encoded
    into that supported representation; it never pretends extraction succeeded
    on the original unfamiliar prose. Preserve original evidence in the report.
    """
    from ..intervention.feedback_notes import PHRASES
    inverse={v:k for k,v in PHRASES.items()}
    return ' '.join(inverse[tuple(f[k] for k in CONCEPTS)] for f in case['gold']['observations'])


def matched_snapshot_evaluation(cases=None):
    """Actual extraction -> filtering -> policy at a matched feasible snapshot.

    Case content is an explicit controlled information intervention, not a
    claim that an arbitrary source event was generated by its hidden condition.
    Normal temporal and event provenance checks still run in the controller.
    """
    from ..school.delivery_config import DeliveryConfig
    from ..school.phase5_delivery import population_environment,PredictionController
    from ..school.delivery_policy import WeeklyDeliveryPolicy
    from ..school.delivery_resources import validate_offers
    cases=build_language_benchmark() if cases is None else cases
    results=[]
    for case in cases:
        if case['split']!='test' or not case['eligible']:
            continue
        arms={}
        for arm in ('structured_observable','note_content_gold','extracted_notes','missing_notes'):
            config=DeliveryConfig(num_students=6,num_mentors=1,horizon_weeks=8,weekly_mentor_hours=1,
                weekly_session_capacity=1,max_concurrent_students=1,seed=415)
            env,pop=population_environment(config,population_mode='source_held_out',split='test',population_seed=415)
            c=PredictionController(env,WeeklyDeliveryPolicy(config,'point'))
            note=next(n for n in c.notes if n.source_week==0)
            if arm=='note_content_gold':
                c.notes=[replace(note,text=gold_canonical_text(case))]
            elif arm=='extracted_notes':
                c.notes=[replace(note,text=case['note']['text'])]
            elif arm=='missing_notes':
                c.notes=[]
            # structured_observable keeps all authorized emissions in their
            # exact structured-equivalent representation as a wider control.
            state=c.prepare_decision_snapshot()
            action=c.policy.plan(state)
            validate_offers(state,action,config)
            beliefs={s.student_id:s.estimate.condition_probabilities for s in state.students}
            risks={s.student_id:s.risk.probability for s in state.students}
            rank={s.student_id:float(r) for s,r in zip(state.students,rankdata([-s.risk.probability for s in state.students]))}
            arms[arm]=dict(beliefs=beliefs,risks=risks,ranks=rank,
                assignments=[(a.student_id,a.mentor_id) for a in action.offers],
                cancellations=list(action.cancel_programme_ids),attempts=len(c.attempts),
                constraint_valid=True,decision_status=action.status,
                missed_opportunity_rule='gold-supported feasible assignment absent from extracted arm',
                unnecessary_rule='extracted assignment absent from gold; disagreement, not causal harm')
        gold,extracted=arms['note_content_gold'],arms['extracted_notes']
        results.append(dict(case_id=case['case_id'],arms=arms,
            status='exercised' if extracted['attempts'] else 'unavailable_zero_extraction_attempts',
            belief_l1=sum(sum(abs(a-b) for a,b in zip(gold['beliefs'][sid],extracted['beliefs'][sid])) for sid in gold['beliefs']),
            risk_l1=sum(abs(gold['risks'][sid]-extracted['risks'][sid]) for sid in gold['risks']),
            ranking_changes=sum(gold['ranks'][sid]!=extracted['ranks'][sid] for sid in gold['ranks']),
            assignment_disagreement=set(gold['assignments'])!=set(extracted['assignments']),
            continuation_cancellation_disagreement=gold['cancellations']!=extracted['cancellations'],
            missing_gold_assignments=len(set(gold['assignments'])-set(extracted['assignments'])),
            extra_extracted_assignments=len(set(extracted['assignments'])-set(gold['assignments']))))
    return dict(contract='heldout_note_matched_snapshot/v1',cases=results,
        attempts=sum(r['arms']['extracted_notes']['attempts'] for r in results),
        status='exercised' if any(r['arms']['extracted_notes']['attempts'] for r in results) else 'unavailable_zero_extraction_attempts',
        assignment_disagreements=sum(r['assignment_disagreement'] for r in results),
        limitation='snapshot interventions; gold semantic bridge explicit; no held-out prompt tuning; continuation coverage needs active-programme example')


def active_programme_language_example(output=None):
    """Held-out regular-report syntax at an established actual-session boundary.

    Each arm runs its own trajectory and subsequent observations. Only the one
    controlled mentor note differs. Existing public resource checks still apply.
    This selected engineering fixture is not a population effect estimate.
    """
    from ..school.delivery_feedback_acceptance import mentor_boundary_episode,mentor_chain
    from ..school.delivery_experiments import save_delivery_episode,replay_delivery_episode,normalized
    case=next(c for c in build_language_benchmark() if c['category']=='teacher_letter')
    gold=mentor_boundary_episode()
    extracted=mentor_boundary_episode(unsupported_text=case['note']['text'])
    low=mentor_boundary_episode('low_participation')
    arms={'gold_supported_regular':gold,'extracted_heldout_regular':extracted,'supported_low_positive_control':low}
    chains={name:mentor_chain(c) for name,c in arms.items()}
    replays={}
    if output is not None:
        for name,c in arms.items():
            path=Path(output)/name
            save_delivery_episode(c,path)
            replays[name]=replay_delivery_episode(path)
    return normalized(dict(case_id=case['case_id'],arms=chains,replays=replays,
        gold_cutoff2_review=gold.decisions[1].continuation_reviews[0].decision,
        extracted_cutoff2_review=extracted.decisions[1].continuation_reviews[0].decision,
        later_assignment_disagreement=any(a.offers!=b.offers for a,b in zip(gold.decisions[2:],extracted.decisions[2:])),
        limitation='established controlled fictional boundary, not source-population effect evidence'))

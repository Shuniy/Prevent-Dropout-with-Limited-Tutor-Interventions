"""Separately frozen language v2: annotation contract, real inference and replay."""
from dataclasses import asdict
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .extraction_evaluation import evaluate_records, _batch_payload
from .phase5_language import validate_partitions
from .provenance import digest,write_exclusive
from ..intervention.observation_extractor import CONCEPTS,EXTRACTION_SCHEMA,validate_batch,validate_extraction
from ..intervention.followup_extractor import (LegacyDeterministicExtractor,
    PROMPT_VERSION,RULE_VERSION,EVIDENCE_CONTRACT)
from ..school.followup_notes import FollowupWeeklyNote


CORPUS_VERSION='mentor_prose_challenge/v2'
# Annotation meanings are separately declared, never obtained from extraction.
MEANINGS={
 'regular':('participation','reported','unknown','present','regular','unknown','unknown'),
 'low':('participation','reported','unknown','present','low','unknown','unknown'),
 'difficulty':('academic_difficulty','reported','unknown','present','difficulty','unresolved','unknown'),
 'no_contact':('participation','reported','unknown','absent','no_contact','unknown','unknown'),
 'unknown':('participation','insufficient_evidence','unknown','unknown','unknown','unknown','unknown'),
 'conflict':('participation','conflicting','unknown','unknown','unknown','unknown','unknown'),
}


def build_followup_corpus():
    # A new synthetic set, not modifications of the original frozen challenge.
    # The validator's development rules are fixed before evaluating these splits.
    texts={
      'development':[
        ('The mentor reports participation is regular.','regular'),
        ('The mentor reports participation is low.','low'),
        ('The teacher reports no recent contact with the learner.','no_contact'),
        ('The learner reports assignments are difficult to complete.','difficulty'),
        ('Information about participation is insufficient.','unknown'),
        ('Accounts of participation conflict and are not reconciled.','conflict'),
        ('A guess about family income is not a verified observation.',None)],
      'validation':[
        ('The teacher reports that participation is regular.','regular'),
        ('The teacher reports participation has been low.','low'),
        ('The learner reports that assignments are difficult to complete.','difficulty'),
        ('The classroom clock needs a new battery.',None)],
      'test':[
        ('School staff report that participation has been regular.','regular'),
        ('School staff report that participation has been low.','low'),
        ('School staff report no recent contact with the learner.','no_contact'),
        ('The pupil described the set work as hard to finish.','difficulty'),
        ('Participation cannot yet be described from the available records.','unknown'),
        ('The accounts disagree about participation and nobody has adjudicated them.','conflict'),
        ('An observer speculates that tutoring prevented a departure.',None),
        ('A request for financial help is not financial verification.',None)]}
    cases=[]
    for split,rows in texts.items():
        for index,(text,label) in enumerate(rows):
            identity=f'language-v2-{split}-{index}'
            note=FollowupWeeklyNote(identity,identity+'-student',0,1,text,(identity+'-source',))
            facts=[] if label is None else [dict(zip(CONCEPTS,MEANINGS[label])) | dict(
                numeric_value=None,unit=None,evidence=text,start_offset=0,end_offset=len(text),source_month=0)]
            payload=dict(student_id=note.student_id,note_id=note.note_id,observations=facts)
            # Independent controls here carry the same information by design.
            cases.append(dict(case_id=identity,split=split,category=label or 'unsupported',
                scenario_id=identity,paraphrase_group=identity,template_family=split+'-v2-family',
                style=split+'-v2-prose',source_anchor=None,weekly_note=asdict(note),
                note=dict(note_id=identity,student_id=note.student_id,text=text,event_month=0),
                as_of_month=1,eligible=True,gold=payload,structured_observations=payload,
                annotation=dict(source='new_synthetic_author',reviewer_status='unreviewed_synthetic',
                    author_id='synthetic_author',reviewer_id=None,exact_evidence_spans=[
                        dict(start=0,end=len(text),quote=text)] if facts else [],
                    unknown_assertions=label=='unknown',conflicting_assertions=label=='conflict',
                    unsupported_claims=[text] if label is None else [],disagreements=[],adjudication=None)))
    validate_corpus(cases)
    return cases


def note_from_case(case):
    n=dict(case['weekly_note']);n['source_event_ids']=tuple(n['source_event_ids'])
    return FollowupWeeklyNote(**n)


def validate_corpus(cases):
    """Input contract for external authors/reviewers; metadata is self-reported.

    Gold may annotate unfamiliar semantics: only schema, exact spans and source
    time are checked here. It never trains or expands the inference validator.
    """
    if not isinstance(cases,list) or len({c['case_id'] for c in cases}) != len(cases):
        raise ValueError('corpus requires a list of unique case IDs')
    validate_partitions(cases)
    seen_notes=set()
    for case in cases:
        if case['split'] not in ('development','validation','test'):
            raise ValueError('explicit language partition required')
        note=note_from_case(case)
        if note.note_id in seen_notes:
            raise ValueError('duplicate note ID')
        seen_notes.add(note.note_id)
        if case['note'] != dict(note_id=note.note_id,student_id=note.student_id,text=note.text,event_month=note.source_week):
            raise ValueError('language note representations disagree')
        annotation=case['annotation']
        required=('source','reviewer_status','author_id','reviewer_id','exact_evidence_spans',
                  'unknown_assertions','conflicting_assertions','unsupported_claims','disagreements','adjudication')
        if not all(k in annotation for k in required):
            raise ValueError('incomplete annotation provenance')
        status=annotation['reviewer_status']
        if status not in ('unreviewed_synthetic','unreviewed_external','reviewed_external','adjudicated_external'):
            raise ValueError('unknown reviewer status')
        if status in ('reviewed_external','adjudicated_external') and (
                not annotation['reviewer_id'] or annotation['reviewer_id']==annotation['author_id']):
            raise ValueError('independent reviewer identity required')
        if annotation['disagreements'] and status=='adjudicated_external' and not annotation['adjudication']:
            raise ValueError('adjudication metadata required')
        eligible=note.source_week<case['as_of_month'] and note.available_week<=case['as_of_month']
        if case['eligible'] != eligible:
            raise ValueError('incorrect note availability')
        for key in ('gold','structured_observations'):
            payload=case[key]
            if payload is None:
                if eligible and key=='gold':
                    raise ValueError('eligible note requires reviewed or explicitly unreviewed gold')
                continue
            Draft202012Validator(EXTRACTION_SCHEMA).validate(payload)
            if (payload['student_id'],payload['note_id']) != (note.student_id,note.note_id):
                raise ValueError('annotation identity mismatch')
            for fact in payload['observations']:
                start,end=fact['start_offset'],fact['end_offset']
                if (end<=start or note.text[start:end]!=fact['evidence'] or fact['source_month']!=note.source_week):
                    raise ValueError('annotation evidence span or timestamp mismatch')
                if key=='gold' and dict(start=start,end=end,quote=fact['evidence']) not in annotation['exact_evidence_spans']:
                    raise ValueError('annotation lacks exact evidence span')
    return cases


def evaluate_followup(cases,extractor=None):
    validate_corpus(cases)
    calls_before=getattr(extractor,'calls',0);responses_before=getattr(extractor,'responses',0)
    methods={name:[] for name in ('structured_available','note_content_gold','existing_deterministic','missing_notes','corrupted_notes')}
    if extractor is not None:
        methods['prompted_llm']=[]
    for case in cases:
        note=note_from_case(case);cutoff=case['as_of_month']
        for name,records in methods.items():
            record=dict(case_id=case['case_id'],method=name,origin=name)
            if not case['eligible']:
                # Prove timing rejection at the extraction boundary without a call.
                try:
                    validate_extraction(dict(student_id=note.student_id,note_id=note.note_id,observations=[]),note,cutoff)
                except ValueError:
                    record['status']='rejected_before_inference'
                else:
                    raise AssertionError('unavailable note accepted')
            elif name in ('structured_available','note_content_gold'):
                payload=case['structured_observations' if name=='structured_available' else 'gold']
                record.update(status='accepted' if payload is not None else 'unavailable_structured_input',
                    accepted_output=payload or {},raw_output=payload)
            elif name in ('missing_notes','corrupted_notes'):
                record.update(status='accepted',accepted_output=dict(student_id=note.student_id,
                    note_id=note.note_id,observations=[]),raw_output=None,
                    condition='note_removed' if name=='missing_notes' else 'unsupported_corrupted_text')
            else:
                actual=extractor if name=='prompted_llm' else LegacyDeterministicExtractor()
                try:
                    batch=validate_batch(actual.extract(note,cutoff),note,cutoff)
                except (ValueError,RuntimeError,OSError) as exc:
                    record.update(status='quarantined',error=str(exc))
                else:
                    record.update(status='accepted',accepted_output=_batch_payload(batch),validated_batch=asdict(batch))
                if name=='prompted_llm':
                    audit=actual.audit_records[-1]
                    record.update(audit=audit,raw_output=audit.get('raw_output'))
            records.append(record)
    calls=getattr(extractor,'calls',0)-calls_before;responses=getattr(extractor,'responses',0)-responses_before
    status=('unexecuted_not_requested' if extractor is None else 'unexecuted_zero_attempts' if calls==0
            else 'unexecuted_model_unavailable' if responses==0 else
            'executed_mock_software_regression' if extractor.inference_kind=='mock_software_regression' else 'executed_real_model')
    def method_entry(split,name,records):
        selected=[c for c in cases if c['split']==split];ids={c['case_id'] for c in selected}
        records=[r for r in records if r['case_id'] in ids]
        attempts=[a for r in records for a in r.get('audit',{}).get('attempts',[])]
        received=sum(bool(a['model_response_received']) for a in attempts)
        entry=dict(records=records,metrics=None if name=='prompted_llm' and received==0 else evaluate_records(selected,records))
        if name=='prompted_llm':
            entry['inference']=dict(request_attempts=len(attempts),model_responses=received,
                latency_seconds=sum(a['latency_seconds'] for a in attempts),
                status='unexecuted_zero_attempts' if not attempts else 'unexecuted_model_unavailable' if not received
                    else 'executed_mock_software_regression' if extractor.inference_kind=='mock_software_regression' else 'executed_real_model')
        return entry
    return dict(contract='language_followup/v2',corpus_version=CORPUS_VERSION,corpus_identity=digest(cases),
        prompt_version=PROMPT_VERSION,rule_version=RULE_VERSION,evidence_contract=EVIDENCE_CONTRACT,
        llm=dict(status=status,request_attempts=calls,model_responses=responses,
            configuration=extractor.configuration if extractor is not None else None),
        independent_human_validation='incomplete' if not cases or any(
            c['annotation']['reviewer_status'] not in ('reviewed_external','adjudicated_external') for c in cases)
            else 'externally_reported_review_metadata_not_independently_attested',
        independence='distinct synthetic note IDs and declared surface styles; shared development grammar and semantic categories; no independent-template or real-person generalization claim',
        splits={split:dict(n=sum(c['split']==split for c in cases),methods={
            name:method_entry(split,name,records) for name,records in methods.items()})
            for split in ('development','validation','test')},
        limitations=['synthetic prose; no independent human validation unless externally supplied',
            'conservative development grammar; unfamiliar supported facts may still be missed',
            'no prompt or entailment-rule selection using validation/test outcomes'])


def verify_language_report(cases,report):
    validate_corpus(cases)
    if digest(cases)!=report['corpus_identity']:
        raise ValueError('frozen corpus identity mismatch')
    requests=responses=0
    for split,entry in report['splits'].items():
        selected=[c for c in cases if c['split']==split]
        index={c['case_id']:c for c in selected}
        for name,method in entry['methods'].items():
            if len(method['records'])!=len(selected) or {r['case_id'] for r in method['records']}!=set(index):
                raise ValueError('incomplete language record matrix')
            for record in method['records']:
                if record['status']=='accepted' and name in ('prompted_llm','existing_deterministic'):
                    case=index[record['case_id']]
                    batch=validate_extraction(record['accepted_output'],note_from_case(case),case['as_of_month'])
                    if json.loads(json.dumps(asdict(batch)))!=json.loads(json.dumps(record.get('validated_batch',asdict(batch)))):
                        raise ValueError('recorded extraction replay mismatch')
                    if name=='prompted_llm' and _batch_payload(validate_extraction(record['raw_output'],note_from_case(case),case['as_of_month']))!=record['accepted_output']:
                        raise ValueError('raw model response differs from accepted evidence')
                if name=='prompted_llm':
                    attempts=record.get('audit',{}).get('attempts',[])
                    requests+=len(attempts);responses+=sum(bool(a['model_response_received']) for a in attempts)
            if method['metrics'] is not None and evaluate_records(selected,method['records'])!=method['metrics']:
                raise ValueError('independent language score recomputation mismatch')
            if name=='prompted_llm' and method['inference']['model_responses']==0 and method['metrics'] is not None:
                raise ValueError('zero-response language accuracy is unavailable')
    if (requests,responses)!=(report['llm']['request_attempts'],report['llm']['model_responses']):
        raise ValueError('language request/response provenance mismatch')
    return dict(status='recorded_extraction_and_metrics_verified',live_requests=0)


def run_language_followup(output,extractor=None,corpus_path=None):
    cases=json.loads(Path(corpus_path).read_text()) if corpus_path else build_followup_corpus()
    validate_corpus(cases)
    # Publish the full input and protocol before any inference; never overwrite.
    write_exclusive(Path(output)/'frozen_corpus.json',cases)
    write_exclusive(Path(output)/'language_protocol.json',dict(corpus_version=CORPUS_VERSION,
        corpus_identity=digest(cases),prompt_version=PROMPT_VERSION,rule_version=RULE_VERSION,
        independent_annotations='required_for_human_validation_claim; metadata self-reported',
        tuning='development_only; frozen validation/test never expand evidence rules'))
    report=evaluate_followup(cases,extractor)
    write_exclusive(Path(output)/'extraction_report.json',report)
    write_exclusive(Path(output)/'recorded_replay.json',verify_language_report(cases,report))
    return report

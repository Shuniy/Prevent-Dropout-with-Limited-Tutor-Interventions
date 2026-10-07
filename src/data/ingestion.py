"""Read-only UCI school adapter and independently checked baseline lineage."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import fields
from pathlib import Path

from .contracts import (StudentContext, Lineage, VerifiedContext, AuditGroups,
                        UnknownFields, EnvironmentState)

KEY = ('school','sex','age','address','famsize','Pstatus','Medu','Fedu','Mjob','Fjob','reason','nursery','internet')
# Explicit source-specific mapping. No university field is accepted by this adapter.
DIRECT = {'school_id':'school', 'age_years':'age', 'mother_education_code':'Medu',
          'father_education_code':'Fedu', 'mother_job':'Mjob', 'father_job':'Fjob',
          'guardian':'guardian', 'travel_time_category':'traveltime',
          'study_time_category':'studytime', 'past_failures_count':'failures',
          'family_relationship_rating':'famrel', 'health_self_rating':'health',
          'anchor_grade1_0_20':'G1'}
BOOL_MAP = {'rural_residence':('address','R'), 'family_size_gt3':('famsize','GT3'),
            'parents_apart':('Pstatus','A'), 'school_support_existing':('schoolsup','yes'),
            'family_support_existing':('famsup','yes'), 'paid_classes_existing':('paid','yes'),
            'extracurricular':('activities','yes'), 'nursery_attended':('nursery','yes'),
            'higher_education_aspiration':('higher','yes'), 'internet_at_home':('internet','yes')}
STRING_FIELDS = {'school_id','mother_job','father_job','guardian'}
UNKNOWN = ('income_amount','income_currency','verified_economic_disadvantage','observed_school_dropout')
AUDIT = tuple(f.name for f in fields(AuditGroups))
RAW_CATEGORIES = {'school':{'GP','MS'}, 'sex':{'F','M'}, 'address':{'U','R'},
    'famsize':{'LE3','GT3'}, 'Pstatus':{'T','A'},
    'Mjob':{'teacher','health','services','at_home','other'},
    'Fjob':{'teacher','health','services','at_home','other'},
    'reason':{'home','reputation','course','other'}, 'guardian':{'mother','father','other'},
    **{k:{'yes','no'} for k in ('schoolsup','famsup','paid','activities','nursery','higher','internet','romantic')}}
RAW_RANGES = {'age':(15,22), 'Medu':(0,4), 'Fedu':(0,4), 'traveltime':(1,4),
    'studytime':(1,4), 'failures':(0,3), **{k:(1,5) for k in ('famrel','freetime','goout','Dalc','Walc','health')},
    'absences':(0,93), **{k:(0,20) for k in ('G1','G2','G3')}}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path, delimiter=','):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Duplicate/missing CSV header')
        rows = list(reader)
    require(all(None not in r and None not in r.values() for r in rows), 'Malformed CSV width')
    return rows


def integer(value):
    # Baseline pandas writes nullable integer enrichment as 5.0; accept exact integers only.
    f = float(value)
    require(f.is_integer(), f'Not an integer: {value}')
    return int(f)


def boolean(value):
    require(value in ('0','1'), f'Not a binary source recode: {value}')
    return value == '1'


def group_id(row):
    return hashlib.sha256(json.dumps([row[k] for k in KEY], separators=(',',':')).encode()).hexdigest()[:20]


def split_for(group):
    u = int(hashlib.sha256(('split-v1:'+group).encode()).hexdigest()[:12],16) / 16**12
    return 'train' if u < .6 else 'validation' if u < .8 else 'test'


def unique_index(rows, key):
    result = {r[key]:r for r in rows}
    require(len(result) == len(rows), f'Duplicate {key}')
    return result


def context_record(row):
    data = {}
    for f in fields(VerifiedContext):
        value = row[f.name]
        data[f.name] = (None if value == '' else
                       boolean(value) if f.name in BOOL_MAP else
                       value if f.name in STRING_FIELDS else integer(value))
    audit = {k: row[k] if k == 'sex_source' else integer(row[k]) if k == 'disadvantage_proxy_count'
             else boolean(row[k]) for k in AUDIT}
    require(all(row[k] == '' for k in UNKNOWN), 'Unknown fields must remain null')
    require(row.get('financial_need_verified','') == '', 'Financial need is not verified')
    lineage = Lineage(row['student_id'], row.get('source_anchor_student_id',row['student_id']),
        row['source_dataset'], integer(row['source_row']), row['linkage_group_id'], row['split'],
        row['anchor_subject'], row['link_status'], row['record_provenance'])
    return StudentContext(lineage, row['population'], VerifiedContext(**data), AuditGroups(**audit),
                          UnknownFields(None,None,None,None,None))


def validate_and_adapt(tables):
    """Reconstruct source decisions and compare every inherited field, not just counts."""
    raw, groups = {}, defaultdict(lambda: {'portuguese':[], 'math':[]})
    for subject, label in [('portuguese','raw_portuguese'), ('math','raw_math')]:
        rows = tables[label]
        require(len(rows) == (649 if subject == 'portuguese' else 395), 'Original subject row count changed')
        for i, row in enumerate(rows,1):
            require(set(row) == set(RAW_CATEGORIES) | set(RAW_RANGES), 'Unexpected school source fields')
            for k, cats in RAW_CATEGORIES.items():
                require(row[k] in cats, f'Invalid raw category {k}')
            for k,(low,high) in RAW_RANGES.items():
                require(str(integer(row[k])) == row[k] and low <= integer(row[k]) <= high, f'Invalid raw range {k}')
            sid = ('POR' if subject == 'portuguese' else 'MAT') + f'{i:04d}'
            g = group_id(row)
            raw[sid] = {**row, 'source_row':str(i), 'subject':subject, 'record_id':sid,
                        'linkage_group_id':g, 'split':split_for(g), 'course_failure_proxy':str(int(int(row['G3'])<10))}
            groups[g][subject].append(sid)
    refs = unique_index(tables['subject_records_reference'], 'record_id')
    require(refs == raw, 'Subject reference must preserve all original values and lineage')
    safe = {g for g,v in groups.items() if len(v['portuguese']) == len(v['math']) == 1}
    ambiguous = {g for g,v in groups.items() if v['portuguese'] and v['math'] and g not in safe}
    math_only = {sid for g,v in groups.items() if not v['portuguese'] for sid in v['math']}
    require(len(safe)==358 and len(ambiguous)==8 and len(math_only)==25, 'Conservative linkage counts changed')
    require(sum(len(groups[g]['math']) for g in ambiguous)==12, 'Ambiguous math preservation changed')
    anchors = unique_index(tables['student_dataset'],'student_id')
    expected_ids = {sid for sid in raw if sid.startswith('POR')} | math_only
    require(set(anchors)==expected_ids, 'Unexpected anchor set')
    manifest = unique_index(tables['split_manifest'],'student_id')
    require(set(manifest)==expected_ids, 'Split manifest anchor set mismatch')
    contexts = []
    for sid, row in anchors.items():
        c, original = context_record(row), raw[sid]
        group = original['linkage_group_id']
        require(c.lineage.linkage_group_id==group and c.lineage.split==original['split'] and
                c.lineage.source_row==int(original['source_row']) and c.lineage.anchor_subject==original['subject'], 'Anchor lineage mismatch')
        status = 'one_to_one' if group in safe else 'ambiguous_shared' if group in ambiguous else 'single_subject'
        require(row['link_status']==status, 'Linkage status mismatch')
        require(manifest[sid]=={k:row[k] for k in ('student_id','linkage_group_id','split','anchor_subject')}, 'Manifest inheritance mismatch')
        for dest, source in DIRECT.items():
            expected = original[source] if dest in STRING_FIELDS else int(original[source])
            require(getattr(c.context,dest)==expected, f'Source mapping mismatch: {sid}.{dest}')
        for dest,(source, yes) in BOOL_MAP.items():
            require(getattr(c.context,dest)==(original[source]==yes), f'Boolean mapping mismatch {dest}')
        math = raw[groups[group]['math'][0]] if group in safe else original if sid in math_only else None
        require(c.context.math_grade1_0_20==(int(math['G1']) if math else None), 'Missing/incorrect math enrichment')
        a=c.audit; ctx=c.context
        require(a.sex_source==original['sex'] and a.both_parents_education_at_most_2==(ctx.mother_education_code<=2 and ctx.father_education_code<=2)
                and a.no_home_internet==(not ctx.internet_at_home) and a.travel_over_30min==(ctx.travel_time_category>=3), 'Audit proxy mismatch')
        require(a.disadvantage_proxy_count==sum((a.both_parents_education_at_most_2,a.no_home_internet,a.travel_over_30min))
                and a.disadvantage_proxy_group==(a.disadvantage_proxy_count>=2), 'Audit group mismatch')
        require(abs(float(row['learning_gap_initial_assumed'])-max(0,(10-ctx.anchor_grade1_0_20)/10)) < 1e-10, 'Learning gap mapping mismatch')
        contexts.append(c)
    require(Counter(c.lineage.split for c in contexts if c.lineage.anchor_subject=='portuguese')=={'train':388,'validation':125,'test':136}, 'Primary source split changed')
    # Only the documented math-only evaluator blanks are repaired. Everything else must agree.
    outcomes = unique_index(tables['student_outcomes_reference'],'student_id')
    require(set(outcomes)==expected_ids, 'Outcome identity mismatch')
    repaired = []; repair_ids=set()
    for sid,row in outcomes.items():
        r = dict(row); orig=raw[sid]; g=orig['linkage_group_id']
        require(r['anchor_subject']==orig['subject'] and r['observed_school_dropout']=='', 'Outcome semantics mismatch')
        for dest, source in [('anchor_grade2_0_20','G2'), ('anchor_final_grade_0_20','G3'), ('source_total_absences_count','absences'), ('anchor_course_failure_proxy','course_failure_proxy')]:
            require(integer(r[dest])==int(orig[source]), 'Anchor outcome mismatch')
        math=raw[groups[g]['math'][0]] if g in safe else orig if sid in math_only else None
        for dest, source in [('math_grade2_0_20','G2'), ('math_final_grade_0_20','G3'), ('math_total_absences_count','absences')]:
            if sid in math_only and r[dest]=='':
                r[dest]=orig[source]
                repair_ids.add(sid)
            require((integer(r[dest]) if r[dest] else None)==(int(math[source]) if math else None), 'Math outcome mismatch')
        repaired.append(r)
    fixtures=unique_index(tables['synthetic_student_population'],'student_id')
    hidden=unique_index(tables['simulator_hidden_truth'],'student_id')
    require(set(fixtures)==set(hidden) and len(fixtures)==2000, 'Fixture/hidden identity mismatch')
    fixture_contexts, states = [], []
    for sid,row in fixtures.items():
        source=anchors[row['source_anchor_student_id']]
        require(source['anchor_subject']=='portuguese', 'Fixture anchor not in primary population')
        for k,v in source.items():
            if k not in ('student_id','record_provenance'):
                require(row[k]==v, f'Descendant inheritance mismatch: {sid}.{k}')
        c=context_record(row); h=hidden[sid]
        require(sid.startswith('SYN') and row['enrolled_initial_assumed']=='1' and row['weeks_since_offer']=='0' and row['support_sessions_completed']=='0', 'Invalid initial fixture')
        annual=float(h['annual_dropout_probability_assumed']); weekly=float(h['constant_weekly_hazard_assumed'])
        require(0<=annual<=1 and abs(weekly-(1-(1-annual)**(1/36)))<1e-9, 'Static diagnostic hazard invalid')
        require(h['provenance']=='generated_scenario_truth_not_observed', 'Hidden truth provenance mismatch')
        boolean(h['dropout_draw_at_static_annual_hazard_assumed'])
        state=EnvironmentState(sid,0,True,float(row['initial_attendance_fraction_assumed']),
            float(row['initial_engagement_assumed']),float(row['learning_gap_initial_assumed']),
            float(h['response_tendency_assumed']),boolean(h['financial_barrier_latent_assumed']),(),0,0)
        fixture_contexts.append(c); states.append(state)
    require(Counter(c.lineage.split for c in fixture_contexts)=={'train':1200,'validation':400,'test':400}, 'Fixture splits changed')
    all_groups=defaultdict(set)
    for c in contexts+fixture_contexts:
        all_groups[c.lineage.linkage_group_id].add(c.lineage.split)
    require(all(len(v)==1 for v in all_groups.values()), 'Linkage group crosses splits')
    report={'source_subject_rows':len(raw), 'primary_anchors':sum(c.lineage.anchor_subject=='portuguese' for c in contexts), 'sensitivity_anchors':len(contexts),
        'safe_links':len(safe), 'ambiguous_shared_keys':len(ambiguous),
        'ambiguous_math_reference_rows':sum(len(groups[g]['math']) for g in ambiguous),
        'math_only_outcome_rows_repaired':len(repair_ids), 'fixture_descendants':len(states),
        'represented_fixture_anchors':len({c.lineage.source_anchor_student_id for c in fixture_contexts}),
        'represented_fixture_groups':len({c.lineage.linkage_group_id for c in fixture_contexts}),
        'primary_split_counts':dict(Counter(c.lineage.split for c in contexts if c.lineage.anchor_subject=='portuguese')),
        'fixture_split_counts':dict(Counter(c.lineage.split for c in fixture_contexts)),
        'lineage_crossings':0, 'inherited_field_mismatches':0, 'unknown_fields_preserved':True,
        'source_references_exact':True, 'stage':'1', 'sequential_simulator_executed':False}
    return contexts,fixture_contexts,states,repaired,report

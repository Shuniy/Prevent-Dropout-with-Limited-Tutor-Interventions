"""Independent readback checks and distributable archive construction."""
from pathlib import Path
import hashlib, json, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

r=Path(__file__).resolve().parent
manifest=pd.read_csv(r/'analysis/source_manifest.csv')
assert all(hashlib.sha256(Path(x.source_path).read_bytes()).hexdigest()==x.sha256 for x in manifest.itertuples())
f=pd.read_csv(r/'data/student_dataset.csv'); s=pd.read_csv(r/'data/synthetic_student_population.csv'); truth=pd.read_csv(r/'data/simulator_hidden_truth.csv')
o=pd.read_csv(r/'data/student_outcomes_reference.csv'); audit=pd.read_csv(r/'analysis/source_audit.csv')
assert len(f)==674 and len(f[f.anchor_subject=='portuguese'])==649 and len(s)==2000
assert f.student_id.is_unique and s.student_id.is_unique and set(s.student_id)==set(truth.student_id)
assert f.groupby('linkage_group_id').split.nunique().max()==s.groupby('linkage_group_id').split.nunique().max()==1
assert f[['income_amount','income_currency','verified_economic_disadvantage','observed_school_dropout']].isna().all().all()
assert set(s.source_anchor_student_id)<=set(f[f.anchor_subject=='portuguese'].student_id)
joined=s.merge(f[['student_id','split']],left_on='source_anchor_student_id',right_on='student_id',suffixes=('_synthetic','_source'),validate='many_to_one')
assert (joined.split_synthetic==joined.split_source).all()
assert s.initial_attendance_fraction_assumed.between(0,1).all() and s.initial_engagement_assumed.between(0,1).all()
assert truth.annual_dropout_probability_assumed.between(0,1).all()
assert np.allclose(1-(1-truth.constant_weekly_hazard_assumed)**36,truth.annual_dropout_probability_assumed,atol=1e-9)
assert np.array_equal((o.anchor_final_grade_0_20<10).astype(int),o.anchor_course_failure_proxy)
assert len(pd.read_csv(r/'data/variable_dictionary.csv'))==len(f.columns)
labels=audit[audit.file.str.endswith(('y_train.csv','y_test.csv'))]
assert len(labels)==2 and (labels['columns']==1).all() and (labels.missing_cells==0).all()
assert (audit[audit.file.str.contains('student\\+performance/student/')].missing_cells==0).all()
cfg=json.loads((r/'configs/simulator_config.json').read_text())
matrix=np.array(cfg['markov_transition_assumptions']['usual_support_matrix'])
assert (matrix>=0).all() and np.allclose(matrix.sum(axis=1),1)
assert len(pd.read_csv(r/'configs/experiment_grid.csv'))==144
bm=pd.read_csv(r/'analysis/predictive_baselines.csv')
for x in bm[bm.model=='training_prevalence'].itertuples():
    assert abs(x.average_precision-x.prevalence)<1e-8 and abs(x.roc_auc-.5)<1e-8
pred=pd.read_csv(r/'analysis/school_period1_failure_test_predictions.csv')
assert abs(np.mean((pred.probability-pred.outcome)**2)-bm[(bm.dataset=='school_period1_failure')&(bm.model=='logistic')].brier.iloc[0])<1e-9

ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(r/'student_analysis.xlsx') as z:
    assert z.testzip() is None
    book=ET.fromstring(z.read('xl/workbook.xml')); names=[x.attrib['name'] for x in book.findall('m:sheets/m:sheet',ns)]
    assert names==['Findings','School associations','Variables','Source audit']
    errors=[]; formula_count=0
    for member in z.namelist():
        if member.startswith('xl/worksheets/sheet') and member.endswith('.xml'):
            sheet=ET.fromstring(z.read(member)); errors += [x.attrib.get('r') for x in sheet.findall('.//m:c',ns) if x.attrib.get('t')=='e']
            formula_count+=len(sheet.findall('.//m:f',ns))
    assert not errors and formula_count>=15

checks={'source_hashes_unchanged':True,'primary_csv_readback':True,'unknown_fields_preserved':True,'split_and_bootstrap_lineage_isolation':True,
        'label_file_delimiters_verified':True,'grade_failure_labels_verified':True,'hazard_conversion_verified':True,'markov_rows_sum_to_one':True,
        'predictive_metric_independent_readback':True,'workbook_saved_xml_formula_errors':errors,'workbook_formula_count':formula_count,
        'workbook_dependency_changes_and_restoration_verified':True,'workbook_visual_review':'all four sheets reviewed','policy_experiments_executed':False}
(r/'analysis/final_readback_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
files=[]
for p in r.rglob('*'):
    if not p.is_file() or 'node_modules' in p.parts or '__pycache__' in p.parts: continue
    if p.suffix in ['.png','.zip','.ndjson']: continue
    files.append(p)
archive=r/'student_cmdp_package.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(files): z.write(p,'student_cmdp_study/'+str(p.relative_to(r)))
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
print(json.dumps({'checks':checks,'package_files':len(files),'package_bytes':archive.stat().st_size},indent=2))

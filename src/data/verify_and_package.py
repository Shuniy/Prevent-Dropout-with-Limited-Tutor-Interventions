"""Read-only data validation; optional workbook XML checks and bounded packaging."""
from pathlib import Path
import argparse
import json
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from reproducibility import require, preflight, verify_sources, check_artifacts, make_package


def validate_data(r):
    r = Path(r)
    passed = []
    def check(condition, description):
        require(condition, 'Data validation failed: ' + description)
        passed.append(description)
    f=pd.read_csv(r/'data/student_dataset.csv'); s=pd.read_csv(r/'data/synthetic_student_population.csv'); truth=pd.read_csv(r/'data/simulator_hidden_truth.csv')
    o=pd.read_csv(r/'data/student_outcomes_reference.csv'); audit=pd.read_csv(r/'analysis/source_audit.csv')
    check(len(f)==674 and len(f[f.anchor_subject=='portuguese'])==649 and len(s)==2000, "len(f)==674 and len(f[f.anchor_subject=='portuguese'])==649 and len(s)==2000")
    check(f.student_id.is_unique and s.student_id.is_unique and set(s.student_id)==set(truth.student_id), 'f.student_id.is_unique and s.student_id.is_unique and set(s.student_id)==set(truth.student_id)')
    check(f.groupby('linkage_group_id').split.nunique().max()==s.groupby('linkage_group_id').split.nunique().max()==1, "f.groupby('linkage_group_id').split.nunique().max()==s.groupby('linkage_group_id').split.nunique().max()==1")
    check(f[['income_amount','income_currency','verified_economic_disadvantage','observed_school_dropout']].isna().all().all(), "f[['income_amount','income_currency','verified_economic_disadvantage','observed_school_dropout']].isna().all().all()")
    check(set(s.source_anchor_student_id)<=set(f[f.anchor_subject=='portuguese'].student_id), "set(s.source_anchor_student_id)<=set(f[f.anchor_subject=='portuguese'].student_id)")
    joined=s.merge(f[['student_id','split']],left_on='source_anchor_student_id',right_on='student_id',suffixes=('_synthetic','_source'),validate='many_to_one')
    check((joined.split_synthetic==joined.split_source).all(), '(joined.split_synthetic==joined.split_source).all()')
    check(s.initial_attendance_fraction_assumed.between(0,1).all() and s.initial_engagement_assumed.between(0,1).all(), 's.initial_attendance_fraction_assumed.between(0,1).all() and s.initial_engagement_assumed.between(0,1).all()')
    check(truth.annual_dropout_probability_assumed.between(0,1).all(), 'truth.annual_dropout_probability_assumed.between(0,1).all()')
    check(np.allclose(1-(1-truth.constant_weekly_hazard_assumed)**36,truth.annual_dropout_probability_assumed,atol=1e-9), 'np.allclose(1-(1-truth.constant_weekly_hazard_assumed)**36,truth.annual_dropout_probability_assumed,atol=1e-9)')
    check(np.array_equal((o.anchor_final_grade_0_20<10).astype(int),o.anchor_course_failure_proxy), 'np.array_equal((o.anchor_final_grade_0_20<10).astype(int),o.anchor_course_failure_proxy)')
    check(len(pd.read_csv(r/'data/variable_dictionary.csv'))==len(f.columns), "len(pd.read_csv(r/'data/variable_dictionary.csv'))==len(f.columns)")
    labels=audit[audit.file.str.endswith(('y_train.csv','y_test.csv'))]
    check(len(labels)==2 and (labels['columns']==1).all() and (labels.missing_cells==0).all(), "len(labels)==2 and (labels['columns']==1).all() and (labels.missing_cells==0).all()")
    check((audit[audit.file.str.contains('student\\+performance/student/')].missing_cells==0).all(), "(audit[audit.file.str.contains('student\\\\+performance/student/')].missing_cells==0).all()")
    cfg=json.loads((r/'configs/simulator_config.json').read_text())
    matrix=np.array(cfg['markov_transition_assumptions']['usual_support_matrix'])
    check((matrix>=0).all() and np.allclose(matrix.sum(axis=1),1), '(matrix>=0).all() and np.allclose(matrix.sum(axis=1),1)')
    check(len(pd.read_csv(r/'configs/experiment_grid.csv'))==144, "len(pd.read_csv(r/'configs/experiment_grid.csv'))==144")
    bm=pd.read_csv(r/'analysis/predictive_baselines.csv')
    for x in bm[bm.model=='training_prevalence'].itertuples():
        check(abs(x.average_precision-x.prevalence)<1e-8 and abs(x.roc_auc-.5)<1e-8, 'abs(x.average_precision-x.prevalence)<1e-8 and abs(x.roc_auc-.5)<1e-8')
    pred=pd.read_csv(r/'analysis/school_period1_failure_test_predictions.csv')
    check(abs(np.mean((pred.probability-pred.outcome)**2)-bm[(bm.dataset=='school_period1_failure')&(bm.model=='logistic')].brier.iloc[0])<1e-9, "abs(np.mean((pred.probability-pred.outcome)**2)-bm[(bm.dataset=='school_period1_failure')&(bm.model=='logistic')].brier.iloc[0])<1e-9")

    # Compare every inherited field and explicit unknown against its anchor.
    anchors = f.set_index('student_id').loc[s.source_anchor_student_id].reset_index(drop=True)
    inherited = [c for c in f if c not in {'student_id', 'record_provenance'}]
    pd.testing.assert_frame_equal(s[inherited].reset_index(drop=True), anchors[inherited], check_dtype=False)
    passed.append('all synthetic inherited fields match source anchors, including nulls')
    split_manifest = pd.read_csv(r/'data/split_manifest.csv')
    pd.testing.assert_frame_equal(split_manifest, f[list(split_manifest.columns)])
    passed.append('split manifest equals prepared source records')
    check(f[f.anchor_subject == 'portuguese'].split.value_counts().to_dict() == {'train': 388, 'validation': 125, 'test': 136}, 'primary split counts')
    return {'status': 'passed', 'checks_passed': len(passed), 'checks': passed,
            'source_csv_count': len(audit), 'primary_rows': len(f), 'synthetic_rows': len(s)}


def validate_workbook(path):
    """Optional saved-XML inspection only; no claims of recalculation or rendering."""
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None, 'Workbook archive is corrupt')
        book = ET.fromstring(z.read('xl/workbook.xml'))
        names = [x.attrib['name'] for x in book.findall('m:sheets/m:sheet', ns)]
        require(names == ['Findings', 'School associations', 'Variables', 'Source audit'], 'Unexpected workbook sheets')
        errors, formulas = [], 0
        for member in z.namelist():
            if member.startswith('xl/worksheets/sheet') and member.endswith('.xml'):
                sheet = ET.fromstring(z.read(member))
                errors.extend(x.attrib.get('r') for x in sheet.findall('.//m:c', ns) if x.attrib.get('t') == 'e')
                formulas += len(sheet.findall('.//m:f', ns))
        require(not errors and formulas >= 15, 'Workbook formula structure check failed')
    return {'status': 'passed', 'inspection': 'saved_xml_only', 'formula_count': formulas,
            'formula_errors': errors, 'recalculation': 'not_performed', 'visual_review': 'not_performed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--research-plan', type=Path, required=True)
    parser.add_argument('--workbook', type=Path, help='Optional existing workbook, checked separately')
    parser.add_argument('--archive', type=Path, help='Optional new archive outside the completed output')
    args = parser.parse_args()
    try:
        check_artifacts(args.output_root)
        root, doc, _, cfg, _ = preflight(args.source_root, args.research_plan, args.output_root/'configs/raw_sources.v1.json')
        result = validate_data(args.output_root)
        result['source_identity'] = verify_sources(root, doc, cfg)
        result['workbook_checks'] = validate_workbook(args.workbook) if args.workbook else {'status': 'not_requested'}
        if args.archive:
            result['archive'] = make_package(args.output_root, args.archive)
    except (ValueError, OSError, KeyError, AssertionError, zipfile.BadZipFile) as e:
        parser.exit(1, f'Validation failed: {e}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

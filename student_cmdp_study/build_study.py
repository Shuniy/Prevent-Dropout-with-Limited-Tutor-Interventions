"""Reproducible audit and CSV preparation. Source files are never modified."""
from pathlib import Path
import argparse, hashlib, io, json, math, sys, zipfile
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path('/Users/shuniy/Documents/projects/school-dropout')
DOC = HERE.parents[1] / 'sources/school_dropout_research_plan.md'
SEED = 20261006
KEY = ['school','sex','age','address','famsize','Pstatus','Medu','Fedu','Mjob','Fjob','reason','nursery','internet']
URL_SCHOOL = 'https://archive.ics.uci.edu/dataset/320/student+performance'
URL_HE = 'https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name, x):
    (HERE/name).write_text(json.dumps(x, indent=2, ensure_ascii=False, default=lambda x: x.item() if isinstance(x,np.generic) else str(x))+'\n')
def save(name, d): d.to_csv(HERE/name,index=False,float_format='%.10g')
def key_hash(row):
    return hashlib.sha256(json.dumps([str(row[c]) for c in KEY],separators=(',',':')).encode()).hexdigest()[:20]
def split_for(g):
    u=int(hashlib.sha256(('split-v1:'+g).encode()).hexdigest()[:12],16)/16**12
    return 'train' if u<.6 else ('validation' if u<.8 else 'test')
def clean_read(p):
    # All supplied tabular files use comma or semicolon. Sniffer's auto-detection
    # misidentifies letters in the single-column 'failed' header as delimiters.
    with p.open(encoding='utf-8-sig') as f: header=f.readline()
    sep=';' if header.count(';')>header.count(',') else ','
    d=pd.read_csv(p,sep=sep,encoding='utf-8-sig')
    d.columns=d.columns.str.lstrip('\ufeff').str.strip()
    return d
def wilson(k,n):
    if not n: return (None,None)
    z=1.95996398454; a=(k/n+z*z/(2*n))/(1+z*z/n)
    b=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return (a-b,a+b)
def sigmoid(x): return 1/(1+np.exp(-np.clip(x,-35,35)))

def design(train, others, num, cat):
    """Learn numeric medians/scales and one-hot vocabulary on training only."""
    median=train[num].median(); scale=train[num].std(ddof=0).replace(0,1)
    mean=train[num].fillna(median).mean()
    vocab={c: sorted(train[c].fillna('unknown').astype(str).unique()) for c in cat}
    labels=['intercept']+num+[c+'='+v for c in cat for v in vocab[c][1:]]
    def convert(d):
        arrays=[np.ones((len(d),1)),((d[num].fillna(median)-mean)/scale).to_numpy(float)]
        for c in cat:
            vals=d[c].fillna('unknown').astype(str)
            arrays += [(vals==v).to_numpy(float).reshape(-1,1) for v in vocab[c][1:]]
        return np.concatenate(arrays,axis=1)
    return [convert(d) for d in [train]+others],labels,{'numeric_median':median.to_dict(),'numeric_mean':mean.to_dict(),'numeric_scale':scale.to_dict(),'categories':vocab,'unseen_category_policy':'all-zero indicator (reference); count unknowns at deployment'}

def logit_fit(X,y,lam):
    b=np.zeros(X.shape[1]); b[0]=math.log((y.mean()+1e-5)/(1-y.mean()+1e-5))
    reg=np.eye(len(b))*lam; reg[0,0]=1e-8
    def loss(b): return float(np.logaddexp(0,X@b).sum()-y@(X@b)+.5*b@reg@b)
    for _ in range(80):
        p=sigmoid(X@b); w=np.maximum(p*(1-p),1e-8)
        step=np.linalg.solve(X.T@(w[:,None]*X)+reg,X.T@(p-y)+reg@b)
        old=loss(b); rate=1.
        while rate>1e-7 and loss(b-rate*step)>old: rate*=.5
        b-=rate*step
        if np.max(np.abs(rate*step))<1e-7: break
    return b

def metrics(y,p):
    y=np.asarray(y,int); p=np.asarray(p,float); n=len(y); pos=int(y.sum())
    order=np.argsort(-p,kind='stable'); yy=y[order]; pp=p[order]
    ends=np.r_[np.flatnonzero(np.diff(pp)!=0),n-1]
    tp=np.cumsum(yy)[ends]; precision=tp/(ends+1); recall=tp/max(pos,1)
    ap=float(np.sum(np.diff(np.r_[0,recall])*precision)) if pos else None
    ranks=pd.Series(p).rank(method='average').to_numpy()
    auc=float((ranks[y==1].sum()-pos*(pos+1)/2)/(pos*(n-pos))) if 0<pos<n else None
    bins=np.minimum((p*10).astype(int),9); ece=0.
    for k in np.unique(bins):
        idx=bins==k; ece+=idx.mean()*abs(y[idx].mean()-p[idx].mean())
    k=max(1,math.ceil(.1*n)); cutoff=np.sort(p)[-k]
    above=p>cutoff; tied=p==cutoff; frac=(k-above.sum())/max(tied.sum(),1)
    expected_tp=float(y[above].sum()+frac*y[tied].sum())
    return {'n':n,'positive_n':pos,'prevalence':pos/n,'average_precision':ap,'roc_auc':auc,
            'brier':float(np.mean((p-y)**2)),'log_loss':float(-np.mean(y*np.log(np.clip(p,1e-10,1))+(1-y)*np.log(np.clip(1-p,1e-10,1)))),
            'ece_10_equal_width':float(ece),'review_capacity_n':k,'recall_at_10pct':expected_tp/max(pos,1),
            'precision_at_10pct':expected_tp/k,'mean_prediction':float(p.mean())}

def baseline(d,ycol,num,cat,name):
    parts=[d[d.split==s].copy() for s in ['train','validation','test']]
    xs,labels,transform=design(parts[0],parts[1:],num,cat)
    ys=[part[ycol].to_numpy(int) for part in parts]
    candidates=[]
    for lam in [.1,1.,10.,100.]:
        b=logit_fit(xs[0],ys[0],lam); mv=metrics(ys[1],sigmoid(xs[1]@b))
        candidates.append((mv['log_loss'],lam,b))
    _,lam,b=min(candidates,key=lambda a:a[0])
    p=sigmoid(xs[2]@b); out=[]
    for model,pr in [('training_prevalence',np.full(len(p),ys[0].mean())),('logistic',p)]:
        out.append({'dataset':name,'model':model,'selected_l2_sum_loss':lam if model=='logistic' else None,**metrics(ys[2],pr)})
    pred=pd.DataFrame({'record_id':parts[2].record_id.to_numpy(),'linkage_group_id':parts[2].linkage_group_id.to_numpy(),'outcome':ys[2],'probability':p})
    save('analysis/'+name+'_test_predictions.csv',pred)
    save('analysis/'+name+'_logistic_coefficients.csv',pd.DataFrame({'encoded_feature':labels,'coefficient':b}))
    dump('analysis/'+name+'_preprocessing.json',{'features_numeric':num,'features_categorical':cat,'chosen_l2':lam,'training_only_transform':transform,'validation_candidates':[{'l2':a[1],'validation_log_loss':a[0]} for a in candidates]})
    # Cluster bootstrap linked profiles so shared identities do not become independent samples.
    groups=pred.groupby('linkage_group_id').indices; keys=list(groups); rng=np.random.default_rng(SEED+21)
    reps=[]
    for _ in range(500):
        idx=np.concatenate([groups[g] for g in rng.choice(keys,len(keys),replace=True)])
        reps.append(metrics(ys[2][idx],p[idx]))
    intervals=[]
    for metric in ['average_precision','roc_auc','brier','recall_at_10pct']:
        vals=[x[metric] for x in reps if x[metric] is not None]
        intervals.append({'dataset':name,'metric':metric,'estimate':metrics(ys[2],p)[metric],'lower_95':np.quantile(vals,.025),'upper_95':np.quantile(vals,.975),'bootstrap_reps':500,'unit':'linkage_group_id'})
    return out,intervals

def main():
    for folder in ['data','analysis','configs','support']: (HERE/folder).mkdir(parents=True,exist_ok=True)
    inputs=sorted([p for p in ROOT.rglob('*') if p.is_file() and p.name!='.DS_Store'])+[DOC]
    before={str(p):sha(p) for p in inputs}
    manifest=[{'source_path':str(p),'relative_path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'project_reference/'+p.name,'sha256':before[str(p)],'bytes':p.stat().st_size} for p in inputs]
    save('analysis/source_manifest.csv',pd.DataFrame(manifest))
    audit=[]; fields=[]; frames={}
    for p in sorted(ROOT.rglob('*.csv')):
        d=clean_read(p); rel=str(p.relative_to(ROOT)); frames[rel]=d
        audit.append({'file':rel,'rows':len(d),'columns':len(d.columns),'missing_cells':int(d.isna().sum().sum()),'exact_duplicate_rows':int(d.duplicated().sum())})
        for c in d:
            numeric=pd.api.types.is_numeric_dtype(d[c])
            fields.append({'file':rel,'variable':c,'dtype':str(d[c].dtype),'missing_n':int(d[c].isna().sum()),'unique_n':int(d[c].nunique()),'min':d[c].min() if numeric else None,'max':d[c].max() if numeric else None,'category_examples':'; '.join(map(str,d[c].dropna().unique()[:12])) if not numeric else ''})
    save('analysis/source_audit.csv',pd.DataFrame(audit)); save('analysis/source_variable_profile.csv',pd.DataFrame(fields))
    archive=[]
    for p in sorted(ROOT.rglob('*.zip')):
        with zipfile.ZipFile(p) as z:
            for member in z.infolist():
                if member.is_dir(): continue
                payload=z.read(member.filename); h=hashlib.sha256(payload).hexdigest()
                archive.append({'archive':str(p.relative_to(ROOT)),'member':member.filename,'bytes':len(payload),'sha256':h,'matching_uncompressed_files':'; '.join(x['relative_path'] for x in manifest if x['sha256']==h and not x['relative_path'].endswith('.zip'))})
    save('analysis/archive_inventory.csv',pd.DataFrame(archive))
    m=frames['student+performance/student/student-mat.csv'].copy(); p=frames['student+performance/student/student-por.csv'].copy()
    for d,subject in [(m,'math'),(p,'portuguese')]:
        d['source_row']=np.arange(1,len(d)+1); d['subject']=subject
        d['record_id']=[('MAT' if subject=='math' else 'POR')+f'{i:04d}' for i in d.source_row]
        d['linkage_group_id']=d.apply(key_hash,axis=1); d['split']=d.linkage_group_id.map(split_for)
        d['course_failure_proxy']=(d.G3<10).astype(int)
    counts=m.groupby('linkage_group_id').size().rename('math_rows').to_frame().join(p.groupby('linkage_group_id').size().rename('portuguese_rows'),how='outer').fillna(0).astype(int)
    counts['link_status']=np.where((counts.math_rows==1)&(counts.portuguese_rows==1),'one_to_one',np.where((counts.math_rows>0)&(counts.portuguese_rows>0),'ambiguous_shared','single_subject'))
    save('analysis/linkage_audit.csv',counts.reset_index())
    long=pd.concat([p,m],ignore_index=True)
    save('data/subject_records_reference.csv',long)
    safe=set(counts.index[counts.link_status=='one_to_one']); math_only=m[~m.linkage_group_id.isin(p.linkage_group_id)].copy()
    anchors=pd.concat([p,math_only],ignore_index=True)
    q=m[m.linkage_group_id.isin(safe)].set_index('linkage_group_id')
    features=pd.DataFrame({'student_id':anchors.record_id,'linkage_group_id':anchors.linkage_group_id,'split':anchors.split,
       'source_dataset':'uci_student_performance','population':'portugal_secondary_school','anchor_subject':anchors.subject,
       'source_row':anchors.source_row,'school_id':anchors.school,'record_provenance':'observed_source_with_derived_features',
       'link_status':anchors.linkage_group_id.map(counts.link_status),'age_years':anchors.age,'sex_source':anchors.sex,
       'rural_residence':(anchors.address=='R').astype(int),'family_size_gt3':(anchors.famsize=='GT3').astype(int),
       'parents_apart':(anchors.Pstatus=='A').astype(int),'mother_education_code':anchors.Medu,'father_education_code':anchors.Fedu,
       'mother_job':anchors.Mjob,'father_job':anchors.Fjob,'guardian':anchors.guardian,'travel_time_category':anchors.traveltime,
       'study_time_category':anchors.studytime,'past_failures_count':anchors.failures,'school_support_existing':(anchors.schoolsup=='yes').astype(int),
       'family_support_existing':(anchors.famsup=='yes').astype(int),'paid_classes_existing':(anchors.paid=='yes').astype(int),
       'extracurricular':(anchors.activities=='yes').astype(int),'nursery_attended':(anchors.nursery=='yes').astype(int),
       'higher_education_aspiration':(anchors.higher=='yes').astype(int),'internet_at_home':(anchors.internet=='yes').astype(int),
       'family_relationship_rating':anchors.famrel,'health_self_rating':anchors.health,
       'anchor_grade1_0_20':anchors.G1,'math_grade1_0_20':anchors.linkage_group_id.map(q.G1),
       'income_amount':np.nan,'income_currency':None,'verified_economic_disadvantage':np.nan,'observed_school_dropout':np.nan})
    # The math-only anchors retain their own observed mathematics grade.
    features.loc[features.anchor_subject=='math','math_grade1_0_20']=features.loc[features.anchor_subject=='math','anchor_grade1_0_20']
    features['both_parents_education_at_most_2']=((features.mother_education_code<=2)&(features.father_education_code<=2)).astype(int)
    features['no_home_internet']=1-features.internet_at_home
    features['travel_over_30min']=(features.travel_time_category>=3).astype(int)
    features['disadvantage_proxy_count']=features[['both_parents_education_at_most_2','no_home_internet','travel_over_30min']].sum(axis=1)
    features['disadvantage_proxy_group']=(features.disadvantage_proxy_count>=2).astype(int)
    features['learning_gap_initial_assumed']=np.clip((10-features.anchor_grade1_0_20)/10,0,1)
    save('data/student_dataset.csv',features)
    outcomes=pd.DataFrame({'student_id':anchors.record_id,'anchor_subject':anchors.subject,'anchor_grade2_0_20':anchors.G2,
        'anchor_final_grade_0_20':anchors.G3,'anchor_course_failure_proxy':anchors.course_failure_proxy,'source_total_absences_count':anchors.absences,
        'math_grade2_0_20':anchors.linkage_group_id.map(q.G2),'math_final_grade_0_20':anchors.linkage_group_id.map(q.G3),
        'math_total_absences_count':anchors.linkage_group_id.map(q.absences),'observed_school_dropout':np.nan})
    save('data/student_outcomes_reference.csv',outcomes)
    save('data/split_manifest.csv',features[['student_id','linkage_group_id','split','anchor_subject']])
    # University data remains an independent benchmark, never merged with the children.
    he=frames['Student_Dropout_rate.csv'].copy()
    he['record_id']=[f'HE{i:05d}' for i in range(1,len(he)+1)]
    he['linkage_group_id']=he.apply(lambda r: hashlib.sha256(json.dumps([str(r[c]) for c in he.columns if c not in ['record_id','Target']],separators=(',',':')).encode()).hexdigest()[:20],axis=1)
    he['split']=he.linkage_group_id.map(split_for)
    he_num=['Age at enrollment','Application order','Previous qualification (grade)','Admission grade','Unemployment rate','Inflation rate','GDP']
    he_cat=[c for c in frames['Student_Dropout_rate.csv'] if not c.startswith('Curricular units') and c not in he_num+['Target']]
    save('data/higher_ed_enrollment_features.csv',he[['record_id','linkage_group_id','split']+he_num+he_cat])
    save('data/higher_ed_outcomes_reference.csv',he[['record_id','Target']+[c for c in he if c.startswith('Curricular units')]])
    # Resolved cases only: Enrolled students are not labelled successful completion.
    he_resolved=he[he.Target!='Enrolled'].copy(); he_resolved['dropout']=(he_resolved.Target=='Dropout').astype(int)
    pnum=['age','Medu','Fedu','traveltime','studytime','failures','famrel','health']
    pcat=['school','sex','address','famsize','Pstatus','Mjob','Fjob','guardian','schoolsup','famsup','paid','activities','nursery','higher','internet']
    rows=[]; cis=[]
    for d,y,num,cat,name in [(p,'course_failure_proxy',pnum,pcat,'school_context_failure'),(p,'course_failure_proxy',pnum+['G1'],pcat,'school_period1_failure'),(he_resolved,'dropout',he_num,he_cat,'higher_ed_enrollment_resolved_dropout'),(he_resolved,'dropout',he_num,[c for c in he_cat if c not in ['Debtor','Tuition fees up to date','Scholarship holder']],'higher_ed_without_financial_status')]:
        a,b=baseline(d,y,num,cat,name); rows+=a; cis+=b
    save('analysis/predictive_baselines.csv',pd.DataFrame(rows)); save('analysis/predictive_intervals.csv',pd.DataFrame(cis))
    summaries=[]
    for d,subject in [(p,'portuguese'),(m,'math')]:
        d=d.copy(); d['low_parent_education']=((d.Medu<=2)&(d.Fedu<=2)).astype(int)
        d['digital_exclusion']=(d.internet=='no').astype(int); d['long_commute']=(d.traveltime>=3).astype(int)
        d['disadvantage_proxy_group']=((d.low_parent_education+d.digital_exclusion+d.long_commute)>=2).astype(int)
        d['prior_failure']=(d.failures>0).astype(int)
        for c in ['low_parent_education','digital_exclusion','long_commute','disadvantage_proxy_group','prior_failure','sex','school','schoolsup','famsup']:
            for val,g in d.groupby(c):
                k=int(g.course_failure_proxy.sum()); n=len(g); lo,hi=wilson(k,n)
                summaries.append({'subject':subject,'variable':c,'group':val,'n':n,'course_failure_n':k,'course_failure_rate':k/n,'wilson_lower_95':lo,'wilson_upper_95':hi,'mean_grade1':g.G1.mean(),'mean_final_grade':g.G3.mean(),'mean_absences_full_period':g.absences.mean()})
    save('analysis/school_subgroup_associations.csv',pd.DataFrame(summaries))
    hegroups=[]
    for c in ['Debtor','Tuition fees up to date','Scholarship holder','Gender']:
        for val,g in he.groupby(c):
            hegroups.append({'variable':c,'group':val,'all_n':len(g),'dropout_n':int((g.Target=='Dropout').sum()),'graduate_n':int((g.Target=='Graduate').sum()),'enrolled_n':int((g.Target=='Enrolled').sum()),'dropout_fraction_all':float((g.Target=='Dropout').mean())})
    save('analysis/higher_ed_subgroup_associations.csv',pd.DataFrame(hegroups))
    # Synthetic reset fixtures keep observation and hidden truth separate.
    rng=np.random.default_rng(SEED); sampled=[]
    for split,n in [('train',1200),('validation',400),('test',400)]:
        pool=features[(features.split==split)&(features.anchor_subject=='portuguese')]
        draw=pool.iloc[rng.integers(0,len(pool),n)].copy(); sampled.append(draw)
    syn=pd.concat(sampled,ignore_index=True).rename(columns={'student_id':'source_anchor_student_id'})
    syn.insert(0,'student_id',[f'SYN{i:05d}' for i in range(1,len(syn)+1)])
    syn['record_provenance']='bootstrap_observed_profile_with_assumed_initial_dynamics'
    gap=syn.learning_gap_initial_assumed.to_numpy()
    syn['initial_attendance_fraction_assumed']=np.clip(.90-.12*gap-.06*syn.travel_over_30min.to_numpy()+rng.normal(0,.04,len(syn)),.50,.99)
    syn['initial_engagement_assumed']=np.clip(.80-.25*gap+rng.normal(0,.08,len(syn)),.1,.99)
    syn['weeks_since_offer']=0; syn['support_sessions_completed']=0
    syn['enrolled_initial_assumed']=1; syn['financial_need_verified']=np.nan
    save('data/synthetic_student_population.csv',syn)
    # A scenario effect model, not an estimate from the failure labels.
    def hazard_score(d):
        return .9*d.learning_gap_initial_assumed.to_numpy()+.5*d.travel_over_30min.to_numpy()+.3*d.no_home_internet.to_numpy()+.4*(d.past_failures_count.to_numpy()>0)
    tr=features[(features.split=='train')&(features.anchor_subject=='portuguese')]; ztr=hazard_score(tr)
    l,h=-15.,5.
    for _ in range(100):
        mid=(l+h)/2
        if sigmoid(mid+ztr).mean()<.1: l=mid
        else: h=mid
    intercept=(l+h)/2; annual=sigmoid(intercept+hazard_score(syn))
    latent=pd.DataFrame({'student_id':syn.student_id,'annual_dropout_probability_assumed':annual,'constant_weekly_hazard_assumed':1-(1-annual)**(1/36),
        'response_tendency_assumed':rng.beta(4,2,len(syn)),'financial_barrier_latent_assumed':rng.binomial(1,.35,len(syn)),
        'dropout_draw_at_static_annual_hazard_assumed':(rng.random(len(syn))<annual).astype(int),'provenance':'generated_scenario_truth_not_observed'})
    save('data/simulator_hidden_truth.csv',latent)
    # An exact audit finding in the undocumented bundle.
    bundle='Student-Dropout-Success-All-Academic-Levels/Student Dropout & Success – All Academic Levels/'
    bschool=frames[bundle+'school_students_massachusetts_style.csv']
    formula=.02*(1+.5*(bschool.economic_status=='Economically Disadvantaged'))*(1+.8*(bschool.attendance_rate<80))*(1+(bschool.gpa<2))
    abd=frames['abdullah0a_student-dropout-analysis-and-prediction-dataset/student dropout.csv']
    ucopy=frames[bundle+'university_students_comprehensive.csv']; common=[c for c in he.columns if c in ucopy and c not in ['record_id','linkage_group_id','split']]
    matching_common=len(he[common].astype(str).merge(ucopy[common].astype(str),on=common,how='inner'))
    checks={'school_subject_rows':len(long),'portuguese_rows':len(p),'math_rows':len(m),'safe_one_to_one_links':len(safe),
        'documented_merge_inner_pairs':len(m.merge(p,on=KEY)),'ambiguous_shared_keys':int((counts.link_status=='ambiguous_shared').sum()),
        'math_rows_in_ambiguous_shared_keys':int(counts.loc[counts.link_status=='ambiguous_shared','math_rows'].sum()),
        'math_only_rows_added':len(math_only),'student_initialization_rows':len(features),
        'student_ids_unique':features.student_id.is_unique,'groups_in_multiple_splits':int(features.groupby('linkage_group_id').split.nunique().gt(1).sum()),
        'school_copy_math_equal':frames['student-dropout-prediction/student-mat.csv'].equals(frames['student+performance/student/student-mat.csv']),
        'school_copy_portuguese_equal':frames['student-dropout-prediction/student-por.csv'].equals(frames['student+performance/student/student-por.csv']),
        'abdullah_first_33_columns_equal_portuguese':np.array_equal(abd.iloc[:,:33].astype(str).values,frames['student+performance/student/student-por.csv'].astype(str).values),
        'abdullah_dropped_out_equals_final_grade_lt10':bool(np.array_equal(abd.Dropped_Out.astype(int),(p.G3<10).astype(int))),
        'bundle_school_hazard_rule_exact_match_rows':int(np.isclose(bschool.dropout_probability,formula,atol=1e-12,rtol=0).sum()),
        'bundle_school_grade13_rows':int((bschool.grade==13).sum()),'bundle_university_matching_rows_on_common_source_columns':matching_common,
        'uci_higher_ed_target_counts':he.Target.value_counts().to_dict(),'split_counts':features.split.value_counts().to_dict(),
        'synthetic_split_counts':syn.split.value_counts().to_dict(),'observed_dropout_labels_school':int(features.observed_school_dropout.notna().sum()),
        'annual_hazard_calibration_training_mean':float(sigmoid(intercept+ztr).mean()),'annual_hazard_intercept_assumed':intercept,
        'source_files_unchanged':before=={str(p):sha(p) for p in inputs}}
    with zipfile.ZipFile(ROOT/'predict+students+dropout+and+academic+success.zip') as z:
        zd=pd.read_csv(io.BytesIO(z.read('data.csv')),sep=';'); zd.columns=zd.columns.str.lstrip('\ufeff').str.strip()
        checks['higher_ed_csv_equals_zip_member']=zd.equals(frames['Student_Dropout_rate.csv'])
    assert checks['source_files_unchanged'] and checks['student_ids_unique'] and checks['groups_in_multiple_splits']==0
    assert checks['safe_one_to_one_links']==358 and len(features)==674 and len(syn)==2000
    assert features[['anchor_grade1_0_20','mother_education_code','father_education_code']].notna().all().all()
    assert np.all((latent.constant_weekly_hazard_assumed>=0)&(latent.constant_weekly_hazard_assumed<=1))
    assert not any(c in features for c in ['G2','G3','Dropped_Out','absences','dropout_probability'])
    assert syn.groupby('linkage_group_id').split.nunique().max()==1
    dump('analysis/validation.json',checks)
    config={'version':'1.0','seed':SEED,'horizon_weeks':36,'population_size':2000,'default_population_filter':{'anchor_subject':'portuguese'},
      'time_origin':'hypothetical reset after first grading period; no dated attendance observed',
      'hazard':{'provenance':'assumed','training_calibrated_annual_target':.10,'annual_targets':[.05,.10,.20],
        'intercept_for_target_0_10':intercept,'logit_coefficients':{'learning_gap':.9,'travel_over_30min':.5,'no_home_internet':.3,'past_failures_positive':.4},
        'weekly_conversion':'1 - (1 - sigmoid(intercept + score)) ** (1/36)'},
      'actions':[
        {'id':0,'name':'usual_support','money_units':0,'tutor_hours':0,'liaison_hours':0,'offer_admin_hours':0,'duration_weeks':0,'uptake_assumed':1},
        {'id':1,'name':'tutoring_block','money_units':4,'tutor_hours':2,'liaison_hours':0,'offer_admin_hours':.1,'duration_weeks':4,'uptake_assumed':.7,'eligible':'enrolled and learning_gap >= 0.1','delay_weeks':1,'effect':'accepted delivery reduces learning_gap by 0.05 * response_tendency per session; clip 0..1'},
        {'id':2,'name':'attendance_family_liaison','money_units':1,'tutor_hours':0,'liaison_hours':.5,'offer_admin_hours':.1,'duration_weeks':1,'uptake_assumed':.75,'eligible':'enrolled and (observed attendance < 0.85 or engagement < 0.6)','delay_weeks':1,'effect':'accepted contact adds 0.04 * response_tendency to attendance and 0.03 * response_tendency to engagement'},
        {'id':3,'name':'transport_assessment_referral','money_units':2,'tutor_hours':0,'liaison_hours':1,'offer_admin_hours':.1,'duration_weeks':1,'uptake_assumed':.6,'eligible':'enrolled and travel_over_30min == 1 and programme_available; travel is not proof of poverty','delay_weeks':2,'effect':'successful assumed referral removes 0.03 attendance penalty for four weeks; not direct cash assistance'}],
      'action_parameters_provenance':'all costs, effects, eligibility cutoffs, uptake, delays and programme availability are scenario assumptions',
      'resources':{'capacity_fractions':[.05,.10,.20],'unit':'normalized hypothetical budget, not currency','definition':'K=floor(fraction*N_initial); tutor_hours=2*K; liaison_hours=0.5*K; money=4*K; administration_hours=0.1*K weekly; per-step offers<=K; reservations consume these budgets before new offers',
        'transport_programme_available':True,'reserve_tutoring_full_4week_cost_before_offer':True,'funding_horizon_rule':'do not initiate a block that finishes after week 36; cancellations release future reservations'},
      'fairness':{'window_weeks':4,'group':'disadvantage_proxy_group','need_strata':'low/moderate/high from learning_gap and simulated attendance at window start',
        'coverage_targets':[0,.10,.20],'target_definition':'unique eligible students offered an appropriate action / fixed eligible cohort at start of window','denominator_freeze':True,'minimum_report_group_n':30,'hard_constraints':['capacity','budget','eligibility','one_new_offer_per_student_per_week'],'access_infeasibility':'minimize declared nonnegative coverage slack; never violate hard resources'},
      'effect_multipliers':[-.5,0,.5,1,2],'transition_families':['continuous_latent_hazard','four_state_markov'],
      'observation_conditions':['structured_complete','mcar_20pct','group_dependent_missing_40_vs_10pct'],
      'evaluation_seeds':{'pilot':list(range(10)),'heldout':list(range(1000,1030))},
      'rng_streams':['population','state_shocks','dropout','uptake','observation','policy_tie_break'],
      'implementation_status':'configuration and reset data generated; sequential environment and policy trials not executed'}
    config['objective']={'primary':'maximize expected terminal enrolled_count / initial_population_count','discount':1,'intermediate_reward':0,'secondary_metrics':['attendance','engagement','first_withdrawal','reentry'],'partial_observation':'belief/history policy required when latent states hidden'}
    config['continuous_transition_assumptions']={'learning_gap':'clip(g + 0.01*(1-A) + Normal(0,0.015) - tutoring_effect,0,1)',
      'engagement':'clip(e + 0.02*(A-0.85) + Normal(0,0.025) + liaison_effect,0,1)',
      'attendance':'clip(0.85 + 0.15*(e_next-0.5) - 0.10*g_next - 0.06*active_travel_barrier + Normal(0,0.03) + support_effect,0,1)',
      'dynamic_hazard_score_addition':'1.0*(0.85-A) + 0.5*(0.7-e)','reentry_weekly_probability':.005,'reentry_sensitivity':[0,.02],
      'calibration_required':'dynamic usual-support retention is not calibrated by the static annual intercept alone'}
    config['markov_transition_assumptions']={'state_order':['engaged','intermittent','disengaged','withdrawn'],
      'usual_support_matrix':[[.970,.025,.004,.001],[.120,.835,.040,.005],[.020,.130,.825,.025],[0,.005,0,.995]],
      'initial_state_rule':'engaged if A>=0.9 and e>=0.7; disengaged if A<0.75 or e<0.4; intermittent otherwise',
      'intervention_mass_shifts':'see experiment_plan.md; cap by available mass and validate simplex after every adjustment'}
    dump('configs/simulator_config.json',config)
    ex=[]
    policies=['usual_support','random_feasible','longest_waiting','highest_risk','benefit_per_cost','rolling_horizon','rolling_horizon_fair','robust_rolling_horizon_fair']
    for family in config['transition_families']:
        for cap in config['resources']['capacity_fractions']:
            for obs in config['observation_conditions']:
                for policy in policies:
                    ex.append({'stage':'primary','transition_family':family,'capacity_fraction':cap,'observation':obs,'policy':policy,'effect_multiplier':1,'annual_hazard_target':.1,'fairness_target':.1 if policy.endswith('_fair') else 0,'heldout_seed_count':30,'population_size':2000,'weeks':36})
    save('configs/experiment_grid.csv',pd.DataFrame(ex))
    # Column-level provenance and definitions, including fields deliberately unknown.
    source_map={'age_years':'age','sex_source':'sex','rural_residence':'address','family_size_gt3':'famsize','parents_apart':'Pstatus','mother_education_code':'Medu','father_education_code':'Fedu','mother_job':'Mjob','father_job':'Fjob','guardian':'guardian','travel_time_category':'traveltime','study_time_category':'studytime','past_failures_count':'failures','school_support_existing':'schoolsup','family_support_existing':'famsup','paid_classes_existing':'paid','extracurricular':'activities','nursery_attended':'nursery','higher_education_aspiration':'higher','internet_at_home':'internet','family_relationship_rating':'famrel','health_self_rating':'health','anchor_grade1_0_20':'G1','math_grade1_0_20':'G1 (math)'}
    definitions={
      'mother_education_code':'0 none; 1 primary (4th grade); 2 grades 5-9; 3 secondary; 4 higher education',
      'father_education_code':'0 none; 1 primary (4th grade); 2 grades 5-9; 3 secondary; 4 higher education',
      'travel_time_category':'1 <15 min; 2 15-30 min; 3 30-60 min; 4 >60 min',
      'study_time_category':'1 <2h/week; 2 2-5h; 3 5-10h; 4 >10h',
      'past_failures_count':'published past class failures value retained; local values 0-3; codebook description ambiguous at upper end',
      'income_amount':'Unavailable; blank means unknown, never zero income','income_currency':'Unavailable',
      'verified_economic_disadvantage':'Unavailable; blank means not measured',
      'observed_school_dropout':'Unavailable; course failure must not fill this field',
      'both_parents_education_at_most_2':'Medu<=2 and Fedu<=2; proxy for educational disadvantage',
      'no_home_internet':'internet_at_home==0; digital access proxy',
      'travel_over_30min':'traveltime>=3; transport access proxy',
      'disadvantage_proxy_count':'sum of low parental education, no internet, and long commute (0-3); no poverty interpretation',
      'disadvantage_proxy_group':'disadvantage_proxy_count>=2; analyst-defined access-audit group',
      'learning_gap_initial_assumed':'clip((10-anchor_grade1_0_20)/10,0,1); assumed simulator scale, not validated need measure',
      'math_grade1_0_20':'mathematics G1 for unique one-to-one match or math-only anchor; blank when absent/ambiguous',
      'student_id':'POR/MAT plus stable 1-based source data row; local pseudonym, not real identifier',
      'linkage_group_id':'SHA-256 prefix of documented 13 linkage fields; conservative split cluster, not verified identity',
      'split':'deterministic SHA-256 group allocation: 60/20/20 in expectation',
      'link_status':'one_to_one, ambiguous_shared or single_subject; only one_to_one permits math enrichment',
      'record_provenance':'observed_source_with_derived_features',
      'source_row':'1-based data-row number in original subject CSV',
      'anchor_subject':'Portuguese for 649 records; math for 25 profiles with no Portuguese linkage key',
      'school_id':'GP or MS (two Portuguese schools)',
      'family_relationship_rating':'self-reported 1 very bad to 5 excellent','health_self_rating':'self-reported 1 very bad to 5 very good'}
    dictionary=[]
    unknown={'income_amount','income_currency','verified_economic_disadvantage','observed_school_dropout'}
    ids={'student_id','linkage_group_id','split','source_dataset','population','anchor_subject','source_row','record_provenance','link_status'}
    for c in features:
        prov='unavailable' if c in unknown else ('assumed_mapping' if c=='learning_gap_initial_assumed' else ('observed_or_recoded' if c in source_map or c=='school_id' else 'derived'))
        role='metadata' if c in ids else ('unavailable' if c in unknown else ('protected_audit' if c=='sex_source' else ('fairness_audit' if 'disadvantage_proxy' in c else 'context_or_initial_state')))
        dictionary.append({'variable':c,'source_variable':source_map.get(c,''),'definition':definitions.get(c,c.replace('_',' ')),'provenance':prov,'role':role,'availability':'hypothetical first-period reset' if c.endswith('0_20') or c=='learning_gap_initial_assumed' else 'questionnaire timing not established; assume verified at reset','missing_n':int(features[c].isna().sum()),'source_url':URL_SCHOOL})
    save('data/variable_dictionary.csv',pd.DataFrame(dictionary))
    # Bundle issue details and source-use decisions.
    decisions=[]
    for row in audit:
        file=row['file']
        if file.startswith('student+performance/student/'):
            use='primary observed secondary-school source'; reason='performance outcome only; no verified dropout, income or intervention logs'
        elif file=='Student_Dropout_rate.csv':
            use='separate observed higher-education benchmark'; reason='matches bundled UCI data.csv exactly; genuine three-class endpoint; no weekly action log'
        elif 'abdullah0a' in file:
            use='exclude duplicate/relabelled data'; reason='33 original columns exactly match Portuguese rows; Dropped_Out exactly equals G3<10; unknown mirror licence'
        elif 'student-dropout-prediction' in file:
            use='exclude duplicate/preprocessed data'; reason='original subject copies duplicate primary source; X tables transformed without fitted preprocessing metadata; rederive split and features'
        else:
            use='quarantine as undocumented/synthetic-style stress material'; reason='no collection methodology or codebook; never pool with observed primary population'
            if 'school_students_' in file: reason+='; supplied dropout_probability exactly reconstructed by a three-factor rule; 5,030 grade-13 rows'
            if 'district_aggregates' in file: reason+='; aggregate units have no school identifier, cannot be individual-level joins'
            if 'masters_students' in file: reason+='; heterogeneous concatenated schemas with 45 vs 9,955 rows and structural missingness'
            if 'spanish_technological' in file: reason+='; 12,607 rows have earned credits exceeding attempted credits'
            if 'university_students' in file: reason+=f'; {matching_common} exact full-common-column matches to authentic UCI table; name/row count do not establish identity'
        decisions.append({**row,'recommended_use':use,'reason':reason})
    save('analysis/source_decisions.csv',pd.DataFrame(decisions))
    summary={'generated_on':'2026-10-06','input_csv_files':len(audit),'initialization_profiles':len(features),'recommended_portuguese_profiles':len(p),'one_to_one_math_enrichments':len(safe),'synthetic_reset_rows':len(syn),'source_files_unchanged':checks['source_files_unchanged'],'baseline_metrics':rows,'school_proxy_group_counts':features.disadvantage_proxy_group.value_counts().to_dict(),'experiment_primary_cells':len(ex),'experiment_primary_episodes':30*len(ex),'environment_versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__}}
    dump('analysis/study_summary.json',summary)
    dump('support/workbook_inputs.json',{'summary':summary,'subgroups':summaries,'decisions':decisions,'dictionary':dictionary,'intervals':cis})
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()

"""Complete machine-readable coverage for retained fields and versioned contracts."""
from .contracts import json_schemas
from .ingestion import DIRECT, BOOL_MAP, UNKNOWN, RAW_CATEGORIES, RAW_RANGES

DEFINITIONS = {
    'student_id':'Local join identity; never a predictive feature or a verified person ID',
    'source_anchor_student_id':'Original POR/MAT anchor inherited by each bootstrap descendant; join metadata only',
    'source_dataset':'Source-family identity; school adapter accepts only UCI Student Performance',
    'linkage_group_id':'SHA-256 prefix of the 13 documented linkage fields; conservative cluster, not verified identity',
    'split':'Inherited train/validation/test linkage-cluster partition; never a score feature',
    'anchor_subject':'Subject supplying the immutable context and historical first-period grade',
    'link_status':'Only one-to-one cross-subject matches enrich Portuguese anchors; ambiguous math stays in references',
    'record_provenance':'Observed anchor or bootstrap descendant with assumed initial dynamics',
    'income_amount':'Not measured; null, never zero', 'income_currency':'Not measured; null',
    'verified_economic_disadvantage':'Not verified; null, never false or inferred poverty',
    'observed_school_dropout':'No school-dropout label exists; null; G3<10 is course failure',
    'financial_need_verified':'Not verified; null, never inferred from access proxies',
    'sex_source':'Original F/M coding authorized for audit only; excluded from scoring',
    'both_parents_education_at_most_2':'Medu<=2 and Fedu<=2; transparent access proxy',
    'no_home_internet':'Negation of source internet=yes; transparent access proxy',
    'travel_over_30min':'traveltime>=3; transparent access proxy',
    'disadvantage_proxy_count':'Sum of low-parent-education, no-internet and long-commute indicators; not poverty',
    'disadvantage_proxy_group':'Proxy count>=2; audit group, not benefit eligibility',
    'source_time':'Source/event time in simulation weeks, null when source collection time is unavailable',
    'available_at':'Earliest time evidence or an intervention event is authorized for a consumer',
    'as_of_time':'Decision/estimate cutoff in simulation weeks',
    'observation_id':'Stable source assertion identity for joins/deduplication',
    'field':'Closed allowlist of supported observable dimensions; excludes hidden truth and predicted risk',
    'value':'Value in the field-specific unit; null when unsupported/unobserved; no silent coercion',
    'status':'Explicit observed/reported/unknown/missing/withheld/conflicting state, or the enclosing contract status',
    'source':'Named evidence source; reset source timestamps are not known',
    'missingness':'Missingness cause retained separately from a numeric/category value',
    'units':'Field-specific measurement unit; source categories are not continuous durations',
    'note_id':'Stable note identity for evidence provenance and later idempotent assimilation',
    'assertion_id':'Stable assertion identity within a note; later updater must deduplicate across retries',
    'event_time':'Note event/source time, distinct from receipt/availability time',
    'evidence_start':'Inclusive character offset in the retained note',
    'evidence_end':'Exclusive character offset in the retained note',
    'evidence_text':'Exact note substring supporting the assertion; verified at batch construction',
    'kind':'Quantitative measured fact or qualitative trend; qualitative evidence cannot invent a numeric value',
    'trend':'Supported improving/worsening/stable/unknown direction, not an assumed effect size',
    'numerator':'Attendance events in an explicitly stated ratio; never inferred from a trend',
    'denominator':'Opportunities in the same ratio; positive and at least the numerator',
    'last_observed_at':'Most recent evidence time; null if no dated evidence; never after estimate cutoff',
    'conflict':'Unresolved evidence disagreement; retain alternatives in evidence history',
    'evidence_ids':'Identifiers linking an estimated field or eligibility to authorized supporting facts',
    'estimate_version':'Immutable estimate revision; risk and decision must reference the same revision',
    'lower':'Lower uncertainty bound; field-specific units; null when no supported interval exists',
    'upper':'Upper uncertainty bound; field-specific units; null when no supported interval exists',
    'predicted_simulated_withdrawal_risk':'Independent probability for the declared simulated target; null if unavailable or not applicable',
    'target':'Any simulated withdrawal in the horizon conditional on current enrollment; not observed school dropout',
    'horizon_steps':'Forecast steps, positive when risk is available; terminal forecasts are unavailable',
    'reference_support_regime':'Continue known commitments without new scarce offers',
    'feature_snapshot_hash':'Hash of the risk model feature snapshot; never a model feature itself',
    'out_of_distribution':'Declared model applicability flag; not an excuse to manufacture a probability',
    'uncertainty_method':'Named interval construction/calibration method; required if risk bounds are supplied',
    'prediction_description':'Logged estimator prediction before assimilation; never a copy of realized latent response',
    'correction_description':'Logged evidence-driven correction under the named update rule',
    'waiting_weeks':'Known waiting time in weeks, including unserved students',
    'eligibility':'Operational eligibility derived from authorized information; unknown stays explicit',
    'staff_hours':'Staff time charged or reserved for the named event/week',
    'concurrent_caseload':'Concurrent student places used, reserved or available',
    'money':'Scenario money charged/reserved in the ledger currency',
    'administration_hours':'Administrative staff time, accounted separately',
    'waste':'Committed resources lost under future scheduler rules; nonnegative amount',
    'cancellations':'Commitment identifiers cancelled under future scheduler rules',
    'programme_timers':'Full programme timing/session state needed by future stochastic dynamics',
    'continuing_effect_until':'Declared effect-timer end in simulation weeks; no efficacy assumed by this schema',
    'remaining_sessions':'Outstanding sessions in a known commitment; sessions are not weeks',
    'seed':'Explicit random-stream seed; Stage 1 performs no random sampling',
    'configuration_hash':'SHA-256 identity of the configuration used to create a result/episode',
}

GENERATOR_ASSUMPTIONS = {
    'seed': {'value':20261006, 'units':'integer', 'meaning':'Legacy fixed fixture seed; no new sampling in Stage 1', 'mechanism':'NumPy default_rng, sequential draws in Stage 0 build_study.py'},
    'bootstrap_counts': {'value':{'train':1200,'validation':400,'test':400}, 'units':'descendants', 'meaning':'Whole Portuguese profiles drawn within source split', 'mechanism':'rng.integers(0, len(pool), n), with replacement; train then validation then test'},
    'learning_gap': {'value':'clip((10-G1)/10,0,1)', 'units':'fraction', 'meaning':'Assumed learning need scale, not measured need', 'mechanism':'Deterministic first-period grade transform'},
    'attendance': {'value':{'intercept':.90,'gap_coefficient':-.12,'long_commute_coefficient':-.06,'noise_sd':.04,'lower':.50,'upper':.99}, 'units':'fraction', 'meaning':'Assumed initial attendance; not observed', 'mechanism':'clip(.90-.12*gap-.06*travel_over_30min+Normal(0,.04),.50,.99)'},
    'engagement': {'value':{'intercept':.80,'gap_coefficient':-.25,'noise_sd':.08,'lower':.1,'upper':.99}, 'units':'fraction', 'meaning':'Assumed initial engagement; not observed', 'mechanism':'clip(.80-.25*gap+Normal(0,.08),.1,.99)'},
    'response_tendency': {'value':{'alpha':4,'beta':2}, 'units':'fraction', 'meaning':'Latent simulated responsiveness; not a fitted treatment effect', 'mechanism':'rng.beta(4,2,n)'},
    'financial_barrier': {'value':.35, 'units':'probability', 'meaning':'Latent assumed barrier; not verified poverty', 'mechanism':'rng.binomial(1,.35,n)'},
    'static_hazard': {'value':{'training_mean':.10,'reference_weeks':36,'gap':.9,'long_commute':.5,'no_internet':.3,'past_failure_positive':.4,'intercept_bisection_iterations':100,'intercept_search_lower':-15,'intercept_search_upper':5}, 'units':'probability', 'meaning':'Legacy assumed reference-period withdrawal probability, not measured school dropout', 'mechanism':'logistic(intercept+.9*gap+.5*long_commute+.3*no_internet+.4*(failures>0)); intercept bisected on training Portuguese anchors; weekly=1-(1-p)**(1/36)'},
    'static_future_draw': {'value':'Bernoulli(static reference-period probability)', 'units':'boolean', 'meaning':'Legacy diagnostic only; prohibited as sequential outcome', 'mechanism':'rng.random(n)<annual_probability'},
    'initial_enrollment': {'value':True, 'units':'boolean', 'meaning':'Assume enrolled at reset', 'mechanism':'Constant true'},
    'initial_programme_state': {'value':{'weeks_since_offer':0,'support_sessions_completed':0,'programme_timers':[]}, 'units':'weeks/sessions', 'meaning':'New simulated programme, not absence of historical support', 'mechanism':'Constant empty/zero'},
    'observation_reset_time': {'value':0, 'units':'simulation_weeks', 'meaning':'Hypothetical first-period landmark; source collection dates unavailable', 'mechanism':'Constant landmark; source_time=null; selected questionnaire context assumed available'},
}

MECHANISMS = {
    'initial_attendance_fraction_assumed':'attendance', 'attendance':'attendance',
    'initial_engagement_assumed':'engagement', 'engagement':'engagement',
    'learning_gap_initial_assumed':'learning_gap', 'learning_need':'learning_gap',
    'response_tendency_assumed':'response_tendency', 'response_tendency':'response_tendency',
    'financial_barrier_latent_assumed':'financial_barrier', 'financial_barrier':'financial_barrier',
    'annual_dropout_probability_assumed':'static_hazard', 'constant_weekly_hazard_assumed':'static_hazard',
    'dropout_draw_at_static_annual_hazard_assumed':'static_future_draw',
    'enrolled_initial_assumed':'initial_enrollment', 'enrolled':'initial_enrollment',
    'weeks_since_offer':'initial_programme_state', 'support_sessions_completed':'initial_programme_state',
    'programme_timers':'initial_programme_state'}


def units_for(name):
    if name in ('income_amount','money'):
        return 'declared currency; null when unknown'
    if name in ('income_currency','currency'):
        return 'currency identifier'
    if name.endswith('_id') or name in ('source_dataset','split','anchor_subject','record_provenance','feature_snapshot_hash','configuration_hash') or name.endswith('_version'):
        return 'identifier / metadata; not a model feature'
    if name in RAW_CATEGORIES or name.endswith('_category') or name.endswith('_code') or name in ('field','status','trend','kind','missingness','eligibility','target','reference_support_regime'):
        return 'nominal or ordinal category; see source codebook / contract'
    if name in BOOL_MAP or name in ('sex_source','conflict','out_of_distribution','accepted','delivered','evaluator_only','verified_economic_disadvantage','observed_school_dropout','financial_need_verified','disadvantage_proxy_group','both_parents_education_at_most_2','no_home_internet','travel_over_30min'):
        return 'source category F/M' if name=='sex_source' else 'boolean; null where unknown'
    if name in MECHANISMS:
        return GENERATOR_ASSUMPTIONS[MECHANISMS[name]]['units']
    if 'grade' in name or name in ('G1','G2','G3'):
        return 'grade_0_20'
    if name in ('age','age_years'):
        return 'years'
    if 'hours' in name:
        return 'hours'
    if name == 'money':
        return 'ledger_currency'
    if 'time' in name or name in ('available_at','week'):
        return 'simulation_weeks' if name != 'travel_time_category' else 'source_category'
    if 'probability' in name or name in ('predicted_simulated_withdrawal_risk','lower','upper'):
        return 'dimension_specific; probability for risk'
    if 'count' in name or 'sessions' in name or 'absences' in name or name in ('source_row','numerator','denominator'):
        return 'count'
    return 'structured value; units specified by child fields' if name in ('observations','context','lineage','audit','unknown','fields','resources','commitments','capacity','used','waste','provenance') else 'dimensionless / metadata; see definition'


def provenance_register(tables, historical, reset_features):
    rows=[]; history={(r['table'],r['field']):r for r in historical}
    for table,data in tables.items():
        for name in data[0]:
            old=history.get((table,name),{})
            mechanism=GENERATOR_ASSUMPTIONS.get(MECHANISMS.get(name,''))
            visibility=old.get('visibility','evaluator_reference' if table.startswith('raw_') else 'metadata')
            if table in ('subject_records_reference','student_outcomes_reference','simulator_hidden_truth'):
                visibility='evaluator_only'
            if mechanism and table=='synthetic_student_population':
                visibility='environment_only_until_observed'
            source=DIRECT.get(name, BOOL_MAP.get(name,('',))[0]) or old.get('source_field','')
            if name=='school_id': source='school'
            rows.append({'table':table,'field':name,'definition':DEFINITIONS.get(name,old.get('explanation',f'Original UCI school column {name}; preserve supplied units/categories')),
                'units':units_for(name),'role':visibility,'source_derivation':source or f'{table}.{name}',
                'decision_time_availability':'never' if visibility=='evaluator_only' else 'observation mechanism required' if visibility=='environment_only_until_observed' else old.get('availability','reference_only'),
                'classification':old.get('classification','OBSERVED FROM DATA'),
                'uncertainty_range':'not empirically calibrated' if mechanism else 'source measurement uncertainty unavailable',
                'generation_mechanism':mechanism['mechanism'] if mechanism else 'none; retained or deterministically recoded',
                'assumed_meaning':mechanism['meaning'] if mechanism else 'No extra measured quantity implied',
                'schema_version':'2.0.0'})
    # Every property of every contract is registered, including nested helper records.
    for contract,schema in json_schemas()['$defs'].items():
        for name,spec in schema['properties'].items():
            mechanism=GENERATOR_ASSUMPTIONS.get(MECHANISMS.get(name,'')) if contract=='EnvironmentState' else None
            definition=spec.get('description') or DEFINITIONS.get(name,f'{contract}.{name}; typed operational record; see contract and child-field definitions')
            role=('metadata' if contract=='Lineage' else 'audit_only' if contract=='AuditGroups' else
                  'environment_only' if contract in ('EnvironmentState','ProgrammeTimer') else
                  'evaluator_only' if contract in ('Outcome','EpisodeRecord') else
                  'authorized_observation_or_estimate' if contract in ('Observation','EvidenceAssertion','EstimatedStudentState','EstimateField') else 'typed_interface')
            rows.append({'table':contract,'field':name,'definition':definition,'units':units_for(name),
                'role':role,'source_derivation':DIRECT.get(name,BOOL_MAP.get(name,('',))[0]) or f'{contract} contract',
                'decision_time_availability':'never' if role in ('environment_only','evaluator_only') else 'only through consumer allowlist and available_at/as_of_time',
                'classification':'GENERATED' if mechanism else 'OBSERVED FROM DATA' if contract=='VerifiedContext' else 'UNAVAILABLE' if contract=='UnknownFields' else 'ESTIMATED FROM DATA' if contract in ('EstimatedStudentState','EstimateField','RiskEstimate') else 'DERIVED',
                'uncertainty_range':f"{spec.get('minimum','unspecified')}..{spec.get('maximum','unspecified')}; bounds are not calibrated confidence",
                'generation_mechanism':mechanism['mechanism'] if mechanism else 'none in Stage 1; record construction / deterministic projection',
                'assumed_meaning':mechanism['meaning'] if mechanism else 'Interface definition; future records need event/update provenance',
                'schema_version':'2.0.0'})
    for name,spec in GENERATOR_ASSUMPTIONS.items():
        def leaves(v,prefix):
            if isinstance(v,dict):
                for key,val in v.items(): yield from leaves(val,f'{prefix}.{key}')
            else: yield prefix,v
        for path,value in leaves(spec['value'],name):
            rows.append({'table':'fixture_parameters','field':path,'definition':spec['meaning'],
                'units':spec['units'],'role':'environment_assumption','source_derivation':'Stage 0 builder, retained fixed fixture',
                'decision_time_availability':'never','classification':'ASSUMED FOR SIMULATION',
                'uncertainty_range':'not fitted; sensitivity deferred to simulator stages',
                'generation_mechanism':spec['mechanism'],'assumed_meaning':str(value),'schema_version':'2.0.0'})
    for name,value in [('reset_features',list(reset_features)),('schema_version','2.0.0'),('adapter_version','stage1-v1')]:
        rows.append({'table':'stage1_configuration','field':name,'definition':'Frozen ingestion/consumer configuration',
            'units':'feature names / version identifier','role':'configuration','source_derivation':'configs/stage1_inputs.v1.json',
            'decision_time_availability':'configuration metadata only','classification':'DERIVED',
            'uncertainty_range':'not a measured quantity','generation_mechanism':'deterministic configuration',
            'assumed_meaning':str(value),'schema_version':'2.0.0'})
    return rows


def source_mapping():
    result=[]
    for dest,source in DIRECT.items():
        result.append({'source_family':'uci_student_performance','source_field':source,
            'canonical_path':'StudentContext.context.'+dest,'transformation':'preserve category/unit',
            'availability':'hypothetical first-period reset; questionnaire times unverified'})
    for dest,(source,yes) in BOOL_MAP.items():
        result.append({'source_family':'uci_student_performance','source_field':source,
            'canonical_path':'StudentContext.context.'+dest,'transformation':f'{source} == {yes!r}',
            'availability':'hypothetical first-period reset; questionnaire times unverified'})
    result.extend([
        {'source_family':'uci_student_performance','source_field':'sex','canonical_path':'StudentContext.audit.sex_source','transformation':'retain F/M source coding; audit only','availability':'audit only'},
        {'source_family':'uci_student_performance','source_field':'G1 (math)','canonical_path':'StudentContext.context.math_grade1_0_20','transformation':'358 safe enrichments plus math-only anchors; otherwise null','availability':'not synchronized; excluded from policy'},
    ])
    mapped={r['source_field'] for r in result}
    for name in sorted(set(RAW_CATEGORIES)|set(RAW_RANGES)):
        if name not in mapped:
            result.append({'source_family':'uci_student_performance','source_field':name,
                'canonical_path':'evaluator.subject_records_reference.'+name,
                'transformation':'preserve original unit/category; G3<10 is course failure only',
                'availability':'evaluator/reference only; excluded from reset'})
    for name in UNKNOWN:
        result.append({'source_family':'uci_student_performance','source_field':'not measured',
            'canonical_path':'StudentContext.unknown.'+name,'transformation':'null preserved','availability':'unavailable'})
    return result

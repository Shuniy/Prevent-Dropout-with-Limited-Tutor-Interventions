"""Frozen Phase 5 offline experiments, independent verification and exact replay.

python -m src.evaluation.phase5_experiments --stage all --output results/phase5_new
"""
import argparse
from collections import Counter,defaultdict
from dataclasses import asdict,replace
import json
from pathlib import Path
import tomllib

import numpy as np

from .provenance import (digest,runtime_identity,source_fingerprints,staged_artifacts,
    write_exclusive,seal_directory,verify_directory)
from .paired_statistics import summarize,paired_comparison
from .phase5_prediction_evaluation import (generate_reference_labels,evaluate_predictor,calibration_plot,
    reference_label_from_record)
from .phase5_language import (build_language_benchmark,evaluate_language,matched_snapshot_evaluation,
    active_programme_language_example)
from ..school.delivery_config import DeliveryConfig
from ..school.delivery_policy import WeeklyDeliveryPolicy
from ..school.delivery_experiments import normalized,scorecard
from ..school.phase5_delivery import (population_environment,ResearchInformationController,
    PredictionController,TrainedRiskPriorityPolicy,save_phase5_episode,replay_phase5_episode)
from ..school.population_sampling import population_validation
from ..school.trained_withdrawal_risk import fit_model,TrainedWithdrawalRiskModel
from ..school.student_condition import STATES,StudentCondition
from ..school.delivery_resources import feasible_offers


ROOT=Path(__file__).resolve().parents[2]
PROTOCOL=ROOT/'docs/phase5_research_protocol_v2.md'
CONFIG=ROOT/'configs/phase5_evaluation_v2.toml'


def load_configuration(path=CONFIG):
    with Path(path).open('rb') as stream:
        config=tomllib.load(stream)
    p=config['phase5']
    if p['protocol_version'] not in ('phase5_research/v1','phase5_research/v2'):
        raise ValueError('unsupported Phase 5 protocol')
    seed_names=('training_world_seeds','validation_world_seeds','prediction_test_world_seeds',
                'development_world_seeds','heldout_world_seeds')
    owners={}
    for name in seed_names:
        seeds=p[name]
        if len(set(seeds))!=len(seeds) or not seeds or any(type(s) is not int or s<0 for s in seeds):
            raise ValueError('world seeds must be explicit, nonempty, unique nonnegative integers')
        for seed in seeds:
            if seed in owners:
                raise ValueError('world seed partition overlap')
            owners[seed]=name
    DeliveryConfig(**config['delivery'])
    return config


def make_controller(config,split,population_seed,mode,*,model=None,information='structured_observable'):
    env,pop=population_environment(config,population_mode='source_held_out',split=split,population_seed=population_seed)
    policy=TrainedRiskPriorityPolicy(config,model) if mode=='trained_risk_priority' else WeeklyDeliveryPolicy(config,mode)
    return ResearchInformationController(env,policy,trained_model=model,information_mode=information),pop


def estimation_scorecard(c):
    truth={week:dict(values) for week,values in c.environment.evaluator_truth}
    records=[]
    for state in c.snapshots:
        for student in state.students:
            actual=truth[state.week-1][student.student_id]
            onehot=np.array([float(actual==s) for s in STATES])
            belief=np.asarray(student.estimate.condition_probabilities)
            records.append(dict(cutoff=state.week,student_id=student.student_id,
                group=str(getattr(student.profile,c.environment.config.fairness_grouping_attribute)),brier=float(np.sum((belief-onehot)**2)),
                negative_log_likelihood=float(-np.log(max(belief[list(STATES).index(actual)],1e-12))),
                missing=bool(dict(student.estimate.uncertainty).get('missing_current_signal',True))))
    return dict(n=len(records),mean_state_brier=float(np.mean([r['brier'] for r in records])),
        mean_state_nll=float(np.mean([r['negative_log_likelihood'] for r in records])),
        records=records,trained_predictions=normalized(c.trained_predictions),
        prediction_note='online diagnostics; calibration requires separate reference-outcome evaluation')


def four_scorecards(c,pop):
    raw=scorecard(c)
    final=dict(c.environment.evaluator_truth[-1][1])
    by_group={}
    for profile in c.environment.profiles:
        by_group.setdefault(str(getattr(profile,c.environment.config.fairness_grouping_attribute)),[]).append(profile.student_id)
    group_retention={g:sum(final[sid]!=StudentCondition.WITHDRAWN for sid in ids)/len(ids) for g,ids in by_group.items()}
    fairness=raw['fairness']
    gaps=[r['offer_coverage_group_disparity'] for r in fairness if r['offer_coverage_group_disparity'] is not None]
    truth=c.environment.evaluator_truth
    withdrawals=sum(any(dict(values)[p.student_id]==StudentCondition.WITHDRAWN for _,values in truth)
                    for p in c.environment.profiles)
    reentries=sum(sum(a==StudentCondition.WITHDRAWN and b!=StudentCondition.WITHDRAWN
        for a,b in zip([dict(v)[p.student_id] for _,v in truth],[dict(v)[p.student_id] for _,v in truth][1:]))
        for p in c.environment.profiles)
    statuses=Counter(raw['solver_statuses'])
    allocation=dict(raw,policy='trained_risk_priority' if isinstance(c.policy,TrainedRiskPriorityPolicy) else c.policy.mode,
        stage='phase5_episode_descriptive_scorecard',
        unique_offered_students=len({e.student_id for e in c.environment.events if e.kind=='support_offered'}),
        offer_rate=len({e.student_id for e in c.environment.events if e.kind=='support_offered'})/len(final),
        completion_rate=raw['programme_completed']/len(final),
        normalized_fairness_shortfall=sum(r['normalized_shortfall'] for r in fairness if r['normalized_shortfall'] is not None),
        nonempty_fairness_cells=sum(r['frozen_eligible_students']>0 for r in fairness),
        max_comparable_need_access_gap=max(gaps) if gaps else None,
        solver_status_counts=dict(statuses),incomplete_optimization_stages=sum(not a.lexicographic_complete for a in c.decisions),
        solver_failures=sum('fail' in a.status or 'infeasible' in a.status for a in c.decisions))
    return normalized(dict(extraction=dict(attempts=len(c.attempts),
            accepted=sum(a['status']=='accepted' for a in c.attempts),
            quarantine=sum(a['status']=='quarantined' for a in c.attempts),
            accepted_empty=sum(a.get('result')=='empty' for a in c.attempts),
            quality_status='not_identified_without_content_gold; see independent language benchmark'),
        estimation_prediction=estimation_scorecard(c),allocation=allocation,
        simulated_effectiveness=dict(retention_rate=raw['simulated_terminal_retention']/len(final),
            retained=raw['simulated_terminal_retention'],n=len(final),withdrawal_events=withdrawals,reentry_events=reentries,
            group_retention=group_retention,worst_group_retention=min(group_retention.values()),
            population_identity=pop.identity,population_seed=pop.population_seed,world_seed=c.environment.config.seed)))


def run_prediction(config,output,protocol):
    p=config['phase5'];base=DeliveryConfig(**config['delivery'])
    partitions={}
    for split,world_key,pop_key in (
        ('train','training_world_seeds','training_population_seed_base'),
        ('validation','validation_world_seeds','validation_population_seed_base'),
        ('test','prediction_test_world_seeds','prediction_test_population_seed_base')):
        rows=[]
        # Do not generate or inspect final labels until selection/calibration freezes.
        if split=='test':
            model,training=fit_model(partitions['train'],partitions['validation'])
            model.save(output/'model.json')
            write_exclusive(output/'training_selection.json',training)
        for world in p[world_key]:
            print(f'prediction {split} world {world}',flush=True)
            cfg=replace(base,num_students=p['prediction_cohort_size'],horizon_weeks=p['prediction_weeks'],sessions_required=2,seed=world)
            c,pop=make_controller(cfg,split,p[pop_key]+world,'random')
            rows.extend(generate_reference_labels(c,pop,horizon=p['prediction_horizon']))
            path=output/'trajectories'/f'{split}_{world}'
            save_phase5_episode(c,pop,path,protocol_text=protocol)
            replay_phase5_episode(path)
        partitions[split]=rows
        write_exclusive(output/(split+'_reference_labels.json'),[asdict(r) for r in rows])
    report=evaluate_predictor(model,partitions['test'],training['constant_by_horizon'])
    write_exclusive(output/'heldout_metrics.json',report)
    uncalibrated={k:v for k,v in model.artifact.items() if k!='model_version'}
    uncalibrated['calibration']=dict(method='none',reason='same_selected_coefficients_uncalibrated_control')
    uncalibrated=TrainedWithdrawalRiskModel({**uncalibrated,'model_version':digest(uncalibrated)})
    write_exclusive(output/'heldout_uncalibrated_metrics.json',evaluate_predictor(
        uncalibrated,partitions['test'],training['constant_by_horizon']))
    calibration_plot(report,output/'calibration.png')
    return model,dict(model_version=model.version,metrics=report['pooled_descriptive'],
        worlds=len(p['prediction_test_world_seeds']),labels=len(partitions['test']),ood=report['ood'],abstentions=report['abstentions'])


def run_language(output,live_extractor=None):
    cases=build_language_benchmark()
    # Save complete corpus/annotations before first evaluation invocation.
    write_exclusive(output/'frozen_corpus.json',cases)
    report=evaluate_language(cases,live_extractor=live_extractor)
    write_exclusive(output/'extraction_report.json',report)
    snapshots=matched_snapshot_evaluation(cases)
    write_exclusive(output/'matched_snapshots.json',snapshots)
    active=active_programme_language_example(output/'active_programme')
    write_exclusive(output/'active_programme_comparison.json',active)
    return dict(splits={s:dict(n=v['n'],metrics=v['methods']['deterministic_grammar']['metrics']['micro'])
        for s,v in report['splits'].items()},matched_attempts=snapshots['attempts'],
        matched_assignment_disagreements=snapshots['assignment_disagreements'],
        active_programme_reviews=[active['gold_cutoff2_review'],active['extracted_cutoff2_review']],
        active_later_assignment_disagreement=active['later_assignment_disagreement'],llm=report['llm'])


def compatibility_audit(state,config):
    """Public pre-outcome gate: do resources and audited needs exercise policy?"""
    ids={a.student_id for a in feasible_offers(state,config,end_week=state.week)}
    groups=Counter(str(getattr(s.profile,config.fairness_grouping_attribute)) for s in state.students
                   if s.student_id in ids)
    strata=defaultdict(set)
    for cohort in state.fairness_window.cohorts:
        if ids.intersection(cohort.student_ids) and cohort.group!='unknown':
            strata[cohort.stratum].add(cohort.group)
    shared=sorted(k for k,v in strata.items() if len(v)>=2)
    return dict(feasible_students=len(ids),feasible_students_by_audited_group=dict(groups),
        shared_need_strata=shared,exercised_design=len(groups)>=2 and bool(shared))


def run_cell(base,worlds,split,population_seed,modes,information,output,protocol,*,model=None,require_nonvacuous=False):
    rows=[]
    for world in worlds:
        paired_truth=[]
        for mode in modes:
            print(f'weekly {split} {information} world {world} policy {mode}',flush=True)
            cfg=replace(base,seed=world)
            c,pop=make_controller(cfg,split,population_seed,mode,model=model,information=information)
            audit=compatibility_audit(c.prepare_decision_snapshot(),cfg)
            if require_nonvacuous and not audit['exercised_design']:
                raise ValueError('unexercised population/group compatibility; no primary policy claim: '+str(audit))
            c.run_episode()
            cards=four_scorecards(c,pop)
            if require_nonvacuous and (cards['allocation']['support_offered']==0 or cards['extraction']['attempts']==0):
                raise ValueError('unexercised allocation or extraction; no primary policy claim')
            path=output/f'{world}_{mode}'
            save_phase5_episode(c,pop,path,protocol_text=protocol)
            replay_phase5_episode(path)
            write_exclusive(output/(f'{world}_{mode}_scorecards.json'),cards)
            effect=cards['simulated_effectiveness'];allocation=cards['allocation']
            rows.append(dict(seed=world,policy=mode,information=information,population_identity=pop.identity,
                setting=Path(output).name,configuration_identity=digest(asdict(cfg)),
                weekly_capacity=cfg.weekly_session_capacity,effect_strength=cfg.effect_strength,
                compatibility_audit=audit,actual_support_offers=allocation['support_offered'],
                population_seed=population_seed,retention_rate=effect['retention_rate'],
                worst_group_retention=effect['worst_group_retention'],
                access_gap=allocation['max_comparable_need_access_gap'],
                normalized_shortfall=allocation['normalized_fairness_shortfall'],
                offer_rate=allocation['offer_rate'],completion_rate=allocation['completion_rate'],
                cost=float(allocation['spent_money']),solver_failures=allocation['solver_failures'],
                incomplete_stages=allocation['incomplete_optimization_stages'],
                extraction_failures=cards['extraction']['quarantine'],
                episode_identity=json.loads((path/'manifest.json').read_text())['identity']))
            paired_truth.append(c.environment.evaluator_truth)
        if base.effect_strength==0 and any(t!=paired_truth[0] for t in paired_truth[1:]):
            raise AssertionError('zero-effect policies changed keyed hidden trajectory')
    write_exclusive(output/'world_results.json',rows)
    return rows


def paired_report(rows):
    point=[r for r in rows if r['policy']=='fair_point']
    robust=[r for r in rows if r['policy']=='fair_robust']
    report={metric:paired_comparison(robust,point,metric) for metric in
        ('retention_rate','worst_group_retention','normalized_shortfall','offer_rate','completion_rate','cost')}
    if all(r['access_gap'] is not None for r in rows):
        report['access_gap']=paired_comparison(robust,point,'access_gap')
    else:
        report['access_gap']=dict(status='unavailable_in_some_worlds',
            unavailable_worlds=sorted({r['seed'] for r in rows if r['access_gap'] is None}),
            reason='no shared nonempty comparable-need group cells; no fabricated zero gap')
    return dict(contrast='FairRobust_minus_FairPoint',outcomes=report,
        exercise_status='exercised' if all(r.get('actual_support_offers',0)>0 and
            r.get('compatibility_audit',{}).get('exercised_design',False) for r in rows) else 'not_fully_exercised',
        raw_policy_means={m:{metric:summarize([r[metric] for r in rows if r['policy']==m]) for metric in
            ('retention_rate','worst_group_retention','normalized_shortfall','offer_rate','completion_rate','cost')}
            for m in ('fair_point','fair_robust')},
        constraints=dict(solver_failures=sum(r['solver_failures'] for r in rows),
            incomplete_stages=sum(r['incomplete_stages'] for r in rows),extraction_failures=sum(r['extraction_failures'] for r in rows)),
        inference='paired independent world intervals conditional on this cohort/effect; no equivalence or real-world claim')


def verify_primary_design(rows,config):
    """Refuse missing, duplicate, wrong-condition or unexercised primary cells."""
    p=config['phase5']
    seeds=p['heldout_world_seeds']
    expected={(s,m) for s in seeds for m in ('fair_point','fair_robust')}
    keys=[(r.get('seed'),r.get('policy')) for r in rows]
    if len(seeds)<30 or len(keys)!=len(set(keys)) or set(keys)!=expected:
        raise ValueError('incomplete, duplicate or wrong-world frozen primary matrix')
    base=DeliveryConfig(**config['delivery'])
    for row in rows:
        if (row.get('setting')!='primary' or row.get('information')!='group_dependent'
                or row.get('population_seed')!=p['primary_population_seed']
                or row.get('configuration_identity')!=digest(asdict(replace(base,seed=row['seed'])))
                or row.get('actual_support_offers',0)<=0
                or not row.get('compatibility_audit',{}).get('exercised_design',False)):
            raise ValueError('wrong configuration or unexercised frozen primary cell')
    return dict(status='complete_exercised_primary',paired_worlds=len(seeds),episodes=len(rows))


def run_primary(config,output,protocol,*,model=None,development_only=False):
    p=config['phase5'];base=DeliveryConfig(**config['delivery'])
    dev=run_cell(base,p['development_world_seeds'],'validation',p['development_population_seed'],
        ('fair_point','fair_robust'),'group_dependent',output/'development',protocol,model=model,require_nonvacuous=True)
    if any(r['solver_failures'] or r['incomplete_stages'] for r in dev):
        raise ValueError('development gate failed: solver failure or incomplete stages; held-out not executed')
    write_exclusive(output/'development_report.json',paired_report(dev))
    if development_only:
        return dict(status='development_only',paired_worlds=len(p['development_world_seeds']))
    if len(p['heldout_world_seeds'])<30:
        raise ValueError('frozen primary requires at least 30 held-out paired worlds')
    heldout=run_cell(base,p['heldout_world_seeds'],'test',p['primary_population_seed'],
        ('fair_point','fair_robust'),'group_dependent',output/'primary',protocol,model=model,require_nonvacuous=True)
    verify_primary_design(heldout,config)
    report=paired_report(heldout)
    write_exclusive(output/'primary_report.json',report)
    return report


def run_secondary(config,output,protocol,model):
    p=config['phase5'];base=DeliveryConfig(**config['delivery']);worlds=p['heldout_world_seeds'][:5]
    cells=[]
    cells.extend(run_cell(base,worlds,'test',p['primary_population_seed'],
        ('wait','random','priority','trained_risk_priority'),'group_dependent',output/'controls',protocol,model=model))
    for information in ('structured_observable','random_missing','corrupted_language','heldout_style'):
        cells.extend(run_cell(base,worlds,'test',p['primary_population_seed'],('fair_point',),
            information,output/information,protocol,model=model))
    for capacity in (1,3):
        cells.extend(run_cell(replace(base,weekly_session_capacity=capacity,weekly_mentor_hours=float(capacity),
            max_concurrent_students=capacity),worlds,'test',p['primary_population_seed'],('fair_point','fair_robust'),
            'group_dependent',output/f'capacity_{capacity}',protocol,model=model))
    for strength in (0.,.25,.5):
        cells.extend(run_cell(replace(base,effect_strength=strength),worlds,'test',p['primary_population_seed'],
            ('fair_point','fair_robust'),'group_dependent',output/f'effect_{strength}',protocol,model=model))
    for population_seed in p['sensitivity_population_seeds']:
        cells.extend(run_cell(base,worlds,'test',population_seed,('fair_point','fair_robust'),
            'group_dependent',output/f'population_{population_seed}',protocol,model=model))
    write_exclusive(output/'secondary_world_results.json',cells)
    return dict(episodes=len(cells),status='exploratory_one_factor_sensitivities',
        unsupported_effect_scenarios=['delayed','heterogeneous'],
        adverse_effect_scenario='separate_frozen_followup: --stage adverse')


def adverse_effect_config(base):
    """Explicit assumption accepted by the existing weekly matrix contract."""
    matrix=((.968,.025,.004,.003),(.04,.89,.05,.02),(.01,.04,.87,.08),(0.,0.,0.,1.))
    return replace(base,weekly_tutoring_matrix=matrix,effect_strength=1.)


def adverse_report(rows):
    reference=[r for r in rows if r['policy']=='wait']
    metrics=('retention_rate','worst_group_retention','normalized_shortfall','offer_rate','completion_rate','cost')
    return dict(status='exploratory_adverse_effect_stress',
        paired_vs_wait={mode:{metric:paired_comparison([r for r in rows if r['policy']==mode],reference,metric)
            for metric in metrics} for mode in ('fair_point','fair_robust')},
        raw_policy_means={mode:{metric:summarize([r[metric] for r in rows if r['policy']==mode])
            for metric in metrics} for mode in ('wait','fair_point','fair_robust')},
        inference='five exploratory paired worlds; no causal or confirmatory real-school claim')


def run_adverse(config,output,protocol,model=None):
    p=config['phase5'];base=adverse_effect_config(DeliveryConfig(**config['delivery']))
    rows=run_cell(base,p['heldout_world_seeds'][:5],'test',p['primary_population_seed'],
        ('wait','fair_point','fair_robust'),'group_dependent',output,protocol,model=model)
    report=adverse_report(rows)
    write_exclusive(output/'adverse_report.json',report)
    return report


def verify_run(source,*,replay=True):
    source=Path(source)
    verify_directory(source)
    frozen=json.loads((source/'frozen_execution.json').read_text())
    if digest(frozen['configuration'])!=frozen['configuration_identity'] or digest(frozen['protocol'])!=frozen['protocol_identity']:
        raise ValueError('frozen execution identity mismatch')
    if replay and source_fingerprints()!=frozen['source_fingerprints']:
        raise ValueError('exact verification requires frozen execution source')
    primary=source/'weekly/primary_report.json'
    if frozen['stage'] in ('all','primary') and not primary.exists():
        raise ValueError('claimed primary execution lacks its frozen primary report')
    if primary.exists():
        verify_primary_design(json.loads((source/'weekly/primary/world_results.json').read_text()),frozen['configuration'])
    manifests=sorted(source.rglob('manifest.json'))
    count=0
    for path in manifests:
        record=json.loads(path.read_text())
        if record.get('contract')=='phase5_source_weekly/replay/v1':
            if record['protocol_text']!=frozen['protocol']:
                raise ValueError('episode protocol differs from frozen research execution')
            if replay:
                # Reconstruct all four scorecards from the verified live
                # controller, independently of their saved derived JSON.
                card_path=path.parent.parent/(path.parent.name+'_scorecards.json')
                def check_cards(controller,population):
                    if card_path.exists() and four_scorecards(controller,population)!=json.loads(card_path.read_text()):
                        raise ValueError('independent four-scorecard recomputation mismatch')
                replay_phase5_episode(path.parent,on_verified_controller=check_cards)
            count+=1
        elif record.get('contract')=='scheduled_weekly/replay/v3':
            if replay:
                from ..school.delivery_experiments import replay_delivery_episode
                replay_delivery_episode(path.parent)
            count+=1
    if primary.exists():
        actual=json.loads(primary.read_text())
        rows=json.loads((source/'weekly/primary/world_results.json').read_text())
        if paired_report(rows)!=actual:
            raise ValueError('independent paired report recomputation mismatch')
        # Independently derive reported inputs from each episode's scorecard.
        for row in rows:
            path=source/'weekly/primary'/f"{row['seed']}_{row['policy']}"
            summary=json.loads((path/'summary.json').read_text())
            episode=json.loads((path/'manifest.json').read_text())
            cards=json.loads((path.parent/(path.name+'_scorecards.json')).read_text())
            allocation,effect=cards['allocation'],cards['simulated_effectiveness']
            if (row['episode_identity']!=episode['identity'] or row['population_identity']!=episode['population_identity']
                    or row['retention_rate']!=summary['simulated_terminal_retention']/summary['initial_cohort_size']
                    or row['cost']!=float(summary['spent_money'])
                    or row['worst_group_retention']!=effect['worst_group_retention']
                    or row['access_gap']!=allocation['max_comparable_need_access_gap']
                    or row['normalized_shortfall']!=allocation['normalized_fairness_shortfall']):
                raise ValueError('report differs from episode outcomes/ledgers')
    adverse=source/'adverse/adverse_report.json'
    if adverse.exists():
        rows=json.loads((source/'adverse/world_results.json').read_text())
        expected={(s,m) for s in frozen['configuration']['phase5']['heldout_world_seeds'][:5]
                  for m in ('wait','fair_point','fair_robust')}
        keys=[(r['seed'],r['policy']) for r in rows]
        if len(keys)!=len(set(keys)) or set(keys)!=expected or adverse_report(rows)!=json.loads(adverse.read_text()):
            raise ValueError('incomplete or inconsistent adverse-effect follow-up')
    label_worlds=0
    prediction=source/'prediction'
    if prediction.exists():
        partitions={}
        cfg=frozen['configuration'];p=cfg['phase5'];base=DeliveryConfig(**cfg['delivery'])
        for split,world_key,pop_key in (
                ('train','training_world_seeds','training_population_seed_base'),
                ('validation','validation_world_seeds','validation_population_seed_base'),
                ('test','prediction_test_world_seeds','prediction_test_population_seed_base')):
            saved=json.loads((prediction/(split+'_reference_labels.json')).read_text())
            partitions[split]=[reference_label_from_record(r) for r in saved]
            if replay:
                regenerated=[]
                for world in p[world_key]:
                    print(f'verifying reference branches {split} world {world}',flush=True)
                    config=replace(base,num_students=p['prediction_cohort_size'],horizon_weeks=p['prediction_weeks'],
                        sessions_required=2,seed=world)
                    c,pop=make_controller(config,split,p[pop_key]+world,'random')
                    regenerated.extend(generate_reference_labels(c,pop,horizon=p['prediction_horizon']))
                    label_worlds+=1
                if normalized(regenerated)!=saved:
                    raise ValueError('independent reference-branch label regeneration mismatch')
        model,training=fit_model(partitions['train'],partitions['validation'])
        if (model.artifact!=json.loads((prediction/'model.json').read_text())
                or training!=json.loads((prediction/'training_selection.json').read_text())):
            raise ValueError('independent train/validation fit identity mismatch')
        report=evaluate_predictor(model,partitions['test'],training['constant_by_horizon'])
        if normalized(report)!=json.loads((prediction/'heldout_metrics.json').read_text()):
            raise ValueError('independent predictive report recomputation mismatch')
    language=source/'language'
    if language.exists():
        from .extraction_evaluation import evaluate_records
        from .phase5_language import validate_partitions
        cases=json.loads((language/'frozen_corpus.json').read_text());validate_partitions(cases)
        if cases!=normalized(build_language_benchmark()):
            raise ValueError('frozen language corpus mismatch')
        report=json.loads((language/'extraction_report.json').read_text())
        for split,split_report in report['splits'].items():
            selected=[c for c in cases if c['split']==split]
            for method in split_report['methods'].values():
                if method['metrics'] is not None and evaluate_records(selected,method['records'])!=method['metrics']:
                    raise ValueError('independent extraction metrics mismatch')
        if normalized(matched_snapshot_evaluation(cases))!=json.loads((language/'matched_snapshots.json').read_text()):
            raise ValueError('independent downstream snapshot recomputation mismatch')
    return dict(status='verified',episodes=count,replayed=replay,reference_worlds_regenerated=label_worlds,
        inventory_files=len(verify_directory(source)))


def run(config_path,output,stage,model_path=None,*,live_llm_model=None,ollama_url=None):
    config=load_configuration(config_path)
    protocol_version=config['phase5']['protocol_version'].split('/')[-1]
    protocol=(ROOT/'docs'/f'phase5_research_protocol_{protocol_version}.md').read_text()
    if stage=='adverse':
        protocol=(ROOT/'docs/phase5_adverse_effect_protocol_v1.md').read_text()
    identity=dict(configuration=config,configuration_identity=digest(config),protocol=protocol,protocol_identity=digest(protocol),
        runtime=runtime_identity(),source_fingerprints=source_fingerprints(),stage=stage,
        live_llm_model=live_llm_model,live_llm_enabled=live_llm_model is not None)
    if stage=='adverse':
        identity['adverse_scenario']=asdict(adverse_effect_config(DeliveryConfig(**config['delivery'])))
    with staged_artifacts(output,identity={'phase5_execution':digest(identity)}) as staging:
        write_exclusive(staging/'frozen_execution.json',identity)
        summary={};model=TrainedWithdrawalRiskModel.load(model_path) if model_path else None
        if stage in ('all','prediction'):
            prediction_output=staging/'prediction';prediction_output.mkdir()
            model,summary['prediction']=run_prediction(config,prediction_output,protocol)
        if stage in ('all','language'):
            language_output=staging/'language';language_output.mkdir()
            extractor=None
            if live_llm_model is not None:
                from ..intervention.observation_extractor import LLMObservationExtractor
                from ..intervention.ollama_client import OllamaClient
                extractor=LLMObservationExtractor(OllamaClient(model=live_llm_model,base_url=ollama_url,
                    timeout=30,num_ctx=8192,temperature=0))
            summary['language']=run_language(language_output,extractor)
        if stage in ('all','pilot','primary'):
            summary['weekly']=run_primary(config,staging/'weekly',protocol,model=model,development_only=stage=='pilot')
        if stage in ('all','secondary'):
            if model is None:
                raise ValueError('secondary trained baseline needs an explicit model artifact')
            summary['secondary']=run_secondary(config,staging/'secondary',protocol,model)
        if stage=='adverse':
            summary['adverse']=run_adverse(config,staging/'adverse',protocol,model)
        write_exclusive(staging/'completion.json',summary)
        seal_directory(staging)
        verify_directory(staging)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(CONFIG))
    parser.add_argument('--stage',choices=('all','prediction','language','pilot','primary','secondary','adverse'),default='pilot')
    parser.add_argument('--output')
    parser.add_argument('--model')
    parser.add_argument('--live-llm-model',help='explicit opt-in live Ollama model; absent means offline only')
    parser.add_argument('--ollama-url')
    parser.add_argument('--verify')
    parser.add_argument('--replay')
    args=parser.parse_args()
    if args.verify:
        result=verify_run(args.verify)
    elif args.replay:
        result=replay_phase5_episode(args.replay,args.output)
    else:
        if args.output is None:
            parser.error('--output must be a fresh destination')
        result=run(args.config,args.output,args.stage,args.model,live_llm_model=args.live_llm_model,ollama_url=args.ollama_url)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':
    main()

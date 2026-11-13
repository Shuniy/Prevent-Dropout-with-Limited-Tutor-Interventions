"""Python 3.13 post-review prediction, language and population robustness pilot.

python -m src.evaluation.phase5_followup --stage acceptance --output results/new
python -m src.evaluation.phase5_followup --verify results/new
"""
import argparse
from collections import Counter
from dataclasses import asdict,replace
from hashlib import sha256
import json
from pathlib import Path
import tomllib

import numpy as np

from .provenance import (digest,runtime_identity,source_fingerprints,staged_artifacts,
    write_exclusive,seal_directory,verify_directory)
from .paired_statistics import summarize
from .phase5_experiments import make_controller,four_scorecards,run_cell,compatibility_audit
from .phase5_prediction_evaluation import (generate_reference_labels,evaluate_predictor,
    reference_label_from_record)
from .phase5_language_followup import run_language_followup,verify_language_report
from .phase5_language_decisions import (FollowupInformationController,boundary_comparison,replay_boundary,
    decision_record,compare_decisions)
from ..intervention.followup_extractor import PromptedFollowupExtractor
from ..intervention.ollama_client import OllamaClient
from ..school.delivery_config import DeliveryConfig
from ..school.delivery_policy import WeeklyDeliveryPolicy
from ..school.delivery_experiments import normalized
from ..school.phase5_delivery import population_environment,save_phase5_episode,replay_phase5_episode
from ..school.population_sampling import load_source_pool,sample_population,population_validation
from ..school.trained_withdrawal_risk import (fit_model,TrainedWithdrawalRiskModel,decision_features,regime_fingerprint)


ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'configs/phase5_followup_v3.toml'
PROTOCOL=ROOT/'docs/phase5_post_review_protocol_v3.md'


def verify_historical_inputs():
    record=json.loads((ROOT/'configs/phase5_historical_inputs_v1.json').read_text())
    if record['contract']!='phase5_historical_inputs/v1' or any(
            sha256((ROOT/name).read_bytes()).hexdigest()!=expected for name,expected in record['sha256'].items()):
        raise ValueError('frozen historical Phase 5 evidence changed')
    if sha256((ROOT/'src/school/trained_withdrawal_risk_v1.py').read_bytes()).hexdigest()!=record['legacy_model_source_sha256']:
        raise ValueError('historical model implementation changed')
    return dict(status='unchanged',origin_commit=record['origin_commit'],files=len(record['sha256'])+1,
        manifest_identity=digest(record))


def load_config(path=CONFIG,*,acceptance=False):
    with Path(path).open('rb') as stream:
        config=tomllib.load(stream)
    p=config['followup'];base=DeliveryConfig(**config['delivery'])
    if p['protocol_version']!='phase5_post_review/v3' or base.sessions_required!=5 or base.session_cadence_weeks!=1:
        raise ValueError('follow-up requires its five-session weekly protocol')
    groups=[p[k] for k in ('training_world_seeds','validation_world_seeds','test_world_seeds')]+p['population_world_seeds']
    flat=[s for seeds in groups for s in seeds]
    if any(not seeds for seeds in groups) or len(flat)!=len(set(flat)) or any(type(s) is not int or s<0 for s in flat):
        raise ValueError('world partitions must be unique, explicit and disjoint')
    if (len(p['validation_world_seeds'])<4 or len(p['population_seeds'])!=len(p['population_world_seeds'])
            or len(set(p['population_seeds']))!=len(p['population_seeds'])):
        raise ValueError('invalid validation or population replication')
    if acceptance:
        p.update(prediction_students=16,prediction_weeks=6,test_world_seeds=p['test_world_seeds'][:1])
        config['delivery']['horizon_weeks']=6
    return config


def prediction_config(config,world):
    p=config['followup']
    return replace(DeliveryConfig(**config['delivery']),num_students=p['prediction_students'],
        horizon_weeks=p['prediction_weeks'],seed=world)


def prediction_partitions(config):
    p=config['followup']
    return [(split,p[world_key],p[pop_key]) for split,world_key,pop_key in (
        ('train','training_world_seeds','training_population_seed_base'),
        ('validation','validation_world_seeds','validation_population_seed_base'),
        ('test','test_world_seeds','test_population_seed_base'))]


def run_prediction(config,output,protocol):
    partitions={};model=None
    for split,worlds,popbase in prediction_partitions(config):
        if split=='test':
            # Test labels do not exist when calibration/selection is frozen.
            model,selection=fit_model(partitions['train'],partitions['validation'])
            model.save(output/'model.json');write_exclusive(output/'training_selection.json',selection)
        rows=[]
        for world in worlds:
            print(f'followup prediction {split} world {world}',flush=True)
            c,pop=make_controller(prediction_config(config,world),split,popbase+world,'random')
            rows.extend(generate_reference_labels(c,pop))
            path=output/'trajectories'/f'{split}_{world}'
            save_phase5_episode(c,pop,path,protocol_text=protocol)
        partitions[split]=rows
        write_exclusive(output/(split+'_reference_labels.json'),normalized(rows))
    report=evaluate_predictor(model,partitions['test'],selection['constant_by_horizon'])
    write_exclusive(output/'heldout_metrics.json',normalized(report))
    if report['scored']==0:
        raise AssertionError('held-out compatible prediction was not exercised')
    # Exercise model predictions as well as reference-label trajectories in replay.
    cfg=prediction_config(config,config['followup']['test_world_seeds'][0])
    c,pop=make_controller(cfg,'test',config['followup']['test_population_seed_base']+cfg.seed,
        'trained_risk_priority',model=model)
    c.run_episode();save_phase5_episode(c,pop,output/'trained_baseline',protocol_text=protocol)
    state=c.snapshots[0];student=next(s for s in state.students if s.enrolled)
    incompatible=replace(cfg,sessions_required=2)
    features=decision_features(student,cutoff_week=state.week,remaining_weeks=state.weeks_remaining,config=incompatible)
    result=model.predict(features,expected_estimate_id=features.estimate_id,expected_model_version=model.version)
    if result.probability is not None or result.unavailable_reason!='reference_regime_mismatch':
        raise AssertionError('unsupported programme duration was accepted')
    write_exclusive(output/'schedule_compatibility.json',dict(status='verified',negative_prediction=asdict(result),
        sessions_required=cfg.sessions_required,cadence=cfg.session_cadence_weeks,
        training_schedule_patterns=model.artifact['training_schedule_patterns']))
    return model,dict(model_version=model.version,scored=report['scored'],abstentions=report['abstentions'],
        ood=report['ood'],metrics=report['pooled_descriptive'],world_mean_brier=report['world_mean_brier'])


def cohort_metadata(config,population_seed):
    pop=sample_population('test',config.num_students,population_seed)
    c,_=make_controller(config,'test',population_seed,'wait')
    state=c.prepare_decision_snapshot()
    anchors=Counter(l.source_anchor for l in pop.lineage)
    groups=Counter(l.linkage_group for l in pop.lineage)
    return normalized(dict(population_seed=population_seed,population_identity=pop.identity,
        source_pool_size=pop.source_pool_size,with_replacement=pop.with_replacement,
        unique_source_anchors=len(anchors),repeated_anchor_descendants=sum(n-1 for n in anchors.values()),
        repeated_linkage_descendants=sum(n-1 for n in groups.values()),
        source_anchor_counts=dict(anchors),linkage_group_counts=dict(groups),lineage=pop.lineage,
        compatibility=compatibility_audit(state,config),
        eligible_support_types=dict(Counter(s.profile.support_type for s in state.students if s.eligible)),
        eligible_audited_groups=dict(Counter(str(getattr(s.profile,config.fairness_grouping_attribute)) for s in state.students if s.eligible)),
        population_validation=population_validation(pop)))


def population_summary(rows,cohorts):
    metrics=('retention_rate','worst_group_retention','normalized_shortfall','access_gap')
    index={}
    for row in rows:
        key=(row['population_seed'],row['seed'],row['policy'])
        if key in index:
            raise ValueError('duplicate population/world/policy cell')
        index[key]=row
    pairs={}
    for population in sorted({r['population_seed'] for r in rows}):
        worlds=sorted({r['seed'] for r in rows if r['population_seed']==population})
        for world in worlds:
            if any((population,world,mode) not in index for mode in ('fair_point','fair_robust')):
                raise ValueError('incomplete paired population cell')
        pairs[population]={metric:[None if any(index[population,w,m][metric] is None for m in ('fair_point','fair_robust'))
            else index[population,w,'fair_robust'][metric]-index[population,w,'fair_point'][metric] for w in worlds]
            for metric in metrics}
    summaries={}
    for metric in metrics:
        complete={p:values[metric] for p,values in pairs.items() if all(v is not None for v in values[metric])}
        by_population={str(p):summarize(values) for p,values in complete.items()}
        means=[v['mean'] for v in by_population.values()]
        within=[float(np.var(v,ddof=1)) for v in complete.values() if len(v)>1]
        # The between-mean variance contains residual Monte Carlo variation.
        noise=[float(np.var(v,ddof=1))/len(v) for v in complete.values() if len(v)>1]
        between=float(np.var(means,ddof=1)) if len(means)>1 else None
        summaries[metric]=dict(contrast='FairRobust_minus_FairPoint',population_clusters=summarize(means),
            by_population=by_population,within_population_world_variance_mean=float(np.mean(within)) if within else None,
            observed_population_mean_variance=between,
            estimated_between_population_variance=max(0.,between-float(np.mean(noise))) if between is not None and noise else None,
            unavailable_populations=sorted(set(pairs)-set(complete)),
            decomposition='descriptive method of moments; nested independent world seeds; equal population weighting')
    overlap={}
    for i,a in enumerate(cohorts):
        for b in cohorts[i+1:]:
            overlap[f"{a['population_seed']}|{b['population_seed']}"]=dict(
                shared_source_anchors=len(set(a['source_anchor_counts'])&set(b['source_anchor_counts'])),
                shared_linkage_groups=len(set(a['linkage_group_counts'])&set(b['linkage_group_counts'])))
    return dict(contract='population_cluster_pilot/v1',populations=len(pairs),episodes=len(rows),
        outcomes=summaries,ancestry_overlap=overlap,
        inference='conditional on finite source-test pool; seeded simulated cohorts are not independent observed schools; pilot only',
        feasibility=dict(nonzero_offer_episodes=sum(r['actual_support_offers']>0 for r in rows),
            exercised_group_episodes=sum(r['compatibility_audit']['exercised_design'] for r in rows),
            solver_failures=sum(r['solver_failures'] for r in rows),incomplete_stages=sum(r['incomplete_stages'] for r in rows)))


def run_population(config,output,protocol,*,acceptance=False):
    p=config['followup'];base=DeliveryConfig(**config['delivery']);rows=[];cohorts=[]
    populations=list(zip(p['population_seeds'],p['population_world_seeds']))
    if acceptance:
        populations=[(populations[0][0],populations[0][1][:1])]
    for population_seed,worlds in populations:
        metadata=cohort_metadata(base,population_seed);cohorts.append(metadata)
        write_exclusive(output/f'cohort_{population_seed}.json',metadata)
        rows.extend(run_cell(base,worlds,'test',population_seed,('fair_point','fair_robust'),
            'group_dependent',output/f'population_{population_seed}',protocol,require_nonvacuous=acceptance))
    report=population_summary(rows,cohorts)
    if acceptance and (report['feasibility']['nonzero_offer_episodes']!=2 or report['feasibility']['solver_failures']
            or report['feasibility']['incomplete_stages']):
        raise AssertionError('mandatory Phase 5 policy acceptance failed')
    write_exclusive(output/'world_results.json',rows);write_exclusive(output/'cohorts.json',cohorts)
    write_exclusive(output/'population_report.json',report)
    return report


def run_language_decisions(config,output,protocol,extractor_factory=None,*,llm_downstream='none'):
    boundary=boundary_comparison(output/'controlled_boundary',extractor_factory if llm_downstream in ('boundary','all') else None)
    base=DeliveryConfig(**config['delivery']);arms={};decisions={}
    for arm in ('structured_available','note_content_gold','existing_deterministic','missing_notes','corrupted_notes','prompted_llm'):
        if arm=='prompted_llm' and (extractor_factory is None or llm_downstream!='all'):
            arms[arm]=dict(status='unexecuted_not_requested');continue
        env,pop=population_environment(base,population_mode='source_held_out',split='test',population_seed=config['followup']['population_seeds'][0])
        c=FollowupInformationController(env,WeeklyDeliveryPolicy(base,'fair_point'),language_condition=arm,
            extractor=extractor_factory() if arm=='prompted_llm' else None)
        state=c.prepare_decision_snapshot();action=c.policy.plan(state)
        decisions[arm]=decision_record(c,state,action)
        c.run_episode();c.validate()
        save_phase5_episode(c,pop,output/arm,protocol_text=protocol)
        cards=four_scorecards(c,pop);write_exclusive(output/(arm+'_scorecards.json'),cards)
        arms[arm]=dict(status='executed',scorecards=cards,
            allocations=normalized([a.offers for a in c.decisions]),cancellations=normalized([a.cancel_programme_ids for a in c.decisions]))
        if arm=='prompted_llm':
            arms[arm]['inference']=dict(request_attempts=c.extractor.calls,model_responses=c.extractor.responses,
                status='unexecuted_model_unavailable' if c.extractor.responses==0 else 'executed_real_model')
    gold=decisions['note_content_gold']
    report=dict(contract='source_heldout_language_decisions/v2',arms=arms,matched_snapshots=decisions,
        matched_differences={arm:compare_decisions(gold,v) for arm,v in decisions.items()},
        controlled_boundary=boundary['comparisons'],
        limitation='small designed language conditions and one cohort; differences are not causal improvements')
    write_exclusive(output/'downstream_report.json',report)
    return dict(arms={k:v['status'] for k,v in arms.items()},controlled_boundary=boundary['comparisons'])


def verify_followup(source):
    source=Path(source);verify_directory(source)
    execution=json.loads((source/'frozen_execution.json').read_text());config=execution['configuration']
    runtime=runtime_identity()
    if (execution['contract']!='phase5_post_review_execution/v3' or execution['source_fingerprints']!=source_fingerprints()
            or digest(config)!=execution['configuration_identity'] or digest(execution['protocol'])!=execution['protocol_identity']
            or any(execution['runtime'][k]!=runtime[k] for k in ('python','implementation','dependencies'))):
        raise ValueError('exact follow-up verification requires frozen protocol/config/source/runtime')
    completion=json.loads((source/'completion.json').read_text())
    required={'acceptance':{'prediction','population','language','downstream'},
              'all':{'prediction','population','language','downstream'},
              'prediction':{'prediction'},'population':{'population'},'language':{'language','downstream'}}[execution['stage']]
    if not required<=completion.keys() or any(not (source/name).is_dir() for name in required):
        raise ValueError('missing mandatory completed acceptance artifact')
    if execution['historical_inputs']!=verify_historical_inputs():
        raise ValueError('historical evidence validation differs from frozen execution')
    pool=load_source_pool()
    if json.loads((source/'source_manifest_validation.json').read_text())!=dict(
            status='verified',source_identity=pool.fingerprint,split_sizes={s:len(pool.partition(s)) for s in ('train','validation','test')}):
        raise ValueError('source manifest validation mismatch')
    episodes=0
    for path in sorted(source.rglob('manifest.json')):
        record=json.loads(path.read_text())
        if record.get('contract','').startswith('phase5_source_weekly/replay/'):
            if record['protocol_text']!=execution['protocol']:
                raise ValueError('episode protocol differs from frozen execution')
            def check(c,pop):
                cards=path.parent.parent/(path.parent.name+'_scorecards.json')
                if cards.exists() and four_scorecards(c,pop)!=json.loads(cards.read_text()):
                    raise ValueError('independent derived-scorecard mismatch')
                downstream=source/'downstream/downstream_report.json'
                if path.parent.parent==source/'downstream' and downstream.exists():
                    report=json.loads(downstream.read_text());arm=path.parent.name
                    if (report['arms'][arm]['scorecards']!=four_scorecards(c,pop)
                            or report['matched_snapshots'][arm]!=decision_record(c,c.snapshots[0],c.decisions[0])
                            or report['arms'][arm]['allocations']!=normalized([a.offers for a in c.decisions])
                            or report['arms'][arm]['cancellations']!=normalized([a.cancel_programme_ids for a in c.decisions])):
                        raise ValueError('downstream report differs from replayed decisions/outcomes')
            replay_phase5_episode(path.parent,on_verified_controller=check);episodes+=1
        elif record.get('contract')=='language_controlled_boundary/replay/v2':
            def check_boundary(c):
                report=json.loads((path.parent.parent/'boundary_report.json').read_text())
                arm=path.parent.name
                if (report['arms'][arm]['snapshot']!=decision_record(c,c.snapshots[1],c.decisions[1])
                        or report['arms'][arm]['later_offers']!=normalized([a.offers for a in c.decisions[2:]])):
                    raise ValueError('controlled boundary report differs from exact replay')
            replay_boundary(path.parent,on_verified_controller=check_boundary);episodes+=1
    prediction=source/'prediction';reference_worlds=0
    if prediction.exists():
        partitions={}
        for split,worlds,popbase in prediction_partitions(config):
            saved=json.loads((prediction/(split+'_reference_labels.json')).read_text())
            partitions[split]=[reference_label_from_record(r) for r in saved]
            regenerated=[]
            for world in worlds:
                c,pop=make_controller(prediction_config(config,world),split,popbase+world,'random')
                regenerated.extend(generate_reference_labels(c,pop));reference_worlds+=1
            if normalized(regenerated)!=saved:
                raise ValueError('independent exact reference-label replay mismatch')
        model,selection=fit_model(partitions['train'],partitions['validation'])
        if model.artifact!=json.loads((prediction/'model.json').read_text()) or selection!=json.loads((prediction/'training_selection.json').read_text()):
            raise ValueError('independent training/validation fit mismatch')
        report=evaluate_predictor(model,partitions['test'],selection['constant_by_horizon'])
        if normalized(report)!=json.loads((prediction/'heldout_metrics.json').read_text()):
            raise ValueError('independent predictive metrics mismatch')
        if completion['prediction']!=dict(model_version=model.version,scored=report['scored'],abstentions=report['abstentions'],
                ood=report['ood'],metrics=report['pooled_descriptive'],world_mean_brier=report['world_mean_brier']):
            raise ValueError('prediction completion summary mismatch')
    population=source/'population'
    if population.exists():
        rows=json.loads((population/'world_results.json').read_text());cohorts=json.loads((population/'cohorts.json').read_text())
        expected=list(zip(config['followup']['population_seeds'],config['followup']['population_world_seeds']))
        if execution['stage']=='acceptance':
            expected=[(expected[0][0],expected[0][1][:1])]
        keys=[(r['population_seed'],r['seed'],r['policy']) for r in rows]
        if set(keys)!={(p,w,m) for p,ws in expected for w in ws for m in ('fair_point','fair_robust')} or len(keys)!=len(set(keys)):
            raise ValueError('incomplete population matrix')
        if population_summary(rows,cohorts)!=json.loads((population/'population_report.json').read_text()):
            raise ValueError('population cluster summary mismatch')
        if completion['population']!=population_summary(rows,cohorts):
            raise ValueError('population completion summary mismatch')
        if cohorts!=[cohort_metadata(DeliveryConfig(**config['delivery']),p) for p,_ in expected]:
            raise ValueError('independent cohort ancestry/feasibility metadata mismatch')
        for row in rows:
            cell=population/f"population_{row['population_seed']}"/f"{row['seed']}_{row['policy']}"
            cards=json.loads((cell.parent/(cell.name+'_scorecards.json')).read_text())
            allocation,effect=cards['allocation'],cards['simulated_effectiveness']
            if (row['retention_rate']!=effect['retention_rate'] or row['worst_group_retention']!=effect['worst_group_retention']
                    or row['normalized_shortfall']!=allocation['normalized_fairness_shortfall']
                    or row['access_gap']!=allocation['max_comparable_need_access_gap']):
                raise ValueError('population report differs from independent episode scorecard')
    language=source/'language'
    if language.exists():
        report=json.loads((language/'extraction_report.json').read_text())
        verify_language_report(json.loads((language/'frozen_corpus.json').read_text()),report)
        summary=dict(llm=report['llm'],independent_human_validation=report['independent_human_validation'],
            splits={s:{m:v['metrics']['micro'] if v['metrics'] else None for m,v in entry['methods'].items()} for s,entry in report['splits'].items()})
        if completion['language']!=summary:
            raise ValueError('language completion summary mismatch')
    downstream=source/'downstream/downstream_report.json'
    if downstream.exists():
        report=json.loads(downstream.read_text())
        if report['matched_differences']!={arm:compare_decisions(report['matched_snapshots']['note_content_gold'],value)
                                         for arm,value in report['matched_snapshots'].items()}:
            raise ValueError('matched decision difference recomputation mismatch')
        boundary=json.loads((source/'downstream/controlled_boundary/boundary_report.json').read_text())
        expected_differences={arm:compare_decisions(boundary['arms']['note_content_gold']['snapshot'],value['snapshot']) | dict(
            later_allocation_changed=boundary['arms']['note_content_gold']['later_offers']!=value['later_offers'])
            for arm,value in boundary['arms'].items() if 'snapshot' in value}
        if boundary['comparisons']!=expected_differences or report['controlled_boundary']!=expected_differences:
            raise ValueError('controlled boundary differences mismatch')
        if completion['downstream']!=dict(arms={k:v['status'] for k,v in report['arms'].items()},controlled_boundary=expected_differences):
            raise ValueError('downstream completion summary mismatch')
    return dict(status='verified',episodes=episodes,reference_worlds_regenerated=reference_worlds,
        offline_replay=True,inventory_files=len(verify_directory(source)))


def run(config_path,output,stage,*,llm_model=None,ollama_url=None,timeout=30,retries=0,temperature=0.,num_ctx=8192,
        model_digest=None,prompt_version='observable_note_prompt/v2',corpus_path=None,llm_downstream='none'):
    if llm_downstream not in ('none','boundary','all'):
        raise ValueError('unsupported downstream inference scope')
    config=load_config(config_path,acceptance=stage=='acceptance');protocol=PROTOCOL.read_text()
    execution=dict(contract='phase5_post_review_execution/v3',configuration=config,configuration_identity=digest(config),
        protocol=protocol,protocol_identity=digest(protocol),runtime=runtime_identity(),source_fingerprints=source_fingerprints(),stage=stage,
        historical_inputs=verify_historical_inputs(),
        inference=dict(enabled=llm_model is not None,model=llm_model,timeout=timeout,retries=retries,llm_downstream=llm_downstream,
            temperature=temperature,num_ctx=num_ctx,model_digest=model_digest,prompt_version=prompt_version))
    factory=(lambda:PromptedFollowupExtractor(OllamaClient(model=llm_model,base_url=ollama_url,timeout=timeout,
        num_ctx=num_ctx,temperature=temperature,model_digest=model_digest),retries=retries,prompt_version=prompt_version)) if llm_model else None
    with staged_artifacts(output,identity={'followup':digest(execution)}) as stage_dir:
        write_exclusive(stage_dir/'frozen_execution.json',execution)
        pool=load_source_pool();write_exclusive(stage_dir/'source_manifest_validation.json',dict(
            status='verified',source_identity=pool.fingerprint,split_sizes={s:len(pool.partition(s)) for s in ('train','validation','test')}))
        summary={}
        if stage in ('acceptance','all','prediction'):
            _,summary['prediction']=run_prediction(config,stage_dir/'prediction',protocol)
        if stage in ('acceptance','all','population'):
            summary['population']=run_population(config,stage_dir/'population',protocol,acceptance=stage=='acceptance')
        if stage in ('acceptance','all','language'):
            report=run_language_followup(stage_dir/'language',factory() if factory else None,corpus_path)
            summary['language']=dict(llm=report['llm'],independent_human_validation=report['independent_human_validation'],
                splits={s:{m:v['metrics']['micro'] if v['metrics'] else None for m,v in entry['methods'].items()} for s,entry in report['splits'].items()})
            summary['downstream']=run_language_decisions(config,stage_dir/'downstream',protocol,factory,llm_downstream=llm_downstream)
        write_exclusive(stage_dir/'completion.json',normalized(summary));seal_directory(stage_dir)
        verification=verify_followup(stage_dir)
    return dict(output=str(output),summary=summary,verification=verification)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(CONFIG));parser.add_argument('--output')
    parser.add_argument('--stage',choices=('acceptance','all','prediction','population','language'),default='acceptance')
    parser.add_argument('--verify');parser.add_argument('--llm-model');parser.add_argument('--ollama-url')
    parser.add_argument('--timeout',type=float,default=30);parser.add_argument('--retries',type=int,default=0)
    parser.add_argument('--temperature',type=float,default=0);parser.add_argument('--num-ctx',type=int,default=8192)
    parser.add_argument('--model-digest');parser.add_argument('--prompt-version',default='observable_note_prompt/v2')
    parser.add_argument('--llm-downstream',choices=('none','boundary','all'),default='none',
        help='explicit inference scope beyond the frozen benchmark; all runs a model call for every own-trajectory note')
    parser.add_argument('--corpus',help='versioned external annotation contract JSON; copied before any inference')
    args=parser.parse_args()
    if args.verify:
        result=verify_followup(args.verify)
    else:
        if args.output is None:
            parser.error('--output requires a fresh destination')
        if args.timeout<=0 or args.num_ctx<1 or args.temperature<0:
            parser.error('positive timeout/context and nonnegative temperature required')
        result=run(args.config,args.output,args.stage,llm_model=args.llm_model,ollama_url=args.ollama_url,
            timeout=args.timeout,retries=args.retries,temperature=args.temperature,num_ctx=args.num_ctx,
            model_digest=args.model_digest,prompt_version=args.prompt_version,corpus_path=args.corpus,llm_downstream=args.llm_downstream)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':
    main()

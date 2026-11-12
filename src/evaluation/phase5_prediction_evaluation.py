"""Evaluator-owned trajectory branches and outcome-based predictive scorecards."""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from .paired_statistics import summarize
from .provenance import digest
from ..school.delivery_contracts import DeliveryAction
from ..school.student_condition import StudentCondition
from ..school.trained_withdrawal_risk import TARGET, REFERENCE, DecisionFeatures, decision_features


@dataclass(frozen=True)
class ReferenceLabel:
    features: DecisionFeatures
    withdrawal_event: bool
    split: str
    linkage_group: str
    source_anchor: str
    population_identity: str
    world_seed: int
    landmark_week: int
    group: str
    analytical_target_matched: float
    branch_identity: str
    source_fingerprint: str = ''
    population_seed: int = 0
    label_generator: str = 'exact_weekly_reference_branch/v1'
    target: str = TARGET
    reference_policy: str = REFERENCE


def reference_label_from_record(record):
    values=dict(record)
    features=dict(values.pop('features'))
    features['numeric']=tuple(tuple(pair) for pair in features['numeric'])
    return ReferenceLabel(features=DecisionFeatures(**features),**values)


def withdrawal_event(conditions):
    """A withdrawal followed by re-entry still satisfies the event target."""
    return any(c == StudentCondition.WITHDRAWN for c in conditions)


def analytical_event_probability(student, config, horizon):
    """Target-matched first-event probability, including continuing commitments.

    Kill withdrawn mass after every weekly operator. Unlike terminal risk this
    remains a first-passage probability when re-entry is possible. The joint
    active/inactive calculation follows the existing delivery forecast law.
    """
    if not student.enrolled or horizon <= 0:
        return None
    cutoff = student.estimate.as_of_week
    active_programmes = [p for p in student.programmes if p.status in ('ACTIVE','SCHEDULED')]
    if len(active_programmes) > 1:
        raise ValueError('one accepted programme per student required')
    weeks = {s.week for p in active_programmes for s in p.sessions if s.status == 'RESERVED' and s.week >= cutoff}
    belief = np.array(student.estimate.condition_probabilities)
    belief[3] = 0
    if not belief.sum():
        raise ValueError('enrolled registry contradicts posterior')
    belief /= belief.sum()
    active, inactive = belief.copy(), np.zeros(4)
    q = config.attendance_probability*config.delivery_probability
    wait = np.array(config.weekly_wait_matrix)
    for w in range(cutoff,cutoff+horizon):
        if active_programmes and active_programmes[0].offer_week < w <= max(weeks,default=cutoff-1):
            cancelled = active*config.cancellation_probability
            active, inactive = active-cancelled,inactive+cancelled
        matrix = q*config.treatment_matrix+(1-q)*wait if w in weeks else wait
        active, inactive = active@matrix,inactive@wait
        active[3], inactive[3] = 0,0
    return float(np.clip(1-active.sum()-inactive.sum(),0,1))


def generate_reference_labels(controller, population, *, horizon=4, landmark_weeks=None):
    """Continue a FACTUAL policy; fork each landmark BEFORE its next action.

    A branch is an exact deepcopy of the weekly environment (including accepted
    commitments), executed through the existing step mechanism with no new
    offers or controller cancellations. It cannot modify the factual trajectory.
    Labels/provenance never enter features, estimator or runtime risk inference.
    """
    env = controller.environment
    lineage = {r.student_id:r for r in population.lineage}
    rows = []
    while not env.done:
        state = controller.prepare_decision_snapshot()
        if landmark_weeks is None or env.week in landmark_weeks:
            enrolled = [s for s in state.students if s.enrolled]
            features = {s.student_id:decision_features(s,cutoff_week=state.week,
                remaining_weeks=state.weeks_remaining,config=env.config,horizon=horizon) for s in enrolled}
            branch = deepcopy(env)
            duration = min(horizon,state.weeks_remaining)
            outcomes = defaultdict(list)
            for _ in range(duration):
                branch.step(DeliveryAction(status='reference_no_new_offers'))
                for sid,condition in branch.evaluator_truth[-1][1]:
                    outcomes[sid].append(condition)
            branch_identity = digest(dict(world_seed=env.config.seed,landmark=state.week,horizon=duration,
                reference=REFERENCE,initial_conditions=env.evaluator_truth[-1],
                commitments=asdict(state)['students'],truth=branch.evaluator_truth[-duration:],
                draws=branch.exogenous_draws[len(env.exogenous_draws):]))
            for student in enrolled:
                sid = student.student_id
                l = lineage[sid]
                rows.append(ReferenceLabel(features[sid],withdrawal_event(outcomes[sid]),
                    population.split,l.linkage_group,l.source_anchor,population.identity,env.config.seed,state.week,
                    str(getattr(student.profile,env.config.fairness_grouping_attribute)),
                    analytical_event_probability(student,env.config,duration),branch_identity,
                    source_fingerprint=population.source_fingerprint,population_seed=population.population_seed))
        controller.run_week()
    controller.final_snapshot = controller.prepare_decision_snapshot()
    controller.validate()
    return tuple(rows)


def _metrics(labels, probabilities, *, bins=10):
    y, p = np.asarray(labels,dtype=int), np.asarray(probabilities,dtype=float)
    if len(y) == 0:
        return dict(n=0,events=0,prevalence=None,brier=None,log_loss=None,auroc=None,average_precision=None,reliability=[])
    if not np.isfinite(p).all() or np.any((p<0)|(p>1)):
        raise ValueError('invalid scored probabilities')
    clipped = np.clip(p,1e-12,1-1e-12)
    reliability=[]
    for index in range(bins):
        mask = (p >= index/bins) & ((p < (index+1)/bins) if index < bins-1 else (p <= 1))
        reliability.append(dict(lower=index/bins,upper=(index+1)/bins,n=int(mask.sum()),
            mean_prediction=float(p[mask].mean()) if mask.any() else None,
            event_rate=float(y[mask].mean()) if mask.any() else None))
    both = len(set(y)) == 2
    return dict(n=len(y),events=int(y.sum()),prevalence=float(y.mean()),brier=float(np.mean((p-y)**2)),
        log_loss=float(-np.mean(y*np.log(clipped)+(1-y)*np.log1p(-clipped))),
        auroc=float(roc_auc_score(y,p)) if both else None,
        average_precision=float(average_precision_score(y,p)) if both else None,reliability=reliability)


def evaluate_predictor(model, rows, constants, *, review_fraction=.2):
    provenance = model.artifact['provenance']
    if len({r.split for r in rows})>1:
        raise ValueError('predictive evaluation requires a single source split')
    if any(r.target!=TARGET or r.reference_policy!=REFERENCE or r.landmark_week!=r.features.cutoff_week for r in rows):
        raise ValueError('label target/reference/cutoff mismatch')
    if rows and rows[0].split == 'test':
        if ({r.linkage_group for r in rows} & set(provenance['training_groups']+provenance['validation_groups'])
                or {r.world_seed for r in rows} & set(provenance['training_worlds']+provenance['validation_worlds'])):
            raise ValueError('held-out predictive evaluation leakage')
    if not 0 < review_fraction <= 1:
        raise ValueError('invalid review capacity')
    records=[]
    for row in rows:
        p = model.predict(row.features, expected_estimate_id=row.features.estimate_id,expected_model_version=model.version)
        records.append(dict(label=asdict(row),prediction=asdict(p),
            constant=constants.get(str(row.features.horizon))))
    scored = [r for r in records if r['prediction']['probability'] is not None]
    def report(selected):
        labels = [int(r['label']['withdrawal_event']) for r in selected]
        return {name:_metrics(labels,[r['prediction']['probability'] if name=='trained' else
            r['constant'] if name=='training_constant' else r['label']['analytical_target_matched'] for r in selected])
            for name in ('trained','training_constant','analytical_target_matched')}
    worlds = sorted({r['label']['world_seed'] for r in scored})
    by_world = {str(w):report([r for r in scored if r['label']['world_seed']==w]) for w in worlds}
    recall=[]
    for world in worlds:
        landmarks = sorted({r['label']['landmark_week'] for r in scored if r['label']['world_seed']==world})
        for cutoff in landmarks:
            selected=[r for r in scored if (r['label']['world_seed'],r['label']['landmark_week'])==(world,cutoff)]
            capacity=max(1,int(np.floor(review_fraction*len(selected))))
            selected.sort(key=lambda r:(-r['prediction']['probability'],r['prediction']['student_id']))
            events=sum(r['label']['withdrawal_event'] for r in selected)
            caught=sum(r['label']['withdrawal_event'] for r in selected[:capacity])
            recall.append(dict(world_seed=world,cutoff=cutoff,capacity=capacity,events=events,caught=caught,
                recall=caught/events if events else None))
    return dict(contract='heldout_simulated_prediction/v1',target=TARGET,reference=REFERENCE,
        model_version=model.version,landmark_counts=len(rows),scored=len(scored),
        abstentions=len(rows)-len(scored),ood=sum(bool(r['prediction']['ood_reasons']) for r in records),
        unavailable_reasons=dict(Counter(r['prediction']['unavailable_reason'] for r in records
            if r['prediction']['unavailable_reason'] is not None)),
        ood_reasons=dict(Counter(reason for r in records for reason in r['prediction']['ood_reasons'])),
        missing_features=sum(bool(r['prediction']['missing_features']) for r in records),
        pooled_descriptive=report(scored),by_world=by_world,
        world_mean_brier={name:summarize([by_world[str(w)][name]['brier'] for w in worlds])
                         for name in ('trained','training_constant','analytical_target_matched')},
        by_horizon={str(h):report([r for r in scored if r['prediction']['horizon']==h]) for h in sorted({r.features.horizon for r in rows})},
        by_missingness={str(flag):report([r for r in scored if bool(r['prediction']['missing_features'])==flag]) for flag in (False,True)},
        by_documentation={name:report([r for r in scored if
            ('no_assimilated_signal' if dict(r['label']['features']['numeric'])['source_age'] is None
             else 'stale_or_missing_current' if dict(r['label']['features']['numeric'])['missing_signal'] else 'fresh')==name])
            for name in ('fresh','stale_or_missing_current','no_assimilated_signal')},
        by_group={g:dict(**report([r for r in scored if r['label']['group']==g]),
            inference='descriptive_only_small_groups_no_independent_landmark_intervals') for g in sorted({r.group for r in rows})},
        recall_at_capacity=recall,records=records,
        inference_unit='independent_world; overlapping landmarks are descriptive, not independent replicates')


def calibration_plot(report,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(5,4))
    ax.plot([0,1],[0,1],'--',color='grey')
    for name,values in report['pooled_descriptive'].items():
        cells=[c for c in values['reliability'] if c['n']]
        ax.plot([c['mean_prediction'] for c in cells],[c['event_rate'] for c in cells], 'o-',label=name)
    ax.set(xlabel='Predicted event probability',ylabel='Simulated withdrawal event frequency',xlim=(0,1),ylim=(0,1))
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path,dpi=160)
    plt.close(fig)

"""Transparent event-risk prediction; distinct from terminal analytical risks.

Features accept only a public WeeklyStudent. Truth is confined to the separately
named offline reference-label generator in phase5_prediction_evaluation.py.
Artifacts are JSON coefficients, never executable pickles.
"""
from dataclasses import asdict, dataclass
from importlib.metadata import version as dependency_version
import json
from pathlib import Path
import math

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression

from ..evaluation.provenance import digest, write_exclusive


TARGET = 'simulated_any_withdrawal_within_horizon/v1'
REFERENCE = 'continue_accepted_schedules_no_new_offers/v1'
FEATURE_SCHEMA = 'authorized_weekly_schedule_features/v2'
MODEL_CONTRACT = 'trained_withdrawal_model/v2'
NUMERIC = ('belief_stable', 'belief_vulnerable', 'belief_disengaged', 'belief_withdrawn',
    'entropy', 'source_age', 'missing_signal', 'conflict', 'rejected', 'evidence_count',
    'need_score', 'waiting_weeks', 'delivered_sessions', 'reserved_sessions', 'active_programme', 'horizon',
    'scheduled_session_week_0', 'scheduled_session_week_1', 'scheduled_session_week_2', 'scheduled_session_week_3')


def regime_fingerprint(config):
    # A deliberately conservative compatibility boundary. Budgets and cohort size
    # do not affect an already accepted individual's no-new-offers reference law.
    return digest(dict(parameters={k:getattr(config,k) for k in ('world_mode','contract_version','time_unit',
        'sessions_required','session_cadence_weeks','session_duration_hours','rescheduling_policy',
        'acceptance_probability','transition_version','weekly_wait_matrix',
        'weekly_tutoring_matrix','effect_strength','attendance_probability','delivery_probability',
        'cancellation_probability','terminate_on_withdrawal')},
        schedule='first_session_at_offer_week; fixed_cadence; no_rescheduling/v1',
        commitments='one_accepted_programme; cancellation_before_later_week_service; no_controller_cancellations; independent_attendance_and_delivery; transition_after_service/v1'))


@dataclass(frozen=True)
class DecisionFeatures:
    student_id: str
    cutoff_week: int
    estimate_id: str
    enrolled: bool
    horizon: int
    numeric: tuple[tuple[str, float | None], ...]
    support_type: str
    regime_identity: str
    schema: str = FEATURE_SCHEMA
    schedule_issues: tuple[str, ...] = ()

    @property
    def fingerprint(self):
        return digest(asdict(self))


def decision_features(student, *, cutoff_week, remaining_weeks, config, horizon=4):
    if type(horizon) is not int or not 1 <= horizon <= 4:
        raise ValueError('forecast horizon must be an integer in [1,4]')
    if remaining_weeks < 0 or student.estimate.as_of_week != cutoff_week:
        raise ValueError('stale estimate or invalid remaining horizon')
    e, info = student.estimate, dict(student.estimate.uncertainty)
    if e.last_observation_week is not None and not 0 <= e.last_observation_week < cutoff_week:
        raise ValueError('future condition observation')
    belief = np.asarray(e.condition_probabilities)
    age = cutoff_week-1-e.last_observation_week if e.last_observation_week is not None else None
    active = tuple(p for p in student.programmes if p.status in ('SCHEDULED','ACTIVE'))
    if any(p.offer_week >= cutoff_week for p in student.programmes):
        raise ValueError('future programme history')
    issues = []
    if len(active) > 1:
        issues.append('multiple_active_programmes')
    for programme in student.programmes:
        weeks = tuple(s.week for s in programme.sessions)
        if (programme.student_id != student.student_id or not weeks
                or len(weeks) != config.sessions_required
                or weeks != config.schedule(weeks[0])
                or weeks[0] != programme.offer_week):
            issues.append('unsupported_programme_schedule')
        for session in programme.sessions:
            if session.week >= cutoff_week and session.status in ('DELIVERED','MISSED'):
                raise ValueError('future session realization is not authorized')
            if session.week < cutoff_week and session.status == 'RESERVED':
                issues.append('past_unresolved_reservation')
            if session.status not in ('RESERVED','DELIVERED','MISSED','RELEASED'):
                issues.append('unknown_session_status')
        if programme.status not in ('REFUSED','SCHEDULED','ACTIVE','CANCELLED','COMPLETED','INCOMPLETE'):
            issues.append('unknown_programme_status')
        if programme not in active and any(s.status == 'RESERVED' for s in programme.sessions):
            issues.append('inactive_programme_reservation')
    values = dict(zip(NUMERIC[:4], map(float, belief)))
    values.update(entropy=float(-sum(p*math.log(p) for p in belief if p > 0)),
        source_age=age, missing_signal=float(info.get('missing_current_signal', age is None or age > 0)),
        conflict=float(info.get('condition_conflict', False)), rejected=float(info.get('rejected_condition_observation',False)),
        evidence_count=float(len(e.evidence_ids)), need_score=student.profile.need_score,
        waiting_weeks=float(student.waiting_weeks),
        delivered_sessions=float(sum(p.delivered_sessions for p in student.programmes)),
        reserved_sessions=float(sum(s.status == 'RESERVED' and s.week >= cutoff_week for p in active for s in p.sessions)),
        active_programme=float(bool(active)), horizon=float(min(horizon, remaining_weeks)))
    values.update({f'scheduled_session_week_{offset}':float(sum(
        s.status == 'RESERVED' and s.week == cutoff_week+offset
        for p in active for s in p.sessions)) if offset < min(horizon,remaining_weeks) else 0.
        for offset in range(4)})
    return DecisionFeatures(student.student_id, cutoff_week, e.estimate_id, student.enrolled,
        min(horizon,remaining_weeks), tuple((k,values[k]) for k in NUMERIC),
        student.profile.support_type, regime_fingerprint(config), schedule_issues=tuple(sorted(set(issues))))


@dataclass(frozen=True)
class TrainedRiskPrediction:
    student_id: str
    cutoff_week: int
    horizon: int
    input_estimate_id: str
    probability: float | None
    unavailable_reason: str | None
    model_version: str
    calibration_version: str
    feature_fingerprint: str
    missing_features: tuple[str, ...]
    ood_reasons: tuple[str, ...]
    target: str = TARGET
    reference_policy: str = REFERENCE
    time_unit: str = 'week'
    fallback: str = 'none_abstain/v1'


def _numeric(features):
    values = dict(features.numeric)
    if features.schema != FEATURE_SCHEMA or tuple(values) != NUMERIC:
        raise ValueError('feature schema mismatch; arbitrary features/labels prohibited')
    if any(v is not None and not math.isfinite(v) for v in values.values()):
        raise ValueError('nonfinite input feature')
    if values['horizon'] != features.horizon:
        raise ValueError('inconsistent forecast horizon')
    if any(values[f'scheduled_session_week_{i}'] not in (0.,1.) for i in range(4)):
        raise ValueError('scheduled session feature must be an authorized reservation indicator')
    if any(values[f'scheduled_session_week_{i}'] for i in range(features.horizon,4)):
        raise ValueError('reservation indicator lies beyond target horizon')
    return [values[k] for k in NUMERIC]


class TrainedWithdrawalRiskModel:
    def __init__(self, artifact):
        artifact = json.loads(json.dumps(artifact, allow_nan=False))
        version = artifact.pop('model_version', None)
        if artifact.get('contract') != MODEL_CONTRACT or digest(artifact) != version:
            raise ValueError('model version/hash mismatch')
        size=2*len(NUMERIC)+len(artifact['categories'])
        if (artifact['schema']!=FEATURE_SCHEMA or artifact['target']!=TARGET or artifact['reference']!=REFERENCE
                or len(artifact['coefficients'])!=size or len(artifact['scales'])!=size
                or any(s<=0 for s in artifact['scales'])
                or any(len(artifact[k])!=len(NUMERIC) for k in ('medians','minimum','maximum'))
                or not artifact.get('training_schedule_patterns')
                or any(not math.isfinite(v) for v in (*artifact['coefficients'],artifact['intercept'],*artifact['scales']))
                or artifact['calibration']['method'] not in ('none','sigmoid')):
            raise ValueError('invalid trained model feature/target/preprocessing contract')
        self.artifact = {**artifact, 'model_version':version}
        self.version = version

    @classmethod
    def load(cls, path):
        if not Path(path).is_file():
            raise FileNotFoundError('trained model unavailable; no fallback configured')
        return cls(json.loads(Path(path).read_text()))

    def save(self, path):
        write_exclusive(path, self.artifact)

    def _transform(self, features):
        a = self.artifact
        row = _numeric(features)
        numeric = np.array([a['medians'][i] if v is None else v for i,v in enumerate(row)])
        missing = np.array([v is None for v in row], dtype=float)
        cats = np.array([features.support_type == c for c in a['categories']], dtype=float)
        return np.r_[numeric, missing, cats] / np.asarray(a['scales'])

    def predict(self, features, *, expected_estimate_id, expected_model_version, reference_regime=REFERENCE):
        if features.estimate_id != expected_estimate_id:
            raise ValueError('stale estimate identity')
        if self.version != expected_model_version:
            raise ValueError('model version mismatch')
        a, reason, ood = self.artifact, None, []
        try:
            row = _numeric(features)
        except ValueError:
            row, reason = [None]*len(NUMERIC), 'invalid_features'
        if reference_regime != REFERENCE or features.regime_identity != a['regime_identity']:
            reason = 'reference_regime_mismatch'
        if features.schedule_issues:
            reason = 'unsupported_programme_schedule'
        if not features.enrolled:
            reason = 'not_currently_enrolled'
        if features.horizon == 0:
            reason = 'terminal_cutoff_not_applicable'
        elif features.horizon not in a['supported_horizons']:
            reason = 'unsupported_horizon'
        for k,v,low,high in zip(NUMERIC,row,a['minimum'],a['maximum']):
            if v is not None and not low <= v <= high:
                ood.append('range:'+k)
        if features.support_type not in a['categories']:
            ood.append('unknown_category:support_type')
        if schedule_pattern(features) not in a['training_schedule_patterns']:
            ood.append('unseen_schedule_pattern')
            if reason is None:
                reason = 'unsupported_schedule_pattern'
        probability = None
        if reason is None:
            score = float(self._transform(features) @ np.asarray(a['coefficients']) + a['intercept'])
            if a['calibration']['method'] == 'sigmoid':
                score = a['calibration']['slope']*score + a['calibration']['intercept']
            probability = float(expit(score)) if math.isfinite(score) else None
            if probability is None or not math.isfinite(probability):
                probability, reason = None, 'nonfinite_prediction'
        return TrainedRiskPrediction(features.student_id, features.cutoff_week, features.horizon,
            features.estimate_id, probability, reason, self.version, digest(a['calibration']),
            features.fingerprint, tuple(k for k,v in zip(NUMERIC,row) if v is None), tuple(ood))


def fit_model(training, validation, *, hyperparameters=(.1, 1., 10.)):
    """Fit only train; split validation WORLDS into calibration and selection.

    Test records are rejected, including source groups shared across boundaries.
    Validation does not refit medians, ranges, categories, scaling or coefficients.
    """
    if not training or not validation or any(r.split != 'train' for r in training) or any(r.split != 'validation' for r in validation):
        raise ValueError('fit requires isolated training and validation records; test prohibited')
    if ({r.linkage_group for r in training} & {r.linkage_group for r in validation}
            or {r.world_seed for r in training} & {r.world_seed for r in validation}):
        raise ValueError('source group/world leakage')
    if len({r.features.regime_identity for r in (*training,*validation)}) != 1:
        raise ValueError('mixed reference laws')
    if any(r.features.schedule_issues or r.target != TARGET or r.reference_policy != REFERENCE
           or r.features.horizon < 1 for r in (*training,*validation)):
        raise ValueError('invalid reference label or unsupported schedule')
    raw = np.array([[np.nan if v is None else v for v in _numeric(r.features)] for r in training])
    # All-missing columns have the declared training-only zero imputation.
    medians = [float(np.median(raw[np.isfinite(raw[:,i]),i])) if np.isfinite(raw[:,i]).any() else 0.
               for i in range(len(NUMERIC))]
    filled = np.where(np.isnan(raw),medians,raw)
    categories = sorted({r.features.support_type for r in training})
    x = np.c_[filled, np.isnan(raw).astype(float), [[r.features.support_type == c for c in categories] for r in training]]
    scales = np.std(x,axis=0)
    scales[scales == 0] = 1
    y = np.array([r.withdrawal_event for r in training],dtype=int)
    if len(set(y)) != 2:
        raise ValueError('logistic fit requires both outcome classes in training')
    minimum = [float(np.min(raw[np.isfinite(raw[:,i]),i])) if np.isfinite(raw[:,i]).any() else 0. for i in range(len(NUMERIC))]
    maximum = [float(np.max(raw[np.isfinite(raw[:,i]),i])) if np.isfinite(raw[:,i]).any() else 0. for i in range(len(NUMERIC))]
    worlds = sorted({r.world_seed for r in validation})
    if len(worlds) < 4:
        raise ValueError('at least four validation worlds required for disjoint calibration/selection')
    calibration_worlds, selection_worlds = worlds[::2], worlds[1::2]
    cal = [r for r in validation if r.world_seed in calibration_worlds]
    selection = [r for r in validation if r.world_seed in selection_worlds]
    provenance = dict(training_worlds=sorted({r.world_seed for r in training}),
        validation_worlds=worlds, calibration_worlds=calibration_worlds, selection_worlds=selection_worlds,
        training_groups=sorted({r.linkage_group for r in training}),
        validation_groups=sorted({r.linkage_group for r in validation}),
        source_data_fingerprints=sorted({r.source_fingerprint for r in (*training,*validation)}),
        training_population_identities=sorted({r.population_identity for r in training}),
        validation_population_identities=sorted({r.population_identity for r in validation}),
        training_population_seeds=sorted({r.population_seed for r in training}),
        validation_population_seeds=sorted({r.population_seed for r in validation}),
        label_generator='exact_weekly_reference_branch/v1',
        label_record_fingerprints=dict(train=digest([asdict(r) for r in training]), validation=digest([asdict(r) for r in validation])))
    candidates, selection_report = [], []
    for strength in hyperparameters:
        estimator = LogisticRegression(C=strength,max_iter=2000,solver='lbfgs',random_state=0).fit(x/scales,y)
        base = dict(contract=MODEL_CONTRACT, target=TARGET, reference=REFERENCE,
            schema=FEATURE_SCHEMA, preprocessing='train_median_missing_indicator_scale_onehot/v1',
            medians=medians, scales=scales.tolist(), minimum=minimum, maximum=maximum, categories=categories,
            supported_horizons=sorted({r.features.horizon for r in training}),
            training_schedule_patterns=sorted({schedule_pattern(r.features) for r in training}),
            regime_identity=training[0].features.regime_identity,
            coefficients=estimator.coef_[0].tolist(), intercept=float(estimator.intercept_[0]),
            hyperparameters=dict(C=strength,penalty='l2',solver='lbfgs',max_iter=2000),
            calibration=dict(method='none',reason='uncalibrated_candidate'), provenance=provenance,
            dependencies={name:dependency_version(name)
                          for name in ('numpy','scipy','scikit-learn')})
        def make(record):
            return TrainedWithdrawalRiskModel({**record,'model_version':digest(record)})
        model = make(base)
        cal_scores = np.array([float(model._transform(r.features) @ estimator.coef_[0]+estimator.intercept_[0]) for r in cal])
        cal_y = np.array([r.withdrawal_event for r in cal],dtype=int)
        variants = [base]
        if min(sum(cal_y),len(cal_y)-sum(cal_y)) >= 10:
            platt = LogisticRegression(C=1.,random_state=0).fit(cal_scores[:,None],cal_y)
            variants.append({**base,'calibration':dict(method='sigmoid',slope=float(platt.coef_[0,0]),
                intercept=float(platt.intercept_[0]),fit_worlds=calibration_worlds)})
        for record in variants:
            model = make(record)
            # Select by world-mean Brier; landmarks are not independent replicates.
            losses = []
            for world in selection_worlds:
                rows = [r for r in selection if r.world_seed == world]
                probabilities = [model.predict(r.features, expected_estimate_id=r.features.estimate_id,
                    expected_model_version=model.version).probability for r in rows]
                # Coverage is fixed by training, never selected using outcomes.
                scored = [(p,int(r.withdrawal_event)) for p,r in zip(probabilities,rows) if p is not None]
                if not scored:
                    raise ValueError('no supported schedule predictions in a validation selection world')
                losses.append(np.mean([(p-y)**2 for p,y in scored]))
            loss = float(np.mean(losses))
            candidates.append((loss,strength,record['calibration']['method'],model))
            selection_report.append(dict(C=strength,calibration=record['calibration'],world_mean_brier=loss,
                selection_records=len(selection), supported_selection_records=sum(
                    schedule_pattern(r.features) in base['training_schedule_patterns'] for r in selection)))
    selected = min(candidates,key=lambda t:t[:3])[3]
    constants = {str(h):float(np.mean([r.withdrawal_event for r in training if r.features.horizon == h]))
                 for h in selected.artifact['supported_horizons']}
    return selected, dict(selection=selection_report, selected_model=selected.version,
        constant_by_horizon=constants, training_prevalence=float(np.mean(y)),
        calibration_status='selected_on_disjoint_validation_worlds',provenance=provenance)


def schedule_pattern(features):
    values = dict(features.numeric)
    return json.dumps([features.horizon,values.get('active_programme'),
        *[values.get(f'scheduled_session_week_{i}') for i in range(4)]],separators=(',',':'))


def load_versioned_model(artifact):
    """Explicit historical dispatch; the v2 loader itself always rejects v1."""
    if artifact.get('contract') == 'trained_withdrawal_model/v1':
        from .trained_withdrawal_risk_v1 import TrainedWithdrawalRiskModel as HistoricalModel
        return HistoricalModel(artifact)
    return TrainedWithdrawalRiskModel(artifact)


def model_features(model, student, **kwargs):
    if (model.artifact['contract'] == 'trained_withdrawal_model/v1'
            and kwargs['config'].sessions_required == 2 and kwargs['config'].session_cadence_weeks == 1):
        from .trained_withdrawal_risk_v1 import decision_features as historical_features
        return historical_features(student, **kwargs)
    return decision_features(student, **kwargs)

"""Categorical filtering with source-time replay for late observations.

Replay updates today's belief only: persisted historical decisions remain immutable.
One emission per source event is used, regardless of how many note sentences cite it.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import numpy as np

from ..intervention.feedback_notes import SIGNAL_PHRASES, MENTOR_SIGNAL_PHRASES
from ..intervention.observation_extractor import ExtractedObservationBatch
from .belief_state import EstimatedStudentState, validate_belief
from .observation_model import ObservationConfig, SIGNALS
from .transition_model import P_WAIT, programme_matrix, validate_matrix


@dataclass(frozen=True)
class EstimateUpdate:
    student_id: str
    month: int
    previous_belief: tuple
    predicted_belief: tuple
    accepted_observations: tuple
    rejected_observations: tuple
    updated_belief: tuple
    estimate_id: str
    uncertainty: tuple
    assimilated_condition_evidence_ids: tuple


class StudentStateEstimator:
    def __init__(self, *, observation_config=ObservationConfig(), wait_matrix=P_WAIT,
                 treatment_matrix=None, prior=(1/3, 1/3, 1/3, 0), action_contract='atomic_monthly'):
        if action_contract not in ('atomic_monthly', 'weekly_delivered_v1'):
            raise ValueError('unknown estimator action contract')
        self.action_contract = action_contract
        self.prior = validate_belief(prior)
        self.wait = validate_matrix(wait_matrix)
        self.programme = validate_matrix(programme_matrix() if treatment_matrix is None else treatment_matrix)
        self.observation_config = observation_config
        self.likelihoods = observation_config.likelihood_matrix
        self.updates = []

    @property
    def configuration(self):
        result = {"prior": self.prior, "wait_matrix": self.wait.tolist(),
                "programme_matrix": self.programme.tolist(),
                "observation_config": asdict(self.observation_config),
                "registry_model": "exact_administrative_enrollment",
                "correlation_rule": "one_signal_per_event_conflicts_quarantined"}
        # Preserve the exact legacy configuration identity and replay hashes.
        if self.action_contract != 'atomic_monthly':
            result['action_contract'] = self.action_contract
            from .delivery_observations import MENTOR_OBSERVATION_CONTRACT
            result['mentor_observation_contract'] = MENTOR_OBSERVATION_CONTRACT
        return result

    def initialize(self, student_id, initial_observations=(), *, registry=(), as_of_month=1, known_actions=()):
        return self._update(student_id, None, initial_observations, known_actions, as_of_month, registry)

    def update(self, previous_belief, validated_observations=(), known_actions=(), *,
               as_of_month, registry=()):
        if as_of_month < previous_belief.as_of_month:
            raise ValueError("cannot rewrite a historical estimate")
        return self._update(previous_belief.student_id, previous_belief, validated_observations,
                            known_actions, as_of_month, registry)

    def _update(self, sid, previous, batches, actions, cutoff, registry):
        if type(cutoff) is not int or cutoff < 1:
            raise ValueError("decision cutoff must be a positive month")
        actions = tuple(actions)
        if ((self.action_contract == 'atomic_monthly' and len(actions) > 1)
                or len(actions) != len(set(actions))
                or any(type(m) is not int or not 1 <= m < cutoff for m in actions)
                or (previous and not set(previous.known_actions) <= set(actions))):
            raise ValueError("known admission history must preserve the single past programme")
        history = {f.evidence_id: f for f in previous.observation_history} if previous else {}
        accepted, rejected = [], []
        for batch in batches:
            if (not isinstance(batch, ExtractedObservationBatch) or batch.student_id != sid
                    or batch.as_of_month > cutoff):
                raise ValueError("estimator requires validated as-of observations for this student")
            for fact in batch.facts:
                if fact.source_month >= cutoff:
                    raise ValueError("future evidence cannot update a belief")
                if fact.evidence_id in history:
                    rejected.append((fact.evidence_id, "duplicate_evidence"))
                else:
                    history[fact.evidence_id] = fact
                    accepted.append(fact.evidence_id)
        registry_by_month = {r.event_month: r for r in previous.enrollment_history} if previous else {}
        for record in registry:
            if (record.student_id != sid or record.available_from_month > cutoff
                    or record.event_month >= cutoff):
                raise ValueError("invalid administrative observation cutoff")
            if record.event_month in registry_by_month and registry_by_month[record.event_month] != record:
                raise ValueError("conflicting registry records")
            registry_by_month[record.event_month] = record
        by_time = defaultdict(lambda: defaultdict(list))
        for fact in history.values():
            by_time[fact.source_month][fact.event_id].append(fact)
        probabilities = np.asarray(self.prior)
        unresolved = []
        assimilated_months = set()
        assimilated_ids = set()
        reverse = {phrase: signal for signal, phrase in SIGNAL_PHRASES.items()}
        if self.action_contract == 'weekly_delivered_v1':
            reverse.update({phrase: signal for signal, phrase in MENTOR_SIGNAL_PHRASES.items()})
        for time in range(cutoff):
            if time:
                probabilities = probabilities @ (self.programme if time in actions else self.wait)
            if time in registry_by_month:
                enrolled = registry_by_month[time].enrolled
                mask = np.asarray([1, 1, 1, 0] if enrolled else [0, 0, 0, 1])
                probabilities = self._normalize(probabilities * mask, "impossible registry observation")
            for event_id, facts in sorted(by_time[time].items()):
                facts = sorted(facts, key=lambda f: f.evidence_id)
                signals = {self._signal_for_fact(f,reverse) for f in facts}
                signals.discard(None)
                conflict = any(f.assertion_status == "conflicting" for f in facts) or len(signals) > 1
                if conflict:
                    unresolved.extend(facts)
                    rejected.append((event_id, "conflicting_correlated_event"))
                    continue
                if not signals:
                    unresolved.extend(f for f in facts if f.field != "mentoring_support")
                    continue
                signal = next(iter(signals))
                weighted = probabilities * self.likelihoods[:, SIGNALS.index(signal)]
                if not np.isfinite(weighted).all() or weighted.sum() <= 0:
                    unresolved.extend(facts)
                    rejected.append((event_id, "zero_likelihood_preserved_prediction"))
                    continue
                probabilities = weighted / weighted.sum()
                assimilated_months.add(time)
                assimilated_ids.update(f.evidence_id for f in facts if self._signal_for_fact(f,reverse) is not None)
        posterior = validate_belief(probabilities)
        facts = tuple(sorted(history.values(), key=lambda f: (f.source_month, f.event_id, f.evidence_id)))
        last = max(assimilated_months, default=None)
        entropy = -sum(p * np.log(p) for p in posterior if p > 0)
        uncertainty = (("entropy_nats", float(entropy)), ("missing_current_signal", cutoff - 1 not in assimilated_months),
            ("unresolved_count", len(unresolved)), ("likelihoods_empirically_calibrated", False))
        identity = {"student_id": sid, "cutoff": cutoff, "belief": posterior,
                    "facts": [asdict(f) for f in facts], "actions": actions,
                    "registry": [asdict(r) for _, r in sorted(registry_by_month.items())],
                    "estimator": self.configuration}
        estimate_id = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        result = EstimatedStudentState(
            sid, cutoff, posterior, estimate_id,
            tuple(f.evidence_id for f in facts), tuple(unresolved),
            tuple(f for f in facts if f.field == "mentoring_support"), uncertainty, last,
            facts, tuple(r for _, r in sorted(registry_by_month.items())), actions)
        predicted = np.asarray(previous.condition_probabilities if previous else self.prior)
        if previous:
            for month in range(previous.as_of_month, cutoff):
                predicted = predicted @ (self.programme if month in actions else self.wait)
        self.updates.append(EstimateUpdate(sid, cutoff,
                            previous.condition_probabilities if previous else self.prior,
                            tuple(predicted), tuple(accepted), tuple(rejected), posterior,
                            estimate_id, uncertainty, tuple(sorted(assimilated_ids))))
        return result

    @staticmethod
    def _signal_for_fact(fact,reverse):
        return reverse.get(fact.evidence)

    @staticmethod
    def _normalize(values, reason):
        total = values.sum()
        if not np.isfinite(values).all() or total <= 0:
            raise ValueError(reason)
        return values / total

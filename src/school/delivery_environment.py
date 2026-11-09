"""Weekly delivery world. Offers never write hidden conditions or enrollment.

Decision -> validate/reserve all offers -> uptake -> current sessions -> actual
charges -> one weekly transition -> next-cutoff authorized emissions -> advance.
"""
from dataclasses import replace
from copy import deepcopy

import numpy as np

from .delivery_config import DeliveryConfig
from .delivery_contracts import (DeliveryAction, DeliveryEvent, OfferWindow, Programme,
    ScheduledSession, StudentProfile, WeeklyDecisionState, WeeklyEstimate, WeeklyRisk, WeeklyStudent)
from .delivery_fairness import freeze_offer_window, update_offer_window
from .delivery_forecasts import committed_support_risk
from .delivery_resources import audit_delivery_events, mentor_contracts, validate_offers
from .money import amount
from .observation_model import SyntheticObservationModel, ObservationConfig
from .student_condition import STATES, StudentCondition
from .transition_model import keyed_uniform, sample_condition, validate_matrix
from ..evaluation.provenance import digest


class WeeklyDeliveryEnvironment:
    def __init__(self, profiles, mentors, config, *, initial_conditions, observation_config=ObservationConfig()):
        if not isinstance(config, DeliveryConfig):
            raise ValueError('weekly environment requires DeliveryConfig')
        self.config = config
        self.profiles = tuple(deepcopy(profiles))
        mentors = tuple(mentors)
        if len(self.profiles) != config.num_students or len(mentors) != config.num_mentors:
            raise ValueError('weekly configuration counts must match explicit initial cohort and mentor inputs')
        if (len({s.student_id for s in self.profiles}) != len(self.profiles)
                or any(not isinstance(s, StudentProfile) or not s.student_id for s in self.profiles)):
            raise ValueError('weekly profiles require unique student identities')
        self.mentors = mentor_contracts(deepcopy(mentors), config)
        initial_conditions = tuple(initial_conditions)
        self._conditions = dict(initial_conditions)
        if len(self._conditions) != len(initial_conditions) or set(self._conditions) != {s.student_id for s in self.profiles}:
            raise ValueError('evaluator initial conditions must match the authorized cohort')
        self._conditions = {sid: StudentCondition(c) for sid, c in self._conditions.items()}
        self.initial_conditions = tuple(self._conditions.items())  # evaluator-only replay inputs
        self._wait = validate_matrix(config.weekly_wait_matrix)
        self._treatment = config.treatment_matrix
        self.week = 1
        self._events, self._programmes = [], {}
        self._observations, self._registry = [], []
        self._window = None
        self._windows = []
        self.observation_config = observation_config
        self._observation_model = SyntheticObservationModel(observation_config)
        self.exogenous_draws, self.evaluator_truth, self.records = [], [], []
        self._emit_observations(0)
        self.evaluator_truth.append((0, tuple(self._conditions.items())))

    @property
    def done(self):
        return self.week > self.config.horizon_weeks

    @property
    def events(self):
        return tuple(self._events)

    @property
    def programmes(self):
        return tuple(self._programmes.values())

    @property
    def ledger(self):
        return audit_delivery_events(self.config, self.mentors, self.events, profiles=self.profiles)

    @property
    def windows(self):
        return tuple(self._windows)

    def authorized_observations(self, cutoff):
        return (tuple(e for e in self._observations if e.available_from_month <= cutoff),
                tuple(r for r in self._registry if r.available_from_month <= cutoff),
                tuple(e for e in self.events if e.available_week <= cutoff))

    @property
    def emitted_signals(self):
        """Only declared observable emissions; pending dates remain attached."""
        return tuple(self._observations)

    @property
    def enrollment_history(self):
        return tuple(self._registry)

    @classmethod
    def from_students(cls, students, mentors, config):
        """Adapt existing source profiles without exposing generated reset truth."""
        from .cmdp_environment import initial_condition
        profiles, conditions = [], []
        for student in students:
            condition = initial_condition(student)
            if condition is None:
                continue
            profiles.append(StudentProfile(student.student_id, student.primary_support_type,
                student.need_score, student.disadvantage_proxy_group, student.sex_source))
            conditions.append((student.student_id, condition))
        return cls(tuple(profiles), mentors, config, initial_conditions=tuple(conditions))

    def _emit_observations(self, source_week):
        # Emission model indices are explicitly adapted from periods to weeks.
        # It supplies condition signals only; lifecycle events carry completion.
        events, registry = self._observation_model.generate(tuple(self._conditions.items()),
            month=source_week, seed=self.config.seed)
        self._observations.extend(events)
        self._registry.extend(registry)

    def observe(self, *, estimates=(), risks=()):
        """Public registry and event history only; no oracle/default truth path."""
        cutoff = self.week
        _, registry, events = self.authorized_observations(cutoff)
        enrolled = {r.student_id: r.enrolled for r in registry}
        estimates = {e.student_id: e for e in estimates}
        risks = {r.student_id: r for r in risks}
        students = []
        from .retention_value import wait_values
        for profile in self.profiles:
            sid = profile.student_id
            prior = (1/3, 1/3, 1/3, 0.) if enrolled[sid] else (0., 0., 0., 1.)
            estimate = estimates.get(sid) or WeeklyEstimate(sid, cutoff, prior,
                digest(['weekly_public_prior_v1', sid, cutoff, prior]), (), None, ())
            risk = risks.get(sid) or WeeklyRisk(sid, cutoff, max(0, self.config.horizon_weeks-cutoff+1),
                estimate.estimate_id, float(1 - np.asarray(estimate.condition_probabilities)
                    @ wait_values(self._wait, max(0, self.config.horizon_weeks-cutoff+1))))
            known = tuple(p for p in self.programmes if p.student_id == sid and p.offer_week < cutoff)
            prior_offers = tuple(p.programme_id for p in known)
            # One accepted programme per episode. Refusal may be offered again;
            # repeat offers in one four-week window still count only once.
            eligible = enrolled[sid] and not any(p.status != 'REFUSED' for p in known)
            students.append(WeeklyStudent(profile, enrolled[sid], estimate, risk, eligible,
                cutoff - 1 if eligible else 0, prior_offers, known,
                committed_support_risk(self.config, estimate, known)))
        placeholder = self._window or OfferWindow(1, min(4, self.config.horizon_weeks), ())
        state = WeeklyDecisionState(cutoff, max(0, self.config.horizon_weeks-cutoff+1),
            tuple(students), self.mentors, self.ledger, placeholder, tuple(e.event_id for e in events))
        if not self.done and (self._window is None or cutoff > self._window.end_week):
            self._window = freeze_offer_window(state, self.config)
            self._windows.append(self._window)
        if self._window:
            self._window = update_offer_window(self._window, events)
            self._windows[-1] = self._window
            state = replace(state, fairness_window=self._window)
        state.validate_estimates()
        return state

    def _event(self, kind, p, session=None, *, money='0', reason='', stream=None):
        event = DeliveryEvent(f'{p.programme_id}:event:{len(self._events)}', kind,
            self.week, self.week + 1, p.student_id, p.mentor_id, p.programme_id,
            session.session_id if session else None, session.week if session else None,
            str(money), reason, stream)
        self._events.append(event)

    def _outcome(self, p, kind, probability, overrides, session=None):
        # Programme identity includes student and offer week, not the mentor or
        # global admission index. The same offered intervention across policies
        # shares a draw; different counterfactual starts have different keys.
        stream = f'weekly_delivery/v1:{kind}:{p.programme_id}:{session.session_id if session else "programme"}'
        draw = keyed_uniform(self.config.seed, p.student_id, self.week, stream)
        full_key = (p.student_id, kind, self.week, p.programme_id, session.session_id if session else None)
        fixture_key = (p.student_id, kind, self.week)
        result = overrides.get(full_key, overrides.get(fixture_key, draw < probability))
        if type(result) is not bool:
            raise ValueError('exogenous delivery outcomes must be boolean')
        self.exogenous_draws.append(dict(key=full_key, stream=stream, uniform=draw,
                                        probability=probability, outcome=result))
        return result, stream

    def _cancel(self, p, reason):
        self._event('programme_cancelled', p, reason=reason)
        sessions = []
        for session in p.sessions:
            if session.status == 'RESERVED':
                self._event('reservation_released', p, session,
                    money=amount(self.config.cost_per_session), reason=reason)
                session = replace(session, status='RELEASED')
            sessions.append(session)
        p = replace(p, status='CANCELLED', sessions=tuple(sessions))
        self._event('programme_outcome_observed', p, reason='cancelled; educational outcome unknown')
        self._programmes[p.programme_id] = p

    def step(self, action, *, outcomes=None):
        if self.done:
            raise ValueError('weekly episode has completed')
        outcomes = {} if outcomes is None else dict(outcomes)
        if any(type(value) is not bool for value in outcomes.values()):
            raise ValueError('exogenous delivery outcomes must be boolean')
        # Recompute hard constraints from public records and the event ledger.
        # Private truth never selects feasibility for an ordinary action.
        validate_offers(self.observe(), action, self.config)
        start_event = len(self._events)
        for pid in action.cancel_programme_ids:
            self._cancel(self._programmes[pid], 'controller_cancellation')
        pending = []
        # Temporarily commit ALL offers before resolving any uptake, including
        # refusals; no policy can speculate on an unknown refusal freeing money.
        for offer in action.offers:
            pid = f'{self.config.seed}:{offer.student_id}:weekly-programme:{self.week}'
            p = Programme(pid, offer.student_id, offer.mentor_id, self.week,
                ((self.week-1)//4)*4+1, 'OFFERED', tuple(ScheduledSession(
                    f'{pid}:session:{n+1}', week) for n, week in enumerate(self.config.schedule(self.week))))
            self._event('support_offered', p)
            for session in p.sessions:
                self._event('session_reserved', p, session, money=amount(self.config.cost_per_session))
            self._event('administration_charged', p, money=amount(self.config.administrative_offer_cost))
            pending.append(p)
        for p in pending:
            accepted, stream = self._outcome(p, 'acceptance', self.config.acceptance_probability, outcomes)
            self._event('offer_accepted' if accepted else 'offer_refused', p, stream=stream)
            if accepted:
                for session in p.sessions:
                    self._event('session_scheduled', p, session)
                p = replace(p, status='SCHEDULED')
            else:
                for session in p.sessions:
                    self._event('reservation_released', p, session, money=amount(self.config.cost_per_session), reason='refused')
                p = replace(p, status='REFUSED', sessions=tuple(replace(s, status='RELEASED') for s in p.sessions))
            self._programmes[p.programme_id] = p
        effective = set()
        for p in tuple(self.programmes):
            if p.status not in ('SCHEDULED', 'ACTIVE'):
                continue
            if p.offer_week < self.week:
                cancelled, stream = self._outcome(p, 'cancellation', self.config.cancellation_probability, outcomes)
                if cancelled:
                    self._cancel(p, 'synthetic_cancellation:' + stream)
                    continue
            if p.status == 'SCHEDULED':
                self._event('programme_active', p)
                p = replace(p, status='ACTIVE')
            sessions = []
            for session in p.sessions:
                if session.week == self.week and session.status == 'RESERVED':
                    attends, stream = self._outcome(p, 'attendance', self.config.attendance_probability, outcomes, session)
                    succeeds, delivery_stream = self._outcome(p, 'delivery', self.config.delivery_probability, outcomes, session)
                    delivered = attends and succeeds
                    self._event('session_delivered' if delivered else 'session_missed', p, session,
                        money=amount(self.config.cost_per_session if delivered else self.config.missed_session_cost),
                        reason='delivered' if delivered else 'absent' if not attends else 'delivery_failure',
                        stream=stream + '|' + delivery_stream)
                    session = replace(session, status='DELIVERED' if delivered else 'MISSED')
                    if delivered:
                        effective.add(p.student_id)
                sessions.append(session)
            p = replace(p, sessions=tuple(sessions))
            if self.week == p.sessions[-1].week:
                completed = p.delivered_sessions == self.config.sessions_required
                p = replace(p, status='COMPLETED' if completed else 'INCOMPLETE')
                self._event('programme_completed' if completed else 'programme_incomplete', p)
                self._event('programme_outcome_observed', p,
                    reason='delivery completed; educational response observed only through authorized signals'
                    if completed else 'partial delivery; educational response unknown')
            self._programmes[p.programme_id] = p
        for sid, condition in self._conditions.items():
            uniform = keyed_uniform(self.config.seed, sid, self.week, 'weekly_environment_transition/v1')
            self.exogenous_draws.append(dict(key=(sid, 'transition', self.week),
                stream='weekly_environment_transition/v1', uniform=uniform))
            self._conditions[sid] = sample_condition(condition,
                self._treatment if sid in effective else self._wait, uniform)
        # Transition-time withdrawal ends service AFTER this week's activity.
        # Both registry and cancellation become authorized at the next cutoff.
        if self.config.terminate_on_withdrawal:
            for p in tuple(self.programmes):
                if p.status in ('SCHEDULED', 'ACTIVE') and self._conditions[p.student_id] == StudentCondition.WITHDRAWN:
                    self._cancel(p, 'authorized_withdrawal_registry')
        self._emit_observations(self.week)
        self.evaluator_truth.append((self.week, tuple(self._conditions.items())))
        ledger = self.ledger
        self.records.append(dict(week=self.week, action=action, ledger=ledger,
                                 event_ids=tuple(e.event_id for e in self._events[start_event:])))
        self.week += 1
        return self.records[-1]

    def terminal_reward(self):
        if not self.done:
            raise ValueError('terminal retention requires a completed episode')
        return sum(c != StudentCondition.WITHDRAWN for c in self._conditions.values())

"""Weekly adapter of the validated Phase 1–3 note/filter information boundary.

Only the adapter uses historical *_month schema field names as period indices;
all world clocks, persisted snapshots and reported dates are explicitly weekly.
"""
from ..intervention.feedback_notes import NoteQuality, render_note
from ..intervention.observation_extractor import FixtureObservationExtractor, RecordedOutcomeExtractor, validate_batch
from .delivery_contracts import WeeklyEstimate, WeeklyNote, WeeklyRisk
from .delivery_resources import validate_offers
from .simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from .state_estimator import StudentStateEstimator


LIFECYCLE_TEXT = {
    'support_offered': 'A tutoring programme was offered.',
    'offer_accepted': 'The tutoring offer was accepted. Sessions remain scheduled.',
    'offer_refused': 'The tutoring offer was refused. No session was delivered.',
    'session_delivered': 'A scheduled tutoring session was delivered.',
    'session_missed': 'A scheduled tutoring session was missed. It was not rescheduled.',
    'programme_completed': 'The student completed the scheduled mentoring appointments.',
    'programme_incomplete': 'The programme ended with incomplete session delivery.',
    'programme_cancelled': 'The tutoring programme was cancelled. Undelivered sessions were released.',
    'programme_outcome_observed': 'Programme delivery status was recorded. Educational success is unknown.',
}


class WeeklyFeedbackController:
    def __init__(self, environment, policy, *, extractor=None, note_quality=NoteQuality(),
                 recorded_notes=None):
        self.environment, self.policy = environment, policy
        self.extractor = extractor if extractor is not None else FixtureObservationExtractor()
        self.note_quality = note_quality
        self.recorded_notes = recorded_notes
        self.estimator = StudentStateEstimator(wait_matrix=environment.config.weekly_wait_matrix,
            treatment_matrix=environment.config.treatment_matrix, action_contract='weekly_delivered_v1',
            observation_config=environment.observation_config)
        self.risk_model = SimulatedWithdrawalRiskEstimator(environment.config.weekly_wait_matrix)
        self.estimates = {}
        self.notes, self.batches, self.attempts, self.snapshots, self.decisions = [], [], [], [], []
        self.processed = set()
        self._generated = set()
        self._cutoff_diagnostics = {}
        self._new_evidence_by_cutoff = {}
        self._generate_notes()

    def _generate_notes(self):
        env = self.environment
        notes = []
        # The renderer receives only authorized emissions, never private truth.
        for event in env.emitted_signals:
            if event.event_id in self._generated:
                continue
            rendered = render_note(event, seed=env.config.seed, quality=self.note_quality)
            notes.append(WeeklyNote(rendered.note_id, rendered.student_id, event.event_month,
                rendered.available_from_month, rendered.text, rendered.source_event_ids))
            self._generated.add(event.event_id)
        for event in env.events:
            if event.event_id in self._generated or event.kind not in LIFECYCLE_TEXT:
                continue
            notes.append(WeeklyNote(event.event_id + ':note', event.student_id,
                event.source_week, event.available_week, LIFECYCLE_TEXT[event.kind],
                (event.event_id,), event.mentor_id, event.programme_id))
            self._generated.add(event.event_id)
        for note in notes:
            if self.recorded_notes is not None:
                expected = self.recorded_notes.get(note.note_id)
                if expected is None:
                    raise ValueError('missing recorded weekly note')
                # Recorded prose may be generated externally; regenerate timing
                # and identities and verify them before accepting that prose.
                if (expected.student_id != note.student_id or expected.source_week != note.source_week
                        or expected.source_event_ids != note.source_event_ids):
                    raise ValueError('recorded weekly note provenance mismatch')
                note = expected
            self.notes.append(note)

    def prepare_decision_snapshot(self):
        env, cutoff = self.environment, self.environment.week
        _, registry, lifecycle = env.authorized_observations(cutoff)
        incoming = {p.student_id: [] for p in env.profiles}
        previously_usable = {sid for sid,e in self.estimates.items() if e.last_observation_month is not None}
        new_evidence = {}
        for note in self.notes:
            if note.note_id in self.processed or note.available_week > cutoff or note.source_week >= cutoff:
                continue
            self.processed.add(note.note_id)
            attempt = dict(note_id=note.note_id, student_id=note.student_id,
                as_of_month=cutoff, source_week=note.source_week, available_week=note.available_week,
                source_event_ids=note.source_event_ids, time_unit='week', evidence_ids=(),
                note_type='programme' if note.programme_id else 'monitoring')
            calls_before = getattr(self.extractor, 'calls', 0)
            audits_before = len(getattr(self.extractor, 'audit_records', ()))
            try:
                batch = validate_batch(self.extractor.extract(note, cutoff), note, cutoff)
                self.batches.append(batch)
                incoming[note.student_id].append(batch)
                attempt.update(status='accepted', evidence_ids=tuple(f.evidence_id for f in batch.facts),
                    result='empty' if not batch.facts else 'conflicting' if any(
                        f.assertion_status == 'conflicting' for f in batch.facts) else
                    'unknown' if all(f.value == 'unknown' for f in batch.facts) else 'supported')
            except Exception as exc:
                attempt.update(status='quarantined', reason=str(exc),
                    error_type=getattr(exc, 'original_error_type', type(exc).__name__))
            attempt.update(model_invocations=getattr(self.extractor,'calls',0)-calls_before, cache_hit=False)
            audits = getattr(self.extractor,'audit_records',())
            if len(audits) > audits_before:
                attempt.update(extractor_audit=audits[-1], cache_hit=bool(audits[-1].get('cache_hit')))
            if isinstance(self.extractor,RecordedOutcomeExtractor):
                attempt = self.extractor.restore_provenance(attempt)
            self.attempts.append(attempt)
        wrapped, risks = [], []
        for profile in env.profiles:
            sid = profile.student_id
            # This is observed completed activity, NOT offer/acceptance history.
            actions = tuple(sorted({e.source_week for e in lifecycle
                                    if e.student_id == sid and e.kind == 'session_delivered'}))
            records = tuple(r for r in registry if r.student_id == sid)
            previous = self.estimates.get(sid)
            estimate = (self.estimator.update(previous, incoming[sid], actions,
                as_of_month=cutoff, registry=records) if previous else
                self.estimator.initialize(sid, incoming[sid], registry=records, as_of_month=cutoff,
                    known_actions=actions))
            self.estimates[sid] = estimate
            update = self.estimator.updates[-1]
            new = self._new_evidence_by_cutoff.setdefault((cutoff,sid),set())
            new.update(set(update.accepted_observations) & set(update.assimilated_condition_evidence_ids))
            new.intersection_update(update.assimilated_condition_evidence_ids)
            new_evidence[sid] = set(new)
            # Audit only current condition-note attempts. Lifecycle prose and
            # repeated citations cannot manufacture a fresh condition reading.
            current = [a for a in self.attempts if a['student_id'] == sid
                       and a['as_of_month'] == cutoff and a['note_type'] == 'monitoring']
            conflict_events = {event for event,reason in update.rejected_observations
                               if reason == 'conflicting_correlated_event'}
            conflict = any(f.event_id in conflict_events and
                f.source_month >= (estimate.last_observation_month if estimate.last_observation_month is not None else 0)
                for f in estimate.observation_history)
            quality = (*estimate.observation_uncertainty,
                ('new_condition_evidence_ids', tuple(sorted(new_evidence[sid]))),
                ('condition_conflict', conflict),
                ('rejected_condition_observation', any(a['status'] == 'quarantined' for a in current)))
            risk = self.risk_model.predict(estimate, max(0, env.config.horizon_weeks-cutoff+1))
            wrapped.append(WeeklyEstimate(sid, cutoff, estimate.condition_probabilities,
                estimate.estimate_id, estimate.evidence_ids, estimate.last_observation_month,
                quality))
            risks.append(WeeklyRisk(sid, cutoff, risk.months_remaining, risk.input_estimate_id, risk.probability))
        state = env.observe(estimates=tuple(wrapped), risks=tuple(risks))
        eligible = {s.student_id for s in state.students if s.eligible}
        attempts = [a for a in self.attempts if a['as_of_month'] == cutoff]
        self._cutoff_diagnostics.setdefault(cutoff,dict(cutoff_week=cutoff,
            has_allocation_decision=not env.done, eligible_students=len(eligible),
            previously_usable_eligible_ids=tuple(sorted(eligible & previously_usable)),
            usable_eligible_ids=tuple(sorted(sid for sid in eligible if self.estimates[sid].last_observation_month is not None)),
            newly_usable_eligible_ids=tuple(sorted(sid for sid in eligible if new_evidence[sid])),
            actionable_extraction_attempts=sum(a['student_id'] in eligible for a in attempts),
            monitoring_attempts=sum(a['note_type']=='monitoring' for a in attempts),
            programme_attempts=sum(a['note_type']=='programme' for a in attempts),
            quarantined=sum(a['status']=='quarantined' for a in attempts),
            empty_extractions=sum(a.get('result')=='empty' for a in attempts),
            model_invocations=sum(a['model_invocations'] for a in attempts)))
        return state

    @property
    def extraction_diagnostics(self):
        return tuple(self._cutoff_diagnostics[w] for w in sorted(self._cutoff_diagnostics))

    def run_week(self, *, outcomes=None):
        state = self.prepare_decision_snapshot()
        action = self.policy.plan(state)
        validate_offers(state, action, self.environment.config)
        self.snapshots.append(state)
        self.decisions.append(action)
        record = self.environment.step(action, outcomes=outcomes)
        self._generate_notes()
        return record

    def run_episode(self, *, outcome_provider=None):
        while not self.environment.done:
            outcomes = outcome_provider(self.environment.week) if outcome_provider else None
            self.run_week(outcomes=outcomes)
        # Include final outcome observations and the terminal belief at H+1;
        # there is no terminal allocation or retroactive edit of decisions.
        self.final_snapshot = self.prepare_decision_snapshot()
        return self

    def validate(self):
        env = self.environment
        if not env.done or len(self.decisions) != env.config.horizon_weeks:
            raise ValueError('cannot publish incomplete weekly episode')
        for state, action in zip(self.snapshots, self.decisions):
            validate_offers(state, action, env.config)
        # Independently rebuild the full ledger, then every decision-prefix
        # resource state (week t decisions see only week <t events).
        from .delivery_resources import audit_delivery_events
        ledger = audit_delivery_events(env.config, env.mentors, env.events, profiles=env.profiles)
        for state in self.snapshots:
            expected = audit_delivery_events(env.config, env.mentors,
                tuple(e for e in env.events if e.source_week < state.week), profiles=env.profiles)
            if expected != state.ledger:
                raise ValueError('decision snapshot resource ledger mismatch')
            if any(e.available_week > state.week for e in env.events if e.event_id in state.authorized_event_ids):
                raise ValueError('future event leaked into decision snapshot')
        return ledger

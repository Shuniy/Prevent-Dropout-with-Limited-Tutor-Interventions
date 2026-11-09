"""Phase 4.2 real session feedback and read-order regression tests."""
import pickle
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from test_delivery_lifecycle import world
from src.school.delivery_contracts import DeliveryAction, SupportOffer
from src.school.delivery_controller import WeeklyFeedbackController
from src.school.delivery_policy import WeeklyDeliveryPolicy
from src.school.delivery_feedback_acceptance import mentor_boundary_episode
from src.school.delivery_experiments import normalized, episode_payload, scorecard, synthetic_environment
from src.school.delivery_config import DeliveryConfig, WEEKLY_WAIT_V1, WEEKLY_TUTORING_V1
from src.school.delivery_observations import MentorSessionObservationModel, validate_note_source
from src.school.observation_model import ObservationConfig
from src.school.delivery_uncertainty import weekly_uncertainty_sets
from src.school.delivery_resources import audit_delivery_events, validate_offers
from src.school.delivery_fairness import freeze_offer_window
from src.school.student_condition import StudentCondition
from src.intervention.feedback_notes import MENTOR_SIGNAL_PHRASES
from src.intervention.observation_extractor import FixtureObservationExtractor
from src.school.delivery_acceptance import LOW, REGULAR, VAGUE


COMPLETE = ObservationConfig(missing_probability=0, delay_probability=0)


def delivered_controller(*, observation_config=COMPLETE, **config):
    env = world(observation_config=observation_config, **config)
    c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'wait'))
    c.prepare_decision_snapshot()
    env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
    c._generate_notes()
    return c


def focal_note(c):
    return next(n for n in c.notes if n.observation_contract and n.student_id == 's0' and n.source_week == 1)


def isolate_mentor(c):
    c.notes = [replace(n, text=VAGUE) if n.source_week == 1 and not n.programme_id else n for n in c.notes]
    return focal_note(c)


class IntegrationDefectReproductions(unittest.TestCase):
    def test_actual_session_emits_programme_linked_condition_observation(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'wait'))
        signals = env.emitted_mentor_signals
        self.assertEqual(len(signals), 1)
        signal = signals[0]
        delivery = next(e for e in env.events if e.kind == 'session_delivered')
        self.assertEqual(signal.delivery_event_id, delivery.event_id)
        self.assertEqual(signal.session_id, delivery.session_id)
        note = next(n for n in c.notes if n.source_event_ids == (signal.event_id,))
        self.assertEqual(note.programme_id, delivery.programme_id)
        c.prepare_decision_snapshot()
        self.assertTrue(next(b for b in c.batches if b.note_id == note.note_id).facts)

    def test_observe_does_not_mutate_any_environment_state(self):
        env = world()
        before = pickle.dumps(env.__dict__)
        env.observe()
        env.observe()
        self.assertEqual(env.windows, ())
        self.assertEqual(before, pickle.dumps(env.__dict__))

    def test_extra_reads_do_not_change_controller_fairness_initialization(self):
        a, b = world(), world()
        b.observe()
        b.observe()
        ca = WeeklyFeedbackController(a, WeeklyDeliveryPolicy(a.config, 'wait'))
        cb = WeeklyFeedbackController(b, WeeklyDeliveryPolicy(b.config, 'wait'))
        sa, sb = ca.prepare_decision_snapshot(), cb.prepare_decision_snapshot()
        self.assertEqual(sa, sb)
        self.assertEqual(a.windows, b.windows)


class SchoolNoteProvenanceTests(unittest.TestCase):
    def controller(self, observation_config=COMPLETE):
        env = world(observation_config=observation_config)
        return WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'wait'))

    def test_registered_school_note_is_accepted(self):
        c = self.controller()
        note = c.notes[0]
        c.notes = [note]
        state = c.prepare_decision_snapshot()
        self.assertEqual(c.attempts[0]['status'], 'accepted')
        self.assertTrue(c.batches[0].facts)
        self.assertEqual(state.students[0].estimate.last_observation_week, 0)
        self.assertTrue(set(f.evidence_id for f in c.batches[0].facts)
                        <= set(state.students[0].estimate.evidence_ids))

    def test_unknown_school_source_is_quarantined_without_changing_posterior(self):
        baseline, c = self.controller(), self.controller()
        baseline.notes = []
        c.notes = [replace(c.notes[0], source_event_ids=('unregistered-school-event',))]
        expected, actual = baseline.prepare_decision_snapshot(), c.prepare_decision_snapshot()
        self.assertEqual(c.attempts[0]['status'], 'quarantined')
        self.assertFalse(c.batches)
        for a, b in zip(expected.students, actual.students):
            self.assertEqual(a.estimate.condition_probabilities, b.estimate.condition_probabilities)
            self.assertEqual(a.estimate.estimate_id, b.estimate.estimate_id)
            self.assertEqual(a.estimate.evidence_ids, b.estimate.evidence_ids)

    def test_wrong_school_student_or_source_week_is_quarantined(self):
        for changes in ({'student_id': 's1'}, {'source_week': 0}):
            with self.subTest(changes=changes):
                c = self.controller()
                c.run_week()
                note = next(n for n in c.notes if n.student_id == 's0' and n.source_week == 1)
                c.notes = [replace(note, **changes)]
                c.prepare_decision_snapshot()
                self.assertEqual(c.attempts[-1]['status'], 'quarantined')
                self.assertFalse(any(b.note_id == note.note_id for b in c.batches))

    def test_premature_school_availability_is_quarantined(self):
        for cutoff in (1, 3):
            with self.subTest(cutoff=cutoff):
                c = self.controller(replace(COMPLETE, delay_probability=1, delay_months=2))
                note = replace(c.notes[0], available_week=1)
                while c.environment.week < cutoff:
                    c.run_week()
                c.notes = [note]
                state = c.prepare_decision_snapshot()
                self.assertEqual(c.attempts[-1]['status'], 'quarantined')
                self.assertIsNone(state.students[0].estimate.last_observation_week)

    def test_school_note_itself_must_be_available_at_cutoff(self):
        c = self.controller()
        with self.assertRaisesRegex(ValueError, 'school.*provenance'):
            validate_note_source(replace(c.notes[0], available_week=2), c.environment, 1)

    def test_delayed_registered_school_note_is_accepted_at_correct_cutoff(self):
        for observation_delay in (False, True):
            with self.subTest(observation_delay=observation_delay):
                obs = replace(COMPLETE, delay_probability=int(observation_delay), delay_months=2)
                c = self.controller(obs)
                note = replace(c.notes[0], available_week=3)
                c.notes = [note]
                c.run_week()
                first = c.snapshots[0]
                c.notes = [note]
                c.run_week()
                self.assertNotIn(note.note_id, c.processed)
                c.notes = [note]
                state = c.prepare_decision_snapshot()
                self.assertEqual(c.attempts[-1]['status'], 'accepted')
                self.assertEqual(state.students[0].estimate.last_observation_week, 0)
                self.assertEqual(c.snapshots[0], first)
                self.assertTrue(c.batches[-1].facts)

    def test_school_notes_cannot_claim_mentor_or_programme_contract_fields(self):
        for changes in ({'mentor_id': 'm0', 'programme_id': 'fake'},
                        {'mentor_id': '', 'programme_id': ''},
                        {'delivery_event_id': 'fake'}, {'delivery_event_id': ''},
                        {'observation_contract': 'fake'}, {'observation_contract': ''},
                        {'mentor_id': 'm0', 'programme_id': 'fake', 'session_id': 'fake',
                         'delivery_event_id': 'fake', 'observation_contract': 'fake'}):
            with self.subTest(changes=changes):
                c = self.controller()
                c.notes = [replace(c.notes[0], **changes)]
                c.prepare_decision_snapshot()
                self.assertEqual(c.attempts[0]['status'], 'quarantined')
                self.assertFalse(c.batches)

    def test_school_note_cannot_reference_other_event_types(self):
        for source_kind in ('mentor', 'delivery'):
            with self.subTest(source_kind=source_kind):
                c = delivered_controller()
                school = next(n for n in c.notes if n.source_week == 1 and not n.programme_id)
                source = (c.environment.emitted_mentor_signals[0].event_id if source_kind == 'mentor'
                          else next(e.event_id for e in c.environment.events if e.kind == 'session_delivered'))
                c.notes = [replace(school, source_event_ids=(source,))]
                c.prepare_decision_snapshot()
                self.assertEqual(c.attempts[-1]['status'], 'quarantined')

    def test_registered_school_provenance_allows_controlled_text_changes(self):
        states = []
        for text in (LOW, REGULAR):
            c = self.controller()
            c.notes = [replace(c.notes[0], text=text)]
            states.append(c.prepare_decision_snapshot())
            self.assertEqual(c.attempts[0]['status'], 'accepted')
        self.assertNotEqual(states[0].students[0].estimate.condition_probabilities,
                            states[1].students[0].estimate.condition_probabilities)


class MentorFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regular = mentor_boundary_episode()
        cls.low = mentor_boundary_episode('low_participation')
        cls.unsupported = mentor_boundary_episode(unsupported_text=VAGUE)

    def test_actual_session_to_reallocation_and_realized_outcome(self):
        a, b = self.regular, self.low
        self.assertEqual(a.environment.initial_conditions, b.environment.initial_conditions)
        self.assertEqual(a.environment.mentors, b.environment.mentors)
        self.assertEqual(a.snapshots[0], b.snapshots[0])
        self.assertEqual(a.decisions[0], b.decisions[0])
        self.assertEqual(a.environment.evaluator_truth[:2], b.environment.evaluator_truth[:2])
        self.assertEqual([d for d in a.environment.exogenous_draws if d['key'][1] == 'transition'],
                         [d for d in b.environment.exogenous_draws if d['key'][1] == 'transition'])
        self.assertEqual(a.snapshots[1].ledger, b.snapshots[1].ledger)
        for c in (a, b):
            note = next(n for n in c.notes if n.observation_contract and n.source_week == 1)
            delivery = next(e for e in c.environment.events if e.event_id == note.delivery_event_id)
            self.assertEqual(delivery.kind, 'session_delivered')
            self.assertEqual((note.student_id, note.mentor_id, note.programme_id, note.session_id),
                (delivery.student_id, delivery.mentor_id, delivery.programme_id, delivery.session_id))
            self.assertEqual(note.available_week, 2)
            self.assertIn('+00:00', note.creation_time)
            batch = next(b for b in c.batches if b.note_id == note.note_id)
            state = c.snapshots[1].students[0]
            self.assertIn(batch.facts[0].evidence_id, state.estimate.evidence_ids)
            self.assertIn(batch.facts[0].evidence_id, c.decisions[1].uncertainty_sets[0].newly_assimilated_evidence_ids)
            self.assertEqual(state.estimate.last_observation_week, 1)
            for snapshot, action in zip(c.snapshots, c.decisions):
                validate_offers(snapshot, action, c.environment.config)
            self.assertEqual(c.validate(), audit_delivery_events(c.environment.config,
                c.environment.mentors, c.environment.events, profiles=c.environment.profiles))
        changed = [(x, y) for x, y in zip(
            [n for n in a.notes if n.source_week <= 1], [n for n in b.notes if n.source_week <= 1]) if x != y]
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0][0].session_id)
        sa, sb = a.snapshots[1].students[0], b.snapshots[1].students[0]
        self.assertNotEqual(sa.estimate.condition_probabilities, sb.estimate.condition_probabilities)
        self.assertNotEqual(sa.risk.probability, sb.risk.probability)
        self.assertNotEqual(sa.committed_risk.probability, sb.committed_risk.probability)
        self.assertNotEqual(b.decisions[1].uncertainty_sets[0].estimate_id,
                            a.decisions[1].uncertainty_sets[0].estimate_id)
        self.assertEqual((a.decisions[1].continuation_reviews[0].decision,
                          b.decisions[1].continuation_reviews[0].decision), ('cancel', 'continue'))
        self.assertFalse(a.decisions[1].offers)
        self.assertTrue(a.decisions[2].offers)
        self.assertEqual(a.environment.programmes[1].delivered_sessions, 5)
        self.assertEqual(a.environment.terminal_reward(), 3)

    def test_matching_likelihood_used_after_real_treatment_transition(self):
        for c, index in ((self.regular, 0), (self.low, 2)):
            predicted = np.asarray(c.snapshots[0].students[0].estimate.condition_probabilities) @ c.environment.config.treatment_matrix
            expected = predicted * np.array([1, 1, 1, 0]) * c.estimator.likelihoods[:, index]
            np.testing.assert_allclose(c.snapshots[1].students[0].estimate.condition_probabilities,
                expected/expected.sum(), atol=1e-14)

    def test_distinct_school_and_mentor_measurements_use_declared_product_likelihood(self):
        c = delivered_controller(weekly_wait_matrix=WEEKLY_WAIT_V1, weekly_tutoring_matrix=WEEKLY_TUTORING_V1)
        # Reconstruct the source-0 prior through the same authorized initial note.
        earlier = WeeklyFeedbackController(c.environment, WeeklyDeliveryPolicy(c.environment.config, 'wait'))
        initial_batches = [FixtureObservationExtractor().extract(n, 1) for n in earlier.notes
                          if n.student_id == 's0' and n.source_week == 0 and n.available_week == 1]
        prior = c.estimator.initialize('s0', initial_batches, as_of_month=1,
            registry=[r for r in c.environment.enrollment_history if r.student_id == 's0' and r.event_month == 0])
        state = c.prepare_decision_snapshot()
        school = next(e for e in c.environment.emitted_signals if e.student_id == 's0' and e.event_month == 1)
        mentor = c.environment.emitted_mentor_signals[0]
        self.assertNotEqual(school.event_id, mentor.event_id)
        from src.observations.observable_events import SIGNALS
        expected = np.asarray(prior.condition_probabilities) @ c.environment.config.treatment_matrix
        expected *= np.array([1, 1, 1, 0])
        expected *= COMPLETE.likelihood_matrix[:, SIGNALS.index(school.signal)]
        expected *= COMPLETE.likelihood_matrix[:, SIGNALS.index(mentor.signal)]
        np.testing.assert_allclose(state.students[0].estimate.condition_probabilities, expected/expected.sum(), atol=1e-14)

    def test_unsupported_mentor_prose_does_not_change_condition_or_actions(self):
        a = self.unsupported
        b = mentor_boundary_episode(unsupported_text=VAGUE+' The mentor will follow up.')
        self.assertEqual(a.snapshots, b.snapshots)
        self.assertEqual(a.decisions, b.decisions)
        self.assertEqual(a.environment.evaluator_truth, b.environment.evaluator_truth)
        self.assertFalse(a.decisions[1].continuation_reviews[0].fresh_evidence)
        self.assertEqual(a.decisions[1].continuation_reviews[0].decision, 'continue')
        self.assertGreater(a.decisions[1].uncertainty_sets[0].radius,
                           self.regular.decisions[1].uncertainty_sets[0].radius)

    def test_duplicate_mentor_note_has_no_additional_likelihood_or_freshness(self):
        c = delivered_controller()
        note = isolate_mentor(c)
        before = c.prepare_decision_snapshot()
        c.notes.append(replace(note, note_id=note.note_id+':duplicate'))
        after = c.prepare_decision_snapshot()
        self.assertEqual(before, after)
        self.assertTrue(any(reason == 'duplicate_evidence' for _, reason in c.estimator.updates[-3].rejected_observations))
        c.environment.step(DeliveryAction())
        c._generate_notes()
        c.notes = [replace(note, note_id=note.note_id+':late-copy', available_week=3)]
        later = c.prepare_decision_snapshot()
        self.assertEqual(later.students[0].estimate.last_observation_week, 1)
        self.assertFalse(weekly_uncertainty_sets(later)[0].newly_assimilated_evidence_ids)

    def test_conflicting_mentor_measurement_does_not_refresh_condition_evidence(self):
        c = delivered_controller()
        note = isolate_mentor(c)
        text = ' '.join(MENTOR_SIGNAL_PHRASES[s] for s in ('regular_participation', 'low_participation'))
        c.notes = [replace(n, text=text) if n == note else n for n in c.notes]
        state = c.prepare_decision_snapshot()
        self.assertEqual(state.students[0].estimate.last_observation_week, 0)
        u = weekly_uncertainty_sets(state)[0]
        self.assertTrue(u.conflict)
        self.assertFalse(u.newly_assimilated_evidence_ids)

    def test_forged_student_mentor_programme_session_and_source_are_quarantined(self):
        baseline_controller = delivered_controller()
        baseline_note = isolate_mentor(baseline_controller)
        baseline_controller.notes.remove(baseline_note)
        baseline = baseline_controller.prepare_decision_snapshot()
        for field, value in (('student_id', 's1'), ('mentor_id', 'fake'), ('programme_id', 'fake'),
                ('session_id', 'fake'), ('delivery_event_id', 'fake'), ('source_event_ids', ('fake',)),
                ('source_week', 0), ('observation_contract', 'fake')):
            with self.subTest(field=field):
                c = delivered_controller()
                note = isolate_mentor(c)
                c.notes = [n for n in c.notes if n != note]
                c.notes.append(replace(note, **{field: value}))
                state = c.prepare_decision_snapshot()
                self.assertEqual([s.estimate.condition_probabilities for s in baseline.students],
                                 [s.estimate.condition_probabilities for s in state.students])
                self.assertEqual(c.attempts[-1]['status'], 'quarantined')

    def test_missed_session_cannot_attest_condition_or_claim_delivered_service(self):
        env = world(observation_config=COMPLETE)
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)), outcomes={('s0', 'attendance', 1): False})
        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'wait'))
        missed = next(e for e in env.events if e.kind == 'session_missed')
        self.assertFalse(env.emitted_mentor_signals)
        note = next(n for n in c.notes if n.source_event_ids == (missed.event_id,))
        c.notes = [replace(note, text=MENTOR_SIGNAL_PHRASES['regular_participation'])]
        state = c.prepare_decision_snapshot()
        self.assertEqual(c.attempts[0]['status'], 'quarantined')
        self.assertIsNone(state.students[0].estimate.last_observation_week)
        self.assertFalse(c.estimates['s0'].known_actions)
        with self.assertRaises(ValueError):
            MentorSessionObservationModel(COMPLETE).generate(missed, StudentCondition.STABLE, seed=41)

    def test_no_post_session_observation_without_delivered_session(self):
        for kind in ('acceptance', 'attendance', 'delivery'):
            env = world(observation_config=COMPLETE)
            env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)), outcomes={('s0', kind, 1): False})
            self.assertFalse(env.emitted_mentor_signals)
        env = world(observation_config=COMPLETE)
        env.step(DeliveryAction())
        self.assertFalse(env.emitted_mentor_signals)

    def test_delayed_notes_assimilate_at_source_time_without_rewriting_decisions(self):
        obs = replace(COMPLETE, delay_probability=1, delay_months=2)
        c = delivered_controller(observation_config=obs,
            weekly_wait_matrix=WEEKLY_WAIT_V1, weekly_tutoring_matrix=WEEKLY_TUTORING_V1)
        note = focal_note(c)
        self.assertEqual((note.source_week, note.available_week), (1, 4))
        c.run_week()
        self.assertNotIn(note.note_id, c.processed)
        first = c.snapshots[0]
        c.run_week()
        self.assertNotIn(note.note_id, c.processed)
        state = c.prepare_decision_snapshot()
        self.assertIn(note.note_id, c.processed)
        self.assertEqual(state.students[0].estimate.last_observation_week, 1)
        self.assertEqual(c.snapshots[0], first)
        self.assertEqual(weekly_uncertainty_sets(state)[0].signal_age_weeks, 2)
        # Independent source-time filtering: signal at 0, transition+signal at 1,
        # then two delivered transitions with exact administrative masks.
        from src.observations.observable_events import SIGNALS
        expected = np.array([1/3, 1/3, 1/3, 0.])
        for t in range(4):
            if t:
                expected = expected @ c.environment.config.treatment_matrix
            enrolled = next(r.enrolled for r in c.environment.enrollment_history if r.student_id == 's0' and r.event_month == t)
            expected *= np.array([1, 1, 1, 0] if enrolled else [0, 0, 0, 1])
            signals = [e.signal for e in c.environment.emitted_signals if e.student_id == 's0' and e.event_month == t and e.available_from_month <= 4]
            signals += [e.signal for e in c.environment.emitted_mentor_signals if e.student_id == 's0' and e.source_week == t and e.available_week <= 4]
            for signal in signals:
                expected *= obs.likelihood_matrix[:, SIGNALS.index(signal)]
            expected /= expected.sum()
        np.testing.assert_allclose(state.students[0].estimate.condition_probabilities, expected, atol=1e-14)

    def test_forged_early_availability_is_rejected(self):
        c = delivered_controller(observation_config=replace(COMPLETE, delay_probability=1, delay_months=2))
        note = focal_note(c)
        c.notes = [replace(note, available_week=2)]
        state = c.prepare_decision_snapshot()
        self.assertEqual(c.attempts[0]['status'], 'quarantined')
        self.assertIsNone(state.students[0].estimate.last_observation_week)

    def test_programme_completion_does_not_mean_educational_recovery(self):
        env = world(observation_config=COMPLETE)
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        for _ in range(4):
            env.step(DeliveryAction())
        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'wait'))
        c.notes = [n for n in c.notes if n.source_event_ids == (next(e.event_id for e in env.events if e.kind == 'programme_completed'),)]
        state = c.prepare_decision_snapshot()
        np.testing.assert_allclose(state.students[0].estimate.condition_probabilities, [1/3, 1/3, 1/3, 0])
        self.assertIsNone(state.students[0].estimate.last_observation_week)
        self.assertEqual(c.estimates['s0'].observed_support_history[0].workflow_status, 'completed')
        first = next(n for n in WeeklyFeedbackController(env, c.policy).notes if n.observation_contract)
        self.assertNotIn('completed', first.text)

    def test_invalid_extraction_cannot_refresh_uncertainty(self):
        c = delivered_controller()
        note = isolate_mentor(c)
        class Corrupt:
            def extract(self, note, cutoff):
                batch = FixtureObservationExtractor().extract(note, cutoff)
                return replace(batch, facts=tuple(replace(f, numeric_value=0) for f in batch.facts))
        c.notes = [n for n in c.notes if n.source_week == 0 or n == note]
        c.extractor = Corrupt()
        state = c.prepare_decision_snapshot()
        u = weekly_uncertainty_sets(state)[0]
        self.assertEqual(c.attempts[-1]['status'], 'quarantined')
        self.assertEqual(u.latest_assimilated_source_week, 0)
        self.assertTrue(u.rejected_condition_observation)
        self.assertFalse(u.newly_assimilated_evidence_ids)

    def test_cancellation_preserves_historical_delivery_and_expenses(self):
        c = self.regular
        self.assertEqual(c.snapshots[1].ledger.spent, c.snapshots[2].ledger.spent)
        self.assertEqual(float(c.snapshots[2].ledger.released), 4)
        self.assertEqual(float(c.snapshots[2].ledger.reserved), 0)
        p = c.environment.programmes[0]
        self.assertEqual(p.delivered_sessions, 1)
        self.assertEqual(tuple(s.status for s in p.sessions), ('DELIVERED', 'RELEASED', 'RELEASED', 'RELEASED', 'RELEASED'))

    def test_mentor_channel_cannot_shift_delivery_or_transition_draws(self):
        a = world(observation_config=COMPLETE, weekly_wait_matrix=WEEKLY_WAIT_V1,
            weekly_tutoring_matrix=WEEKLY_TUTORING_V1)
        b = world(observation_config=COMPLETE, mentor_observations_enabled=False,
            weekly_wait_matrix=WEEKLY_WAIT_V1, weekly_tutoring_matrix=WEEKLY_TUTORING_V1)
        for week in range(1, 9):
            action = DeliveryAction((SupportOffer('s0', 'm0', 1),)) if week == 1 else DeliveryAction()
            a.step(action)
            b.step(action)
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.evaluator_truth, b.evaluator_truth)
        self.assertEqual(a.emitted_signals, b.emitted_signals)
        self.assertEqual([d for d in a.exogenous_draws if d['key'][1] != 'mentor_observation'], b.exogenous_draws)

    def test_mentor_generation_signal_missingness_and_delay_have_separate_keys(self):
        c = delivered_controller()
        event = next(e for e in c.environment.events if e.kind == 'session_delivered')
        a, draws_a = MentorSessionObservationModel(COMPLETE).generate(event, StudentCondition.VULNERABLE, seed=41)
        delayed, draws_b = MentorSessionObservationModel(replace(COMPLETE, delay_probability=1)).generate(
            event, StudentCondition.VULNERABLE, seed=41)
        missing, draws_c = MentorSessionObservationModel(replace(COMPLETE, missing_probability=1)).generate(
            event, StudentCondition.VULNERABLE, seed=41)
        self.assertEqual(draws_a, draws_b)
        self.assertEqual(draws_a, draws_c)
        self.assertEqual(len({d['stream'] for d in draws_a}), 3)
        self.assertEqual(a.signal, delayed.signal)
        self.assertEqual(delayed.available_week, a.available_week+1)
        self.assertIsNone(missing)

    def test_actual_transitions_use_delivery_and_never_a_note_claim(self):
        from src.school.transition_model import keyed_uniform, sample_condition
        for c in (self.regular, self.low, self.unsupported):
            env = c.environment
            for t in range(1, 9):
                delivered = {e.student_id for e in env.events if e.kind == 'session_delivered' and e.source_week == t}
                for sid, before in env.evaluator_truth[t-1][1]:
                    matrix = env.config.treatment_matrix if sid in delivered else env.config.weekly_wait_matrix
                    self.assertEqual(dict(env.evaluator_truth[t][1])[sid], sample_condition(before, matrix,
                        keyed_uniform(env.config.seed, sid, t, 'weekly_environment_transition/v1')))


class FairnessDeterminismTests(unittest.TestCase):
    def prepared_at(self, week):
        env = synthetic_environment(DeliveryConfig(num_students=3, num_mentors=1, horizon_weeks=9))
        while env.week < week:
            env.step(DeliveryAction())
        return env, env.prepare_decision()

    def test_equivalent_preparation_returns_authoritative_state_without_mutation(self):
        for week in (1, 5, 9, 10):
            with self.subTest(week=week):
                env, state = self.prepared_at(week)
                before = pickle.dumps(env.__dict__)
                # Collection order and equal reconstructed records are immaterial.
                again = env.prepare_decision(
                    estimates=tuple(replace(s.estimate) for s in reversed(state.students)),
                    risks=tuple(replace(s.risk) for s in reversed(state.students)))
                self.assertIs(again, state)
                self.assertIs(env.prepare_decision(), state)
                self.assertIs(env.observe(), state)
                self.assertEqual(before, pickle.dumps(env.__dict__))

    def test_conflicting_estimates_are_rejected_before_any_environment_mutation(self):
        for week in (1, 5, 9):
            env, state = self.prepared_at(week)
            estimates = tuple(s.estimate for s in state.students)
            risks = tuple(s.risk for s in state.students)
            changes = ({'condition_probabilities': (.1, .2, .7, 0.)},
                       {'estimate_id': 'different-estimate'}, {'evidence_ids': ('different-evidence',)},
                       {'as_of_week': week + 1},
                       {'last_observation_week': None if estimates[0].last_observation_week is not None else 0},
                       {'uncertainty': (('entropy_nats', 0.),)})
            for change in changes:
                with self.subTest(week=week, change=change):
                    changed = replace(estimates[0], **change)
                    self.assertNotEqual(changed, estimates[0])
                    changed_risks = (replace(risks[0], input_estimate_id=changed.estimate_id), *risks[1:])
                    before = pickle.dumps(env.__dict__)
                    with self.assertRaisesRegex(ValueError, 'cutoff already prepared with different estimates or risks'):
                        env.prepare_decision(estimates=(changed, *estimates[1:]), risks=changed_risks)
                    self.assertIs(env.observe(), state)
                    self.assertEqual(before, pickle.dumps(env.__dict__))
            self.assertEqual(env.window_initializations[-1].students, state.students)
            self.assertEqual(env.windows[-1], freeze_offer_window(state, env.config))

    def test_conflicting_risks_are_rejected_before_any_environment_mutation(self):
        for week in (1, 5, 9):
            env, state = self.prepared_at(week)
            estimates = tuple(s.estimate for s in state.students)
            risks = tuple(s.risk for s in state.students)
            for change in ({'probability': 1. - risks[0].probability},
                           {'input_estimate_id': 'different-estimate'}, {'as_of_week': week + 1},
                           {'weeks_remaining': risks[0].weeks_remaining + 1},
                           {'reference_policy': 'different-reference-policy'}):
                with self.subTest(week=week, change=change):
                    before = pickle.dumps(env.__dict__)
                    with self.assertRaisesRegex(ValueError, 'cutoff already prepared with different estimates or risks'):
                        env.prepare_decision(estimates=estimates,
                            risks=(replace(risks[0], **change), *risks[1:]))
                    self.assertIs(env.observe(), state)
                    self.assertEqual(before, pickle.dumps(env.__dict__))

    def test_invalid_first_preparation_does_not_freeze_or_advance_windows(self):
        env = synthetic_environment(DeliveryConfig(num_students=3, num_mentors=1, horizon_weeks=9))
        for week in (1, 5, 9):
            while env.week < week:
                env.step(DeliveryAction())
            state = env.observe()
            estimates = tuple(s.estimate for s in state.students)
            risks = tuple(s.risk for s in state.students)
            before = pickle.dumps(env.__dict__)
            with self.assertRaisesRegex(ValueError, 'stale or mismatched'):
                env.prepare_decision(estimates=estimates,
                    risks=(replace(risks[0], input_estimate_id='stale'), *risks[1:]))
            self.assertEqual(before, pickle.dumps(env.__dict__))
            prepared = env.prepare_decision(estimates=estimates, risks=risks)
            self.assertTrue(prepared.decision_prepared)
            self.assertEqual(env.windows[-1], freeze_offer_window(prepared, env.config))

    def test_real_executions_with_extra_reads_cross_week_four_to_five(self):
        for seed in (41, 42):
            for mode in ('fair_point', 'fair_robust'):
                with self.subTest(seed=seed, mode=mode):
                    config = DeliveryConfig(num_students=4, num_mentors=1, horizon_weeks=9,
                        weekly_mentor_hours=1, weekly_session_capacity=1, max_concurrent_students=1,
                        budget=11, seed=seed)
                    runs = []
                    for extra in (False, True):
                        env = synthetic_environment(config)
                        if extra:
                            env.observe()
                            env.observe()
                        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(config, mode))
                        while not env.done:
                            if extra:
                                env.observe()
                                env.observe()
                            c.run_week()
                            if extra:
                                env.observe()
                        c.final_snapshot = c.prepare_decision_snapshot()
                        c.validate()
                        runs.append(c)
                    a, b = runs
                    self.assertEqual(a.environment.windows, b.environment.windows)
                    self.assertEqual([w.start_week for w in a.environment.windows], [1, 5, 9])
                    self.assertEqual(normalized(episode_payload(a)), normalized(episode_payload(b)))
                    self.assertEqual(a.environment.exogenous_draws, b.environment.exogenous_draws)
                    self.assertEqual(a.environment.evaluator_truth, b.environment.evaluator_truth)
                    self.assertEqual(scorecard(a), scorecard(b))
                    for initial in a.environment.window_initializations:
                        self.assertEqual(initial.fairness_window, freeze_offer_window(initial, config))
                        self.assertEqual(initial.students, a.snapshots[initial.week-1].students)

    def test_read_only_snapshot_cannot_silently_initialize_allocation(self):
        env = world()
        state = env.observe()
        self.assertFalse(state.decision_prepared)
        self.assertFalse(env.windows)
        with self.assertRaisesRegex(ValueError, 'prepare_decision'):
            WeeklyDeliveryPolicy(env.config).plan(state)
        self.assertTrue(env.prepare_decision().decision_prepared)
        self.assertEqual(env.observe(), env.prepare_decision())

    def test_direct_step_adapter_uses_same_authorized_estimates_as_controller(self):
        a, b = world(), world()
        b.observe()
        state = WeeklyFeedbackController(a, WeeklyDeliveryPolicy(a.config, 'wait')).prepare_decision_snapshot()
        b.step(DeliveryAction())
        self.assertEqual(a.window_initializations, b.window_initializations)
        self.assertEqual(a.windows, b.windows)
        self.assertTrue(any(s.estimate.last_observation_week is not None for s in state.students))

    def test_reads_and_invalid_preparation_leave_frozen_histories_unchanged(self):
        env = world()
        state = env.prepare_decision()
        before = pickle.dumps(env.__dict__)
        for _ in range(3):
            self.assertEqual(env.observe(), state)
        self.assertEqual(before, pickle.dumps(env.__dict__))
        with self.assertRaisesRegex(ValueError, 'complete authorized estimates'):
            env.prepare_decision(estimates=(), risks=())
        self.assertEqual(before, pickle.dumps(env.__dict__))

    def test_final_week_offers_are_applied_to_original_window_once(self):
        env = world(count=1, mentors=1)
        for _ in range(3):
            env.step(DeliveryAction())
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 4),)), outcomes={('s0', 'acceptance', 4): False})
        env.observe()
        self.assertEqual(len(env.windows), 1)
        state = env.prepare_decision()
        self.assertEqual(env.windows[0].offered_ids, ('s0',))
        self.assertEqual(state.fairness_window.start_week, 5)
        self.assertEqual(len(env.window_initializations), 2)
        env.prepare_decision()
        self.assertEqual(len(env.window_initializations), 2)
        self.assertEqual(env.windows[0].offered_ids, ('s0',))


class MentorReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = mentor_boundary_episode()

    def test_full_session_feedback_chain_replays_exactly(self):
        from src.school.delivery_experiments import save_delivery_episode, replay_delivery_episode, read_delivery_episode
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'episode'
            save_delivery_episode(self.controller, path)
            manifest, payload = read_delivery_episode(path)
            self.assertEqual(manifest['contract'], 'scheduled_weekly/replay/v3')
            self.assertTrue(payload['mentor_observations'])
            self.assertEqual(len(payload['fairness_initializations']), 2)
            self.assertEqual(replay_delivery_episode(path)['status'], 'exact_replay_verified')

    def test_resealed_forged_notes_future_availability_and_cohorts_are_rejected(self):
        from src.school.delivery_experiments import save_delivery_episode, replay_delivery_episode
        from src.evaluation.provenance import digest, artifact_hashes
        for change in ('programme', 'session', 'availability', 'cohort', 'signal', 'protocol'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'episode'
                save_delivery_episode(self.controller, path)
                payload = json.loads((path/'episode.json').read_text())
                manifest = json.loads((path/'manifest.json').read_text())
                note = next(n for n in payload['notes'] if n['observation_contract'])
                if change == 'programme':
                    note['programme_id'] = 'forged'
                elif change == 'session':
                    note['session_id'] = 'forged'
                elif change == 'availability':
                    note['available_week'] += 1
                elif change == 'cohort':
                    cell = next(c for c in payload['fairness_initializations'][0]['fairness_window']['cohorts'] if c['student_ids'])
                    cell['student_ids'] = []
                elif change == 'signal':
                    payload['mentor_observations'][0]['signal'] = 'no_recent_contact'
                else:
                    manifest['mentor_observation_protocol']['contract'] = 'forged'
                manifest['payload_sha256'] = digest(payload)
                manifest['episode_identity'] = digest({k: v for k, v in manifest.items() if k != 'episode_identity'})
                (path/'episode.json').write_text(json.dumps(payload))
                (path/'manifest.json').write_text(json.dumps(manifest))
                (path/'artifact_integrity.json').write_text(json.dumps(artifact_hashes(path)))
                with self.assertRaises(ValueError):
                    replay_delivery_episode(path)


if __name__ == '__main__':
    unittest.main()

"""Phase 1 information boundaries, using controlled evidence and two private worlds."""
from dataclasses import asdict, replace
import json
import unittest

from src.intervention.feedback_notes import NoteQuality, render_note
from src.intervention.observation_extractor import FixtureObservationExtractor
from src.observations.observable_events import ObservableEvent, EnrollmentRecord
from src.school.state_estimator import StudentStateEstimator
from src.school.observation_model import ObservationConfig
from src.school.simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from src.school.cmdp_environment import CMDPEnvironment
from src.school.baseline_policy import BaselinePolicy
from src.school.allocation_result import AllocationResult
from src.school.transition_model import sample_condition
from src.utils.keyed_random import keyed_uniform
from src.school.uncertainty_scenarios import build_belief_scenarios, UncertaintyScenarioConfig
from src.school.transition_model import P_WAIT, P_PROGRAMME
from tests.cmdp_helpers import environment


def evidence(sid, month=0, quality=NoteQuality(), text=None):
    note = render_note(ObservableEvent(f'{sid}:{month}', sid, month, month+1,
                                      'low_participation'), seed=1, quality=quality)
    if text is not None:
        note = replace(note, text=text)
    return FixtureObservationExtractor().extract(note, month+1)


def snapshot(env, estimate):
    return env.operational_snapshot((EnrollmentRecord(estimate.student_id, 0, 1, True),),
        estimates=(estimate,), risks=(SimulatedWithdrawalRiskEstimator().predict(
            estimate, env.config.horizon),))


def details(estimate):
    env, students, _ = environment(1)
    estimate = replace(estimate, student_id=students[0].student_id)
    state = snapshot(env, replace(estimate, as_of_month=1))
    # Advance the decision view without introducing extra simulated observations.
    state = replace(state, month=estimate.as_of_month,
        estimated_student_states=(estimate,), risk_estimates=(
            SimulatedWithdrawalRiskEstimator().predict(estimate, state.months_remaining),))
    scenarios = build_belief_scenarios(state, UncertaintyScenarioConfig(), P_WAIT, P_PROGRAMME)
    return dict(dict(dict(scenarios[0].parameters)['student_uncertainty'])[estimate.student_id])


class FreshnessTests(unittest.TestCase):
    def test_unusable_reports_and_registry_do_not_refresh(self):
        cases = [evidence('A', quality=NoteQuality(conflict_probability=1)),
                 evidence('A', quality=NoteQuality(omission_probability=1)),
                 evidence('A', text='The student reports greater participation, but progress is not yet consistent.'),
                 evidence('A', text='The student completed the scheduled mentoring appointments.')]
        for report in cases:
            with self.subTest(facts=report.facts):
                estimator = StudentStateEstimator()
                state = estimator.initialize('A', (report,), registry=(EnrollmentRecord('A',0,1,True),))
                self.assertEqual(state.condition_probabilities, estimator.prior)
                self.assertIsNone(state.last_observation_month)
                self.assertTrue(dict(state.observation_uncertainty)['missing_current_signal'])
                self.assertEqual(details(state)['mixture_radius'], .75)
                self.assertEqual(details(state)['documentation_subset'], 'missing_or_stale')
                self.assertTrue(state.observation_history)
                if report.facts[0].field == 'mentoring_support':
                    self.assertTrue(state.observed_support_history)

    def test_zero_likelihood_does_not_refresh(self):
        estimator = StudentStateEstimator(observation_config=ObservationConfig(
            emissions=((1,0,0,0),)*4, misleading_probability=0))
        state = estimator.initialize('A', (evidence('A'),))
        self.assertEqual(state.condition_probabilities, estimator.prior)
        self.assertIsNone(state.last_observation_month)
        self.assertEqual(details(state)['mixture_radius'], .75)

    def test_valid_delayed_duplicate_replay_and_aging(self):
        estimator = StudentStateEstimator()
        report = evidence('A')
        initial = estimator.initialize('A', (report,))
        self.assertNotEqual(initial.condition_probabilities, estimator.prior)
        self.assertEqual(initial.last_observation_month, 0)
        self.assertEqual(details(initial)['mixture_radius'], .25)
        duplicate = estimator.update(initial, (report,), as_of_month=1)
        self.assertEqual(initial, duplicate)
        aged = estimator.update(initial, as_of_month=3)
        delayed = StudentStateEstimator().initialize('A', (report,), as_of_month=3)
        self.assertEqual(aged, delayed)
        self.assertEqual(aged.last_observation_month, 0)
        self.assertAlmostEqual(details(aged)['mixture_radius'], .625)
        bad = evidence('A', month=2, quality=NoteQuality(conflict_probability=1))
        rejected = estimator.update(aged, (bad,), as_of_month=3)
        self.assertEqual(aged.condition_probabilities, rejected.condition_probabilities)
        self.assertEqual(rejected.last_observation_month, 0)
        self.assertEqual(details(aged)['mixture_radius'], details(rejected)['mixture_radius'])
        replay = StudentStateEstimator().initialize('A', (bad, report), as_of_month=3)
        self.assertEqual(rejected, replay)


class PublicInputTests(unittest.TestCase):
    def worlds(self, changes):
        env, students, mentors = environment(1)
        base = replace(students[0], anchor_grade1_0_20=10, math_grade1_0_20=None,
            past_failures_count=0, internet_at_home=True, travel_time_category=2,
            study_time_category=2, family_relationship_rating=3, health_self_rating=3,
            initial_attendance_fraction_assumed=1., initial_engagement_assumed=1.)
        altered = replace(base, **changes)
        worlds = [CMDPEnvironment([s], mentors, env.config) for s in (base, altered)]
        estimate = StudentStateEstimator().initialize(base.student_id, (evidence(base.student_id),))
        return base, altered, worlds, [snapshot(w, estimate) for w in worlds]

    def test_hidden_reset_does_not_enter_public_inputs(self):
        base, altered, worlds, states = self.worlds(dict(
            initial_attendance_fraction_assumed=.01, initial_engagement_assumed=.1))
        self.assertNotEqual(worlds[0].observe().students[0].condition,
                            worlds[1].observe().students[0].condition)
        self.assertEqual(states[0], states[1])
        self.assertEqual(base.need_profile, altered.need_profile)
        payload = json.dumps(asdict(states[0]))
        for name in ('initial_attendance', 'initial_engagement', '_conditions', 'math_grade'):
            self.assertNotIn(name, payload)
        self.assertEqual(states[0].students[0].eligible, states[1].students[0].eligible)
        self.assertEqual(states[0].mentors, states[1].mentors)
        for policy in ('need_priority', 'severity', 'random', 'longest_waiting'):
            self.assertEqual(BaselinePolicy(policy).plan(states[0]), BaselinePolicy(policy).plan(states[1]))
        for world in worlds:
            truth = world.observe().students[0].condition
            sid = base.student_id
            expected = sample_condition(truth, P_WAIT,
                keyed_uniform(world.config.seed, sid, 1, 'environment_transition'))
            world.step(AllocationResult(()))
            self.assertEqual(world.observe().students[0].condition, expected)

    def test_unavailable_math_does_not_enter_public_inputs(self):
        base, altered, _, states = self.worlds(dict(math_grade1_0_20=0))
        self.assertIsNone(base.math_grade1_0_20)
        self.assertEqual(altered.math_grade1_0_20, 0)
        self.assertEqual(base.learning_gap, altered.learning_gap)
        self.assertEqual(base.need_profile, altered.need_profile)
        self.assertEqual(states[0], states[1])
        # A second student makes priority-order invariance nontrivial.
        comparator = replace(states[0].students[0], student_id='comparator', need_score=.25)
        ordered = [BaselinePolicy('need_priority').rank_students(
            replace(state, students=(*state.students, comparator))) for state in states]
        self.assertEqual(ordered[0], ordered[1])
        self.assertEqual(replace(base, anchor_grade1_0_20=2).learning_gap, .8)

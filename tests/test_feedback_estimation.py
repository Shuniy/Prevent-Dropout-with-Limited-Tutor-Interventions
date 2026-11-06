"""Hand-calculated filtering, action indexing, late arrival and risk checks."""

from dataclasses import replace
import unittest
import numpy as np

from src.intervention.feedback_notes import render_note
from src.intervention.observation_extractor import FixtureObservationExtractor
from src.school.belief_state import EstimatedStudentState
from src.observations.observable_events import ObservableEvent
from src.school.observation_model import ObservationConfig
from src.school.retention_value import estimate_belief_benefit, estimate_incremental_benefit, expected_terminal_retention
from src.school.simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from src.school.state_estimator import StudentStateEstimator
from src.school.student_condition import STATES
from src.school.transition_model import P_PROGRAMME, P_WAIT


def batch(sid="A", month=0, signal="low_participation", cutoff=None):
    item = render_note(ObservableEvent(f"{sid}:{month}", sid, month, month + 1, signal), seed=1)
    return FixtureObservationExtractor().extract(item, month + 1 if cutoff is None else cutoff)


class BeliefAndRiskTests(unittest.TestCase):
    def test_hand_calculated_bayes_and_no_observation_prediction(self):
        emissions = ((.5, .25, .125, .125), (.25, .25, .375, .125),
                     (.125, .125, .5, .25), (.25, .25, .25, .25))
        estimator = StudentStateEstimator(observation_config=ObservationConfig(
            emissions=emissions, misleading_probability=0), prior=(.5, .5, 0, 0))
        initial = estimator.initialize("A", (batch(),))
        np.testing.assert_allclose(initial.condition_probabilities, (.25, .75, 0, 0))
        next_state = estimator.update(initial, as_of_month=2)
        np.testing.assert_allclose(next_state.condition_probabilities, np.array([.25, .75, 0, 0]) @ P_WAIT)
        self.assertAlmostEqual(sum(next_state.condition_probabilities), 1)

    def test_programme_prediction_once_then_wait(self):
        estimator = StudentStateEstimator(prior=(0, 1, 0, 0))
        initial = estimator.initialize("A")
        treated = estimator.update(initial, known_actions=(1,), as_of_month=2)
        np.testing.assert_allclose(treated.condition_probabilities, P_PROGRAMME[1])
        later = estimator.update(treated, known_actions=(1,), as_of_month=3)
        np.testing.assert_allclose(later.condition_probabilities, P_PROGRAMME[1] @ P_WAIT)
        with self.assertRaises(ValueError):
            estimator.update(later, known_actions=(1, 2), as_of_month=4)

    def test_duplicate_event_cannot_gain_weight_from_another_note(self):
        estimator = StudentStateEstimator()
        observation = batch()
        initial = estimator.initialize("A", (observation,))
        duplicate = replace(observation, note_id="duplicate")
        updated = estimator.update(initial, (duplicate,), as_of_month=1)
        self.assertEqual(updated.condition_probabilities, initial.condition_probabilities)
        self.assertEqual(updated.evidence_ids, initial.evidence_ids)
        self.assertIn("duplicate_evidence", str(estimator.updates[-1].rejected_observations))

    def test_delayed_evidence_replayed_at_source_time_without_rewriting_history(self):
        estimator = StudentStateEstimator()
        initial = estimator.initialize("A")
        historical = estimator.update(initial, as_of_month=2)
        delayed = batch(month=0, cutoff=3)
        current = estimator.update(historical, (delayed,), as_of_month=3)
        gold = StudentStateEstimator().initialize("A", (batch(),))
        np.testing.assert_allclose(current.condition_probabilities,
                                  np.array(gold.condition_probabilities) @ P_WAIT @ P_WAIT)
        self.assertEqual(historical.condition_probabilities, tuple(np.array(initial.condition_probabilities) @ P_WAIT))
        self.assertEqual(current, StudentStateEstimator().update(historical, (delayed,), as_of_month=3))

    def test_conflicting_correlated_event_preserves_prediction(self):
        from src.intervention.feedback_notes import NoteQuality
        item = render_note(ObservableEvent("event", "A", 0, 1, "low_participation"),
                           seed=1, quality=NoteQuality(conflict_probability=1))
        observation = FixtureObservationExtractor().extract(item, 1)
        estimator = StudentStateEstimator()
        state = estimator.initialize("A", (observation,))
        self.assertEqual(state.condition_probabilities, estimator.prior)
        self.assertTrue(state.unresolved_observations)

    def test_undeclared_qualitative_evidence_is_preserved_without_numeric_change(self):
        item = replace(render_note(ObservableEvent("event", "A", 0, 1, "low_participation"), seed=1),
                       text="The student reports greater participation, but progress is not yet consistent.")
        estimator = StudentStateEstimator()
        state = estimator.initialize("A", (FixtureObservationExtractor().extract(item, 1),))
        self.assertEqual(state.condition_probabilities, estimator.prior)
        self.assertEqual(len(state.unresolved_observations), 1)

    def test_zero_likelihood_is_logged_and_invalid_belief_rejected(self):
        estimator = StudentStateEstimator(observation_config=ObservationConfig(
            emissions=((1, 0, 0, 0),) * 4, misleading_probability=0))
        state = estimator.initialize("A", (batch(),))
        self.assertEqual(state.condition_probabilities, estimator.prior)
        self.assertIn("zero_likelihood", str(estimator.updates[-1].rejected_observations))
        for belief in ((.5, .5, .5, 0), (float("nan"), 0, 0, 1), (-1, 1, 1, 0)):
            with self.assertRaises(ValueError):
                StudentStateEstimator(prior=belief)

    def test_risk_one_hot_horizons_and_benefit_remain_distinct(self):
        risk_model = SimulatedWithdrawalRiskEstimator()
        for index, condition in enumerate(STATES):
            belief = tuple(float(i == index) for i in range(4))
            estimate = StudentStateEstimator(prior=belief).initialize("A")
            for horizon in (0, 1, 12):
                risk = risk_model.predict(estimate, horizon)
                self.assertAlmostEqual(risk.probability, 1 - expected_terminal_retention(condition, horizon, P_WAIT))
                self.assertEqual(risk.input_estimate_id, estimate.estimate_id)
                self.assertEqual(risk.target, "synthetic_terminal_non_enrollment")
            self.assertAlmostEqual(estimate_belief_benefit(belief, 3, P_WAIT, P_PROGRAMME),
                                   estimate_incremental_benefit(condition, 3, P_WAIT, P_PROGRAMME))
        state = StudentStateEstimator(prior=(.2, .5, .3, 0)).initialize("A")
        expected = 1 - np.array(state.condition_probabilities) @ np.linalg.matrix_power(P_WAIT, 3) @ [1, 1, 1, 0]
        self.assertAlmostEqual(risk_model.predict(state, 3).probability, expected)
        self.assertNotAlmostEqual(expected, estimate_belief_benefit(state.condition_probabilities, 3, P_WAIT, P_PROGRAMME))
        with self.assertRaises(ValueError):
            risk_model.predict(state, -1)

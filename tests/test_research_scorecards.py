from dataclasses import replace
import json
import math
import unittest
from unittest.mock import patch

import numpy as np

from src.evaluation.scorecards import episode_summary, score_episode, LOG_EPSILON
from src.school.closed_loop_controller import ClosedLoopCMDPController
from src.school.cmdp_scenarios import build_school
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.observation_model import ObservationConfig
from src.school.scenario_config import ScenarioConfig
from src.school.student_condition import STATES


def episode(mode="structured", *, missing=0):
    config = ScenarioConfig(num_students=6, num_mentors=1, horizon=2,
                            monthly_admissions=1, monthly_appointments=5,
                            budget=10, fairness_window=2, fairness_min_access=.5)
    environment = build_school(config).create_cmdp_environment(config=config)
    return ClosedLoopCMDPController(environment, ConstrainedAllocationPlanner(),
        mode=mode, observation_config=ObservationConfig(missing_probability=missing)).run_episode()


class ResearchScorecardsTests(unittest.TestCase):
    def test_multiclass_brier_sums_four_classes_and_clips_nll(self):
        controller = episode()
        state = controller.snapshots[0]
        estimate = state.estimated_student_states[0]
        actual = dict(controller.evaluator_truth[0]["conditions"])[estimate.student_id]
        incorrect = (STATES.index(actual) + 1) % 3
        probability = tuple(float(index == incorrect) for index in range(4))
        changed = replace(estimate, condition_probabilities=probability)
        controller.snapshots[0] = replace(state, estimated_student_states=(
            changed, *state.estimated_student_states[1:]))
        rows = score_episode(controller)["belief_records"]
        row = next(row for row in rows if row["student_id"] == estimate.student_id and row["cutoff"] == 1)
        self.assertEqual(row["brier"], 2)
        self.assertAlmostEqual(row["nll"], -math.log(LOG_EPSILON))
        self.assertEqual(row["entropy_nats"], 0)
        self.assertEqual(row["accuracy"], 0)

    def test_wait_reference_is_conditional_model_probability_not_treated_endpoint(self):
        controller = episode()
        rows = score_episode(controller)["risk_records"]
        truth = dict(controller.evaluator_truth[0]["conditions"])
        wait = np.asarray(controller.environment.transition_assumptions[0])
        row = next(row for row in rows if row["cutoff"] == 1)
        reference = np.linalg.matrix_power(wait, 2)[STATES.index(truth[row["student_id"]]), 3]
        prediction = row["prediction"]
        self.assertAlmostEqual(row["reference_probability"], reference)
        self.assertGreater(reference, 0)
        self.assertLess(reference, 1)
        self.assertAlmostEqual(row["expected_brier"], reference * (1 - prediction) ** 2
                               + (1 - reference) * prediction ** 2)
        self.assertAlmostEqual(row["probability_squared_error"], (prediction - reference) ** 2)
        # Expected Bernoulli Brier includes irreducible reference uncertainty.
        self.assertAlmostEqual(row["expected_brier"] - row["probability_squared_error"],
                               reference * (1 - reference))

    def test_oracle_scores_actual_point_mass_input_and_missingness_by_cutoff_group(self):
        oracle = score_episode(episode("oracle", missing=1))
        self.assertTrue(all(row["brier"] == 0 for row in oracle["belief_records"]))
        self.assertTrue(all(row["probability_squared_error"] < 1e-28 for row in oracle["risk_records"]))
        self.assertTrue(all(row["prediction_source"] == "oracle_current_state_reference"
                            for row in oracle["belief_records"]))
        ordinary = score_episode(episode(missing=1))
        self.assertTrue(all(row["missing_current_signal"] == 1 for row in ordinary["belief_metrics"]))
        self.assertTrue(all(row["no_observation_history"] == 1 for row in ordinary["belief_metrics"]))
        self.assertTrue(any(row["attribute"] == "sex_source" for row in ordinary["belief_metrics"]))
        overall = [row for row in ordinary["belief_metrics"] if row["attribute"] == "all"]
        self.assertEqual([row["cutoff"] for row in overall], [1, 2, 3])
        self.assertTrue(all(sum(map(sum, json.loads(row["confusion_matrix"]))) == row["count"]
                            for row in overall))

    def test_frozen_memberships_and_world_summary_reproduce_execution_without_mutation(self):
        controller = episode()
        before = list(controller.evaluator_truth), list(controller.snapshots), list(controller.decisions)
        # Evaluation must never re-enter the decision or estimation path.
        with patch.object(controller.policy, "plan", side_effect=AssertionError("policy called")), \
             patch.object(controller.estimator, "update", side_effect=AssertionError("filter called")), \
             patch.object(controller.environment, "observe", side_effect=AssertionError("truth interface called")):
            tables = score_episode(controller)
            summary = episode_summary(controller, "resource", "structured", "tiny", 42)
        self.assertEqual(before, (controller.evaluator_truth, controller.snapshots, controller.decisions))
        self.assertEqual(len(tables["group_access"]), len(controller.windows[0].cohorts))
        for row, cohort in zip(tables["group_access"], controller.windows[0].cohorts):
            self.assertEqual(json.loads(row["student_ids"]), sorted(cohort.student_ids))
            self.assertEqual(row["eligible_count"], len(cohort.student_ids))
            self.assertEqual(len(row["membership_digest"]), 64)
        self.assertEqual(summary["normalized_shortfall"], sum(
            row["normalized_shortfall_contribution"] for row in tables["group_access"]))
        self.assertEqual(summary["terminal_enrolled"], tables["monthly_results"][-1]["enrolled"])
        self.assertEqual(summary["enrolled_student_months"], sum(
            row["enrolled"] for row in tables["monthly_results"] if row["month"]))
        self.assertAlmostEqual(summary["spending"], 10 - controller.environment.records[-1].remaining_budget)
        self.assertEqual(summary["solver_incomplete_count"], 0)


if __name__ == "__main__":
    unittest.main()

"""Pure observed-input scenario construction and provenance checks."""

from dataclasses import replace
import unittest

import numpy as np

from src.school.belief_state import EstimatedStudentState, validate_belief
from src.school.constraints import candidate_assignments
from src.school.simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from src.school.student_condition import StudentCondition as S
from src.school.transition_model import P_WAIT, P_PROGRAMME
from src.school.uncertainty_scenarios import (BeliefScenario, UncertaintyScenarioConfig,
    build_belief_scenarios, scenario_candidate_values)
from tests.cmdp_helpers import environment


def estimated_state(count=3, *, month=1, horizon=2, beliefs=None, **options):
    env, _, _ = environment(count, horizon=horizon, num_mentors=1, **options)
    state = env.observe()
    beliefs = beliefs or [(1/3, 1/3, 1/3, 0)] * count
    estimates = tuple(EstimatedStudentState(s.student_id, month, tuple(beliefs[index]),
        f"estimate-{index}-{month}", observation_uncertainty=(
            ("missing_current_signal", index % 2 == 1),),
        last_observation_month=month - 1 if index % 2 == 0 else None)
        for index, s in enumerate(state.students))
    risks = tuple(SimulatedWithdrawalRiskEstimator().predict(e, horizon - month + 1) for e in estimates)
    return replace(state, month=month, months_remaining=horizon - month + 1,
        observation_mode="estimated_state", estimated_student_states=estimates, risk_estimates=risks,
        students=tuple(replace(s, condition=S.VULNERABLE, support_type="tutoring",
            disadvantage_proxy=False, sex_source="F", condition_probabilities=e.condition_probabilities,
            estimate_id=e.estimate_id) for s, e in zip(state.students, estimates)))


class UncertaintyScenarioTests(unittest.TestCase):
    def test_bounded_valid_mixtures_and_documentation_partition(self):
        state = estimated_state()
        config = UncertaintyScenarioConfig()
        scenarios = build_belief_scenarios(state, config, P_WAIT, P_PROGRAMME)
        self.assertEqual(len(scenarios), 5)
        nominal = dict(scenarios[0].beliefs)
        uncertainty = dict(dict(scenarios[0].parameters)["student_uncertainty"])
        for index, student in enumerate(state.students):
            details = dict(uncertainty[student.student_id])
            self.assertAlmostEqual(details["mixture_radius"], .25 if index % 2 == 0 else .75)
            self.assertEqual(details["source"], "decision_state_estimate")
        for scenario in scenarios:
            self.assertIn("not_empirically_calibrated", scenario.source)
            for sid, probabilities in scenario.beliefs:
                validate_belief(probabilities)
                radius = dict(uncertainty[sid])["mixture_radius"]
                self.assertLessEqual(sum(abs(a - b) for a, b in zip(probabilities, nominal[sid])) / 2,
                                     radius + 1e-12)
            if scenario.name.startswith("fresh_documented"):
                self.assertEqual(dict(scenario.beliefs)[state.students[1].student_id],
                                 nominal[state.students[1].student_id])
            if scenario.name.startswith("missing_or_stale"):
                self.assertEqual(dict(scenario.beliefs)[state.students[0].student_id],
                                 nominal[state.students[0].student_id])

    def test_saturation_zero_radius_and_explicit_oracle_point_masses(self):
        state = estimated_state()
        high = build_belief_scenarios(state, UncertaintyScenarioConfig(radius=1), P_WAIT, P_PROGRAMME)
        details = dict(dict(high[0].parameters)["student_uncertainty"])
        self.assertTrue(all(dict(row)["mixture_radius"] == 1 for row in details.values()))
        self.assertEqual(len(build_belief_scenarios(state, UncertaintyScenarioConfig(radius=0),
                                                  P_WAIT, P_PROGRAMME)), 1)
        oracle = replace(state, observation_mode="fully_observed_benchmark")
        scenarios = build_belief_scenarios(oracle, UncertaintyScenarioConfig(), P_WAIT, P_PROGRAMME)
        self.assertEqual(len(scenarios), 1)
        self.assertTrue(all(b == (0, 1, 0, 0) for _, b in scenarios[0].beliefs))

    def test_student_map_and_demographics_do_not_drive_uncertainty(self):
        state = estimated_state()
        changed = replace(state, students=tuple(replace(s, condition=None,
            disadvantage_proxy=True, sex_source=None, need_score=999) for s in state.students))
        args = UncertaintyScenarioConfig(), P_WAIT, P_PROGRAMME
        self.assertEqual(build_belief_scenarios(state, *args), build_belief_scenarios(changed, *args))

    def test_future_candidate_values_use_wait_projection(self):
        state = estimated_state(1)
        scenario = build_belief_scenarios(state, UncertaintyScenarioConfig(radius=0), P_WAIT, P_PROGRAMME)
        candidates = candidate_assignments(state)
        future = tuple(replace(a, month=2) for a in candidates)
        values = scenario_candidate_values(state, (*candidates, *future), scenario, P_WAIT, P_PROGRAMME)[0]
        b = np.asarray(state.students[0].condition_probabilities)
        terminal = np.asarray([1, 1, 1, 0])
        self.assertAlmostEqual(values[0], b @ (P_PROGRAMME - P_WAIT) @ P_WAIT @ terminal)
        self.assertAlmostEqual(values[1], b @ P_WAIT @ (P_PROGRAMME - P_WAIT) @ terminal)

    def test_invalid_config_scenario_and_cutoff_are_rejected(self):
        for options in ({"radius": -1}, {"radius": float("nan")}, {"missingness_multiplier": .5},
                        {"freshness_months": 0}, {"freshness_months": True}):
            with self.assertRaises(ValueError):
                UncertaintyScenarioConfig(**options)
        with self.assertRaises(ValueError):
            BeliefScenario("bad", (("a", (.2, .2, .2, .2)),))
        state = estimated_state(1)
        with self.assertRaises(ValueError):
            build_belief_scenarios(replace(state, month=2), UncertaintyScenarioConfig(), P_WAIT, P_PROGRAMME)
        with self.assertRaises(ValueError):
            scenario_candidate_values(state, candidate_assignments(state),
                (BeliefScenario("missing", ()),), P_WAIT, P_PROGRAMME)


if __name__ == "__main__":
    unittest.main()

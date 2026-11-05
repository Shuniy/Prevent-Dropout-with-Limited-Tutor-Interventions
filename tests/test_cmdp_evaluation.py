from dataclasses import replace
import unittest

from src.school.cmdp_experiments import run_policy
from src.school.cmdp_reports import summarize
from src.school.cmdp_metrics import paired_difference
from src.school.observation_adapter import observation_from_result
from src.school.scenario_config import ScenarioConfig
from src.intervention.intervention_result import InterventionResult
from tests.cmdp_helpers import environment


class EvaluationTests(unittest.TestCase):
    def test_paired_ci_uses_world_differences(self):
        difference = paired_difference([10, 11, 12], [8, 9, 10])
        self.assertEqual(
            difference, {"mean": 2.0, "ci95_low": 2.0, "ci95_high": 2.0, "paired_episodes": 3}
        )
        with self.assertRaises(ValueError):
            paired_difference([1], [1, 2])

    def test_episode_and_summary_reproduce_except_wall_clock(self):
        rows = []
        for seed in (42, 43):
            for policy in ("wait", "random"):
                config = ScenarioConfig(num_students=5, horizon=2, seed=seed)
                first, trajectory = run_policy(config, policy)
                second, repeated = run_policy(config, policy)
                self.assertEqual(first, second)
                self.assertEqual(trajectory, repeated)
                rows.append(
                    {
                        "scenario": "tiny",
                        "partition": "development",
                        "seed": seed,
                        "policy": policy,
                        **first,
                    }
                )
        self.assertEqual(summarize(rows), summarize(list(reversed(rows))))

    def test_existing_result_adapter_cannot_write_simulated_truth(self):
        env, _, _ = environment()
        before = env.observe()
        result = InterventionResult(
            "run",
            "programme",
            1,
            before.students[0].student_id,
            "mentor-1",
            "tutoring",
            5,
            5,
            "completed",
            "completed",
            "yes",
            "yes",
            "yes",
        )
        observation = observation_from_result(result, current_month=2)
        self.assertEqual(observation.attendance_improved, "yes")
        self.assertFalse(hasattr(observation, "condition"))
        self.assertEqual(env.observe(), before)
        with self.assertRaises(ValueError):
            observation_from_result(result, current_month=1)
        with self.assertRaises(ValueError):
            observation_from_result({"condition": "stable"}, current_month=2)

    def test_config_rejects_unsupported_repeats_and_invalid_values(self):
        for values in (
            {"max_programmes_per_student": 2},
            {"budget": float("nan")},
            {"horizon": 0},
            {"effect_strength": 2},
            {"appointments_per_programme": 1},
        ):
            with self.assertRaises(ValueError):
                replace(ScenarioConfig(), **values)

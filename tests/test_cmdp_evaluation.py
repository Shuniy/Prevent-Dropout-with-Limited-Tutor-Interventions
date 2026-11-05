from dataclasses import replace
import unittest

import numpy as np

from src.school.allocation_result import AllocationResult
from src.school.cmdp_environment import CMDPEnvironment
from src.school.cmdp_experiments import run_policy
from src.school.cmdp_reports import summarize
from src.school.cmdp_metrics import episode_metrics, paired_difference
from src.school.constraints import candidate_assignments
from src.school.fairness_audit import freeze_cohorts
from src.school.observation_adapter import observation_from_result
from src.school.scenario_config import ScenarioConfig
from src.intervention.intervention_result import InterventionResult
from tests.cmdp_helpers import environment


class EvaluationTests(unittest.TestCase):
    def test_monthly_summaries_include_initial_state_and_actual_resources(self):
        env, students, mentors = environment(
            3, horizon=3, num_mentors=1, monthly_admissions=1,
            monthly_appointments=10, cost_per_appointment=2, budget=20,
        )
        for student, attendance in zip(students, (0.95, 0.8, 0.5)):
            student.initial_attendance_fraction_assumed = attendance
            student.initial_engagement_assumed = 0.9
            student.anchor_grade1_0_20 = 18
        mentors[0].availability_by_step[1] = replace(
            mentors[0].availability_by_step[1], max_sessions=0
        )
        wait = np.array([[0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]])
        env = CMDPEnvironment(students, mentors, env.config, wait_matrix=wait, treatment_matrix=np.eye(4))
        initial = env.observe()
        cohorts = freeze_cohorts(initial)
        first = candidate_assignments(initial)[0]
        env.step(AllocationResult((first,)))
        env.step(AllocationResult())
        env.step(AllocationResult())
        metrics = episode_metrics(env, initial, cohorts)
        months = metrics["monthly_summaries"]
        self.assertEqual([row["month"] for row in months], [0, 1, 2, 3])
        self.assertEqual([row["enrolled"] for row in months], [3, 2, 2, 1])
        self.assertEqual([row["newly_withdrawn"] for row in months], [0, 1, 0, 1])
        self.assertEqual([row["withdrawn"] for row in months], [0, 1, 1, 2])
        self.assertEqual([row["programmes_started"] for row in months], [0, 1, 0, 0])
        self.assertEqual([row["appointments_delivered"] for row in months], [0, 5, 0, 0])
        self.assertEqual([row["spending"] for row in months], [0, 10, 0, 0])
        self.assertEqual([row["cumulative_spending"] for row in months], [0, 10, 10, 10])
        self.assertEqual([row["remaining_budget"] for row in months], [20, 10, 10, 10])
        self.assertEqual([row["eligible_students"] for row in months], [3, 1, 1, 1])
        self.assertEqual([row["mean_eligible_waiting_months"] for row in months], [0, 1, 2, 3])
        self.assertEqual(months[1]["mentor_utilization"][0]["admission_utilization"], 1)
        self.assertEqual(months[1]["mentor_utilization"][0]["appointment_utilization"], 0.5)
        self.assertEqual(months[2]["mentor_utilization"][0]["appointment_capacity"], 0)
        self.assertEqual(months[2]["mentor_utilization"][0]["appointment_utilization"], 0)
        self.assertEqual(months[-1]["retention_rate"], metrics["retention_rate"])
        self.assertEqual(months[-1]["dropout_rate"], 2 / 3)
        self.assertEqual(metrics["enrolled_student_months"], 5)
        for cohort, audit in zip(cohorts, metrics["group_access"]):
            waits = {s.student_id: s.waiting_months for s in env.observe().students}
            self.assertEqual(
                audit["mean_waiting_months"],
                sum(waits[sid] for sid in cohort.student_ids) / len(cohort.student_ids),
            )

    def test_empty_cohort_monthly_summaries_have_no_rates_or_waiting(self):
        env, _, _ = environment(0, horizon=1, num_mentors=0, budget=0)
        initial = env.observe()
        env.step(AllocationResult())
        metrics = episode_metrics(env, initial, ())
        for row in metrics["monthly_summaries"]:
            self.assertIsNone(row["retention_rate"])
            self.assertIsNone(row["dropout_rate"])
            self.assertEqual(row["mean_eligible_waiting_months"], 0)
            self.assertEqual(row["mentor_utilization"], [])

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

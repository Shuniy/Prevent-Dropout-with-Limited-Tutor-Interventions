"""Run paired CMDP experiments through School; CLI parsing belongs to main.py."""

from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from ..utils.constants import DEFAULT_STUDENT_DATA_PATH
from .allocation_policies import DEFAULT_POLICIES, POLICY_NAMES, make_policy
from .cmdp_metrics import episode_metrics
from .cmdp_reports import format_monthly_summary, save_reports, summarize
from .cmdp_scenarios import build_environment, build_school
from .exact_tiny_mdp import ExactTinyMDP
from .fairness_audit import audit_access
from .student_condition import StudentCondition
from .transition_model import P_WAIT, programme_matrix


BUDGETS = (0, 50, 150, 300, 500)


def run_policy(config, name):
    school = build_school(config)
    simulation = school.run_cmdp(make_policy(name, config), config=config)
    env = simulation.environment
    metrics = episode_metrics(env, simulation.initial_state, simulation.initial_cohorts)

    metrics["fairness_windows"] = [
        entry
        for start, frozen in simulation.window_cohorts
        for entry in audit_access(
            frozen,
            env.records,
            start_month=start,
            end_month=min(config.horizon, start + config.fairness_window - 1),
            minimum_access=config.fairness_min_access,
        )
    ]
    metrics["window_normalized_shortfall"] = sum(
        entry["normalized_shortfall"] for entry in metrics["fairness_windows"]
    )
    trajectory = [asdict(record) for record in env.records]
    return metrics, trajectory


def tiny_comparison(config):
    tiny_config = replace(
        config,
        num_students=2,
        num_mentors=1,
        horizon=3,
        budget=5,
        cost_per_appointment=1.0,
        effect_strength=1.0,
    )
    state = build_environment(tiny_config).observe()
    state = replace(
        state,
        students=tuple(
            replace(student, condition=StudentCondition.STABLE) for student in state.students
        ),
    )
    result = ExactTinyMDP(state).compare()
    result["exact_first_action"] = [asdict(item) for item in result["exact_first_action"]]
    result["scenario"] = (
        "Two initially stable students, three months, one generalist mentor, one funded programme"
    )
    return result


def run_experiments(
    config,
    *,
    output=None,
    suite="default",
    development_seed_count=10,
    evaluation_seed_count=30,
    policies=DEFAULT_POLICIES,
    print_monthly=False,
):
    """Run independent paired worlds and save results in a new destination."""
    if suite not in ("default", "full"):
        raise ValueError("suite must be default or full")
    if not 1 <= development_seed_count <= 10 or not 1 <= evaluation_seed_count <= 30:
        raise ValueError("use 1-10 development seeds and 1-30 independent evaluation seeds")
    policies = tuple(policies)
    if (
        not policies
        or len(policies) != len(set(policies))
        or any(name not in POLICY_NAMES for name in policies)
    ):
        raise ValueError("policies must contain distinct supported policy names")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(output) if output is not None else Path("results/cmdp_v1") / timestamp
    # Refuse to overwrite any prior research run.
    output.mkdir(parents=True, exist_ok=False)
    variations = [(config.effect_strength, config.budget)]
    if suite == "full":
        variations = [(alpha, 150) for alpha in (0, 0.25, 0.5, 1)]
        variations += [(1, budget) for budget in BUDGETS if budget != 150]
    development = tuple(range(config.seed, config.seed + development_seed_count))
    evaluation = tuple(range(config.seed + 10000, config.seed + 10000 + evaluation_seed_count))
    manifest = {
        "config": asdict(config),
        "suite": suite,
        "variations": variations,
        "policies": policies,
        "development_seeds": development,
        "evaluation_seeds": evaluation,
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "wait_matrix": P_WAIT.tolist(),
        "programme_matrices": {
            str(alpha): programme_matrix(alpha).tolist() for alpha, _ in variations
        },
        "modelling_status": "synthetic assumptions; fully observed benchmark; not observed school dropout",
        "policy_tuning": "no parameter fitting or tuning on evaluation seeds",
        "source_population_sha256": hashlib.sha256(
            DEFAULT_STUDENT_DATA_PATH.read_bytes()
        ).hexdigest(),
        "source_code_sha256": {
            str(path.relative_to(Path(__file__).resolve().parents[2])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in [
                *sorted(Path(__file__).parent.glob("*.py")),
                Path(__file__).parents[1] / "main.py",
                Path(__file__).parents[1] / "utils/constants.py",
                Path(__file__).parents[1] / "utils/enums.py",
            ]
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    episodes = []
    with (
        (output / "episodes.jsonl").open("w", encoding="utf-8") as episode_file,
        (output / "sample_trajectories.jsonl").open("w", encoding="utf-8") as trajectory_file,
    ):
        for partition, seeds in (("development", development), ("evaluation", evaluation)):
            for alpha, budget in variations:
                scenario = f"effect_{alpha:g}_budget_{budget:g}"
                for seed in seeds:
                    null_trajectory = None
                    for name in policies:
                        selected = replace(config, effect_strength=alpha, budget=budget, seed=seed)
                        metrics, trajectory = run_policy(selected, name)
                        row = {
                            "scenario": scenario,
                            "partition": partition,
                            "seed": seed,
                            "policy": name,
                            **metrics,
                        }
                        episodes.append(row)
                        episode_file.write(json.dumps(row) + "\n")
                        if print_monthly and partition == "development" and seed == seeds[0]:
                            print(f"Monthly summary: {scenario}, seed {seed}, policy {name}", flush=True)
                            print(format_monthly_summary(metrics["monthly_summaries"]), flush=True)
                        if seed == seeds[0]:
                            trajectory_file.write(
                                json.dumps(
                                    {
                                        "scenario": scenario,
                                        "partition": partition,
                                        "seed": seed,
                                        "policy": name,
                                        "months": trajectory,
                                    }
                                )
                                + "\n"
                            )
                        if alpha == 0:
                            conditions = [record["conditions"] for record in trajectory]
                            if null_trajectory is not None and conditions != null_trajectory:
                                raise AssertionError(
                                    "zero-effect policies produced unequal matched trajectories"
                                )
                            null_trajectory = conditions
                print(f"Completed {partition}: {scenario} ({len(seeds)} paired seeds)", flush=True)
    summaries = summarize(episodes)
    tiny = tiny_comparison(config)
    save_reports(output, summaries, tiny, manifest)
    return output

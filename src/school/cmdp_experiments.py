"""Run paired CMDP experiments through School; CLI parsing belongs to main.py."""

from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ..utils.constants import DEFAULT_STUDENT_DATA_PATH
from .allocation_policies import DEFAULT_POLICIES, POLICY_NAMES, make_policy
from .baseline_policy import BASELINES
from .baseline_validation import validate_episode, validate_experiment_grid
from .cmdp_metrics import episode_metrics
from .cmdp_reports import format_monthly_summary, save_reports, summarize
from .cmdp_scenarios import build_environment, build_school
from .exact_tiny_mdp import ExactTinyMDP
from .fairness_audit import audit_access, group_retention
from .student_condition import StudentCondition
from .constrained_planner import ConstrainedAllocationPlanner
from .transition_model import P_WAIT, programme_matrix


BUDGETS = (0, 50, 150, 300, 500)


def run_policy(config, name, *, school=None):
    school = build_school(config) if school is None else school
    simulation = school.run_cmdp(make_policy(name, config), config=config)
    env = simulation.environment
    metrics = episode_metrics(env, simulation.initial_state, simulation.initial_cohorts)
    metrics["initial_state_hash"] = config_hash(asdict(simulation.initial_state))

    metrics["fairness_windows"] = [
        entry
        for start, frozen in simulation.window_cohorts
        for entry in audit_access(
            frozen,
            env.records,
            start_month=start,
            end_month=min(config.horizon, start + config.fairness_window - 1),
            minimum_access=config.fairness_min_access,
            small_group_threshold=config.fairness_small_group_threshold,
        )
    ]
    metrics["window_normalized_shortfall"] = sum(
        entry["normalized_shortfall"] for entry in metrics["fairness_windows"]
        if entry["normalized_shortfall"] is not None
    )
    metrics["fairness_monthly"] = simulation.fairness_monthly
    metrics["group_retention"] = group_retention(
        simulation.initial_state, env.records, config.fairness_grouping_attribute)
    trajectory = [asdict(record) for record in env.records]
    return metrics, trajectory


def config_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


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
    result["heuristic_first_action"] = [asdict(item) for item in result["heuristic_first_action"]]
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
    stage="both",
):
    """Run independent paired worlds and save results in a new destination."""
    if suite not in ("default", "full"):
        raise ValueError("suite must be default or full")
    if stage not in ("development", "both"):
        raise ValueError("stage must be development or both")
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
    output = Path(output) if output is not None else Path("results/cmdp_baselines") / timestamp
    # Refuse to overwrite any prior research run.
    output.mkdir(parents=True, exist_ok=False)
    variations = [(config.effect_strength, config.budget)]
    if suite == "full":
        variations = [(alpha, 150) for alpha in (0, 0.25, 0.5, 1)]
        variations += [(1, budget) for budget in BUDGETS if budget != 150]
    development = tuple(range(config.seed, config.seed + development_seed_count))
    evaluation = tuple(range(config.seed + 10000, config.seed + 10000 + evaluation_seed_count))
    partitions = ("development",) if stage == "development" else ("development", "evaluation")
    manifest = {
        "config": asdict(config),
        "suite": suite,
        "variations": variations,
        "policies": policies,
        "development_seeds": development,
        "evaluation_seeds": evaluation,
        "partitions": partitions,
        "planner_solver_settings": dict(ConstrainedAllocationPlanner(
            time_limit=config.planner_time_limit, failure_mode=config.planner_failure_mode).settings),
        "confidence_interval": "paired episode-level Student-t, 95%, ddof=1; pointwise",
        "student_month_convention": "enrolled after each monthly transition; excludes month zero",
        "waiting_convention": "full unsupported months survived; admission/withdrawal stop counter",
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
    (output / "experiment_config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    episodes = []
    context = {}
    with (
        (output / "episodes.jsonl").open("w", encoding="utf-8") as episode_file,
        (output / "sample_trajectories.jsonl").open("w", encoding="utf-8") as trajectory_file,
    ):
        try:
            for partition in partitions:
                seeds = development if partition == "development" else evaluation
                for alpha, budget in variations:
                    scenario = f"effect_{alpha:g}_budget_{budget:g}"
                    for seed in seeds:
                        context = dict(scenario=scenario, partition=partition, seed=seed, policy=None)
                        selected = replace(config, effect_strength=alpha, budget=budget, seed=seed)
                        # Construct the cohort and mentor setup once, then let each environment
                        # copy these same source models. Policy iteration cannot resample a world.
                        school = build_school(selected)
                        null_trajectory = None
                        initial_state_hash = None
                        for name in policies:
                            context = dict(scenario=scenario, partition=partition, seed=seed, policy=name)
                            metrics, trajectory = run_policy(selected, name, school=school)
                            validate_episode(metrics, trajectory, selected)
                            if initial_state_hash is not None and metrics["initial_state_hash"] != initial_state_hash:
                                raise ValueError("policies did not start from the identical world")
                            initial_state_hash = metrics["initial_state_hash"]
                            row = {
                                **context,
                                "config_hash": config_hash(asdict(selected)),
                                "scenario_hash": config_hash({k: v for k, v in asdict(selected).items() if k != "seed"}),
                                "budget": budget,
                                "effect_strength": alpha,
                                "student_count": selected.num_students,
                                "horizon": selected.horizon,
                                "resource_constraints_valid": True,
                                **metrics,
                            }
                            if alpha == 0 or budget == 0:
                                conditions = [record["conditions"] for record in trajectory]
                                if null_trajectory is not None and conditions != null_trajectory:
                                    raise ValueError("zero-effect/zero-budget matched trajectories differ")
                                null_trajectory = conditions
                            episodes.append(row)
                            episode_file.write(json.dumps(row) + "\n")
                            if print_monthly and partition == "development" and seed == seeds[0]:
                                print(f"Monthly summary: {scenario}, seed {seed}, policy {name}", flush=True)
                                print(format_monthly_summary(metrics["monthly_summaries"]), flush=True)
                            if seed == seeds[0]:
                                trajectory_file.write(json.dumps({**context, "months": trajectory}) + "\n")
                    print(f"Completed {partition}: {scenario} ({len(seeds)} paired seeds)", flush=True)
                if partition == "development":
                    validate_experiment_grid(episodes, manifest, partitions=("development",))
                    development_summary = summarize(episodes)
                    (output / "development_summary.json").write_text(
                        json.dumps(development_summary, indent=2), encoding="utf-8"
                    )
                    (output / "development_validation.json").write_text(json.dumps({
                        "status": "passed", "episodes": len(episodes),
                        "checks": ["complete manifest grid", "identical initial worlds", "resource ledgers",
                                   "full zero-effect and zero-budget trajectory equality"],
                        "extreme_retention_means": [
                            {"scenario": row["scenario"], "policy": row["policy"], "rate": row["mean_retention_rate"]}
                            for row in development_summary
                            if row["mean_retention_rate"] is not None and not 0.05 < row["mean_retention_rate"] < 0.99
                        ],
                    }, indent=2), encoding="utf-8")
                    episode_file.flush()
                    trajectory_file.flush()
                    print("Development validation passed; held-out evaluation is now permitted.", flush=True)
            summaries = summarize(episodes, manifest)
            tiny = tiny_comparison(config) if any(name not in BASELINES for name in policies) else None
            save_reports(output, summaries, tiny, manifest, episodes=episodes)
            (output / "COMPLETED.json").write_text(json.dumps({
                "status": "complete", "episodes": len(episodes), "partitions": partitions,
            }, indent=2), encoding="utf-8")
        except Exception as exc:
            (output / "failure.json").write_text(json.dumps({
                **context, "status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                "completed_episodes": len(episodes),
            }, indent=2), encoding="utf-8")
            raise
    return output

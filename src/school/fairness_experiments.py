"""Frozen Step 4 grids, paired episode statistics and reproducible audit exports."""

from collections import Counter, defaultdict
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import numpy as np

from .baseline_exports import write_csv
from .baseline_policy import BASELINES
from .baseline_validation import validate_episode
from .cmdp_experiments import run_policy, config_hash
from .cmdp_metrics import paired_difference
from .cmdp_scenarios import build_school
from .fairness_audit import required_access
from ..utils.constants import DEFAULT_STUDENT_DATA_PATH


FAIRNESS_TARGETS = (0., .1, .2, .3, .4)
BUDGETS = (0, 50, 150, 300, 500)
EFFECT_STRENGTHS = (0., .25, .5, 1.)


def experiment_grid(config):
    """Each tuple = budget, alpha, named policy, implemented policy, coverage target."""
    base = [(150, 1., name, name, .3) for name in (*BASELINES, "terminal_value")]
    base += [(150, 1., f"fairness_q{q:g}", "fairness", q) for q in FAIRNESS_TARGETS]
    base += [(budget, 1., name, policy, .3) for budget in BUDGETS if budget != 150
             for name, policy in (("terminal_value", "terminal_value"), ("fairness_q0.3", "fairness"))]
    base += [(150, alpha, name, policy, .3) for alpha in EFFECT_STRENGTHS if alpha != 1
             for name, policy in (("terminal_value", "terminal_value"), ("fairness_q0.3", "fairness"))]
    return tuple(base)


def mean_valid(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def summarize_episodes(episodes):
    grouped = defaultdict(list)
    references = {(e["partition"], e["seed"], e["budget"], e["effect_strength"]): e
                  for e in episodes if e["policy"] == "terminal_value"}
    for episode in episodes:
        grouped[(episode["partition"], episode["budget"], episode["effect_strength"], episode["policy"])].append(episode)
    summaries = []
    metrics = ("retention_rate", "spending", "programmes", "mean_access_rate", "mean_access_disparity",
               "normalized_shortfall", "reference_normalized_shortfall", "shortfall_students",
               "shortfall_cells", "mean_window_waiting", "max_window_waiting", "mentor_admission_utilization",
               "workload_imbalance", "solver_runtime_seconds", "projected_infeasible_months",
               "projected_vs_realized_coverage_gap", "mean_eligible_waiting_months")
    for (partition, budget, alpha, policy), runs in sorted(grouped.items()):
        runs.sort(key=lambda e: e["seed"])
        summary = {"partition": partition, "budget": budget, "effect_strength": alpha,
                   "policy": policy, "target_coverage": runs[0]["target_coverage"], "episodes": len(runs)}
        for metric in metrics:
            summary["mean_" + metric] = mean_valid(e[metric] for e in runs)
        disparities = [e["mean_access_disparity"] for e in runs if e["mean_access_disparity"] is not None]
        summary["sd_access_disparity"] = float(np.std(disparities, ddof=1)) if len(disparities) > 1 else None
        summary["sd_retention_rate"] = float(np.std([e["retention_rate"] for e in runs], ddof=1)) if len(runs) > 1 else None
        summary["p95_episode_solver_runtime_seconds"] = float(np.quantile([e["solver_runtime_seconds"] for e in runs], .95))
        reference = [references[(partition, e["seed"], budget, alpha)] for e in runs]
        for metric in ("retention_rate", "spending", "mentor_admission_utilization"):
            paired = paired_difference([e[metric] for e in runs], [e[metric] for e in reference])
            summary.update({f"paired_{metric}_{key}": value for key, value in paired.items()})
        summaries.append(summary)
    return summaries


def save_figures(output, summaries, groups):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    partition = "evaluation" if any(r["partition"] == "evaluation" for r in summaries) else "development"
    selected = [r for r in summaries if r["partition"] == partition]
    base = [r for r in selected if r["budget"] == 150 and r["effect_strength"] == 1]
    fair = sorted([r for r in base if r["policy"].startswith("fairness_")], key=lambda r: r["target_coverage"])
    figures = output / "figures"
    figures.mkdir()
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    defined = [r for r in fair if r["mean_mean_access_disparity"] is not None]
    ax.plot([r["mean_mean_access_disparity"] for r in defined], [r["mean_retention_rate"] for r in defined], "o-")
    for r in defined:
        ax.annotate(f'q={r["target_coverage"]:g}', (r["mean_mean_access_disparity"], r["mean_retention_rate"]), xytext=(4, 4), textcoords="offset points")
    ax.set(xlabel="Mean realized within-condition access gap", ylabel="Mean terminal retention rate",
           title=f"Synthetic coverage–retention trade-off ({partition})")
    fig.savefig(figures / "fairness_retention_tradeoff.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    ax.bar([r["policy"] for r in base], [r["mean_retention_rate"] for r in base])
    ax.tick_params(axis="x", labelrotation=45)
    ax.set(ylabel="Mean terminal retention rate", title="Synthetic policy comparison")
    fig.savefig(figures / "retention_by_policy.png", dpi=150)
    plt.close(fig)
    for name, field, xlabel in (("group_access_comparison", "group", "Audit group"),
                                 ("coverage_by_window", "window_start", "Window start month")):
        fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
        for policy in ("terminal_value", "fairness_q0.3"):
            rows = [r for r in groups if r["partition"] == partition and r["budget"] == 150
                    and r["effect_strength"] == 1 and r["policy"] == policy and r["access_rate"] is not None]
            keys = sorted({r[field] for r in rows})
            ax.plot([str(k) for k in keys], [mean_valid(r["access_rate"] for r in rows if r[field] == k)
                                             for k in keys], "o-", label=policy)
        ax.set(xlabel=xlabel, ylabel="Mean eligible-cell admission rate", title="Actual frozen-cohort access")
        ax.legend()
        fig.savefig(figures / (name + ".png"), dpi=150)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for policy in ("terminal_value", "fairness_q0.3"):
        rows = sorted([r for r in selected if r["effect_strength"] == 1 and r["policy"] == policy], key=lambda r: r["budget"])
        for ax, metric, ylabel in zip(axes, ("mean_normalized_shortfall", "mean_retention_rate"),
                                     ("Sum normalized coverage shortfall", "Terminal retention rate")):
            ax.plot([r["budget"] for r in rows], [r[metric] for r in rows], "o-", label=policy)
            ax.set(xlabel="Episode budget", ylabel=ylabel)
            ax.legend()
    fig.savefig(figures / "budget_vs_fairness.png", dpi=150)
    plt.close(fig)


def run_fairness_experiments(config, *, output, development_seed_count=10, evaluation_seed_count=30,
                             stage="both"):
    if stage not in ("development", "both"):
        raise ValueError("stage must be development or both")
    if not 1 <= development_seed_count <= 10 or not 1 <= evaluation_seed_count <= 30:
        raise ValueError("use 1-10 development seeds and 1-30 held-out seeds")
    if not config.fairness_enabled or not config.fairness_allow_shortfall:
        raise ValueError("the comparative grid declares enabled shortfall-aware fairness")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    grid = experiment_grid(config)
    partitions = {"development": list(range(config.seed, config.seed + development_seed_count))}
    if stage == "both":
        partitions["evaluation"] = list(range(config.seed + 10000, config.seed + 10000 + evaluation_seed_count))
    manifest = {"config": asdict(config), "grid": grid,
                "seed_partitions": partitions,
                "population_sha256": hashlib.sha256(Path(DEFAULT_STUDENT_DATA_PATH).read_bytes()).hexdigest(),
                "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))},
                "objective_order": ["minimize_sum_integer_shortfall_over_frozen_size", "maximize_projected_retention", "minimize_cost", "canonical_bits"],
                "group_weight": "1 per nonempty group-condition cell; normalized by frozen cell size",
                "projection": "announced calendar, current eligible candidates, WAIT-only future benefit; enrollment is optimistic",
                "common_audit_target": .3, "ci": "pointwise paired episode-level Student-t 95%",
                "unknown_and_empty": "reported; no cell suppression; small cells flagged"}
    # Freeze assumptions before development and held-out outcomes are observed.
    (output / "experiment_config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    episodes, monthly, groups, diagnostics, histories, workloads, retention_groups = [], [], [], [], [], [], []
    samples = []
    context = {}
    try:
        for partition, seeds in partitions.items():
            for budget, alpha in dict.fromkeys((b, a) for b, a, *_ in grid):
                settings = [r for r in grid if r[:2] == (budget, alpha)]
                for seed in seeds:
                    reference_conditions = reference_assignments = reference_hash = None
                    selected = replace(config, budget=budget, effect_strength=alpha, seed=seed)
                    school = build_school(selected)
                    for _, _, label, policy, target in settings:
                        chosen = replace(selected, fairness_min_access=target)
                        context = {"partition": partition, "seed": seed, "budget": budget,
                                   "effect_strength": alpha, "policy": label, "target_coverage": target}
                        metrics, trajectory = run_policy(chosen, policy, school=school)
                        validate_episode(metrics, trajectory, chosen)
                        if metrics["solver_failures"] or metrics["feasibility_validation_failures"]:
                            raise ValueError("solver failure or invalid allocation in comparative run")
                        conditions = [r["conditions"] for r in trajectory]
                        assignments = [r["allocation"]["assignments"] for r in trajectory]
                        if reference_hash is not None and metrics["initial_state_hash"] != reference_hash:
                            raise ValueError("paired policies have different initial worlds")
                        reference_hash = metrics["initial_state_hash"]
                        if policy == "terminal_value":
                            reference_conditions, reference_assignments = conditions, assignments
                        if label == "fairness_q0" and assignments != reference_assignments:
                            raise ValueError("q=0 differs from resource-only decisions")
                        if alpha == 0 and reference_conditions is not None and conditions != reference_conditions:
                            raise ValueError("null-effect matched exogenous trajectories differ")
                        access = metrics["fairness_windows"]
                        valid = [r for r in access if r["eligible_count"]]
                        gaps = {(r["window_start"], r["condition_at_start"]): r["access_disparity"] for r in valid}
                        starts = {(r["window_start"], r["group"], r["condition_at_start"]): r["projected_coverage"]
                                  for r in metrics["fairness_monthly"] if r["month"] == r["window_start"]}
                        final_gaps = [starts[(r["window_start"], r["group"], r["condition_at_start"])] - r["actual_covered"]
                                      for r in metrics["fairness_monthly"] if r["month"] == r["window_end"]]
                        episode = {**context, "config_hash": config_hash(asdict(chosen)),
                                   **{k: v for k, v in metrics.items() if isinstance(v, (str, int, float, bool)) or v is None},
                                   "mean_access_rate": mean_valid(r["access_rate"] for r in valid),
                                   "mean_access_disparity": mean_valid(gaps.values()),
                                   "normalized_shortfall": sum(r["normalized_shortfall"] for r in valid),
                                   "reference_normalized_shortfall": sum(max(0, required_access(.3, r["eligible_count"]) - r["unique_admissions"]) / r["eligible_count"] for r in valid),
                                   "shortfall_students": sum(r["coverage_shortfall"] for r in access),
                                   "shortfall_cells": sum(r["coverage_shortfall"] > 0 for r in access),
                                   "mean_window_waiting": mean_valid(r["mean_waiting_months"] for r in valid),
                                   "max_window_waiting": max((r["max_waiting_months"] for r in valid), default=None),
                                   "workload_imbalance": max((r["programmes"] for r in metrics["mentor_workload"]), default=0) - min((r["programmes"] for r in metrics["mentor_workload"]), default=0),
                                   "projected_infeasible_months": sum(r["allocation"]["projected_fairness_feasible"] is False for r in trajectory),
                                   "strict_infeasible_months": sum(r["allocation"]["status"] == "fairness_infeasible" for r in trajectory),
                                   "projected_vs_realized_coverage_gap": sum(final_gaps),
                                   "trajectory_sha256": config_hash(conditions), "allocation_sha256": config_hash(assignments)}
                        episodes.append(episode)
                        monthly.extend({**context, **r} for r in metrics["monthly_summaries"])
                        groups.extend({**context, **r} for r in access)
                        histories.extend({**context, **r} for r in metrics["fairness_monthly"])
                        workloads.extend({**context, **r} for r in metrics["mentor_workload"])
                        retention_groups.extend({**context, **r} for r in metrics["group_retention"])
                        for record in trajectory:
                            diagnostic = {k: v for k, v in record["allocation"].items() if k != "assignments"}
                            diagnostics.append({**context, "month": record["month"],
                                                **{k: json.dumps(v, sort_keys=True) if isinstance(v, (tuple, list, dict)) else v for k, v in diagnostic.items()}})
                        if seed == seeds[0]:
                            samples.append({**context, "months": trajectory})
                print(f"Completed {partition}: budget={budget}, alpha={alpha:g} ({len(seeds)} paired seeds)", flush=True)
            expected = {(partition, seed, b, a, label) for seed in seeds for b, a, label, *_ in grid}
            actual = Counter((r["partition"], r["seed"], r["budget"], r["effect_strength"], r["policy"]) for r in episodes if r["partition"] == partition)
            if set(actual) != expected or any(v != 1 for v in actual.values()):
                raise ValueError("missing, duplicate or unexpected fairness episodes")
            (output / (partition + "_validation.json")).write_text(json.dumps({"status": "passed", "episodes": len(expected),
                "checks": ["complete frozen grid", "independent operational validation", "identical paired initial worlds",
                           "zero-target exact allocation equality", "null-effect full trajectory equality"]}, indent=2))
            print(f"{partition.capitalize()} validation passed.", flush=True)
        summaries = summarize_episodes(episodes)
        tables = {"episode_results": episodes, "monthly_results": monthly, "group_access": groups,
                  "fairness_shortfalls": groups, "fairness_targets": groups,
                  "fairness_retention_tradeoff": [r for r in summaries if r["budget"] == 150 and r["effect_strength"] == 1],
                  "budget_sensitivity": [r for r in summaries if r["effect_strength"] == 1 and r["policy"] in ("terminal_value", "fairness_q0.3")],
                  "effect_sensitivity": [r for r in summaries if r["budget"] == 150 and r["policy"] in ("terminal_value", "fairness_q0.3")],
                  "solver_diagnostics": diagnostics, "window_history": histories,
                  "mentor_workload": workloads, "group_retention": retention_groups, "policy_comparison": summaries}
        for name, rows in tables.items():
            write_csv(output / (name + ".csv"), rows)
        (output / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
        with (output / "sample_trajectories.jsonl").open("w") as target:
            for sample in samples:
                target.write(json.dumps(sample) + "\n")
        save_figures(output, summaries, groups)
        (output / "COMPLETED.json").write_text(json.dumps({"status": "complete", "episodes": len(episodes),
                                                          "partitions": partitions}, indent=2) + "\n")
    except Exception as exc:
        (output / "failure.json").write_text(json.dumps({**context, "error": repr(exc), "completed_episodes": len(episodes)}, indent=2))
        raise
    return output

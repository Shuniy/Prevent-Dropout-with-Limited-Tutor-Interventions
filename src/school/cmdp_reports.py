"""Summarize and export paired school simulation results; no allocation logic."""

from collections import Counter
import json

import numpy as np

from .cmdp_metrics import paired_difference


def format_monthly_summary(months):
    """Readable per-world output, requested explicitly to keep large sweeps quiet."""
    lines = [
        "Month | Stable | Vulnerable | Disengaged | Withdrawn | New withdrawals | "
        "Enrolled | Programmes | Appointments | Spend | Cumulative spend | Budget left | "
        "Eligible | Mean eligible wait | Mentor usage (programmes/capacity, appointments/slots)",
    ]
    for row in months:
        mentors = "; ".join(
            f"{mentor['mentor_id']}: {mentor['programmes']}/{mentor['admission_capacity']}, "
            f"{mentor['appointments']}/{mentor['appointment_capacity']}"
            for mentor in row["mentor_utilization"]
        )
        lines.append(
            f"{row['month']} | {row['stable']} | {row['vulnerable']} | "
            f"{row['disengaged']} | {row['withdrawn']} | {row['newly_withdrawn']} | "
            f"{row['enrolled']} | {row['programmes_started']} | "
            f"{row['appointments_delivered']} | {row['spending']:.2f} | "
            f"{row['cumulative_spending']:.2f} | {row['remaining_budget']:.2f} | "
            f"{row['eligible_students']} | {row['mean_eligible_waiting_months']:.2f} | {mentors}"
        )
    final = months[-1]
    retention = final["retention_rate"]
    retention_text = f"{retention:.2%}" if retention is not None else "n/a"
    lines.append(
        f"Terminal enrollment: {final['enrolled']}; retention: {retention_text}; "
        f"total spending: {final['cumulative_spending']:.2f}"
    )
    return "\n".join(lines)


def summarize(episodes):
    """Pair by world seed, not by students sharing capacity within a world."""
    summaries = []
    keys = sorted({(item["scenario"], item["partition"]) for item in episodes})
    for scenario, partition in keys:
        subset = [
            item
            for item in episodes
            if (item["scenario"], item["partition"]) == (scenario, partition)
        ]
        names = sorted({item["policy"] for item in subset})
        by_policy = {
            name: {item["seed"]: item for item in subset if item["policy"] == name}
            for name in names
        }
        seeds = sorted(by_policy[names[0]])
        if any(sorted(by_policy[name]) != seeds for name in names):
            raise ValueError("policy comparison is missing paired world seeds")
        for name in names:
            runs = [by_policy[name][seed] for seed in seeds]
            values = [run["terminal_enrolled"] for run in runs]
            scalar_fields = (
                "terminal_enrolled",
                "retention_rate",
                "enrolled_student_months",
                "spending",
                "budget_utilization",
                "programmes",
                "appointments",
                "mean_waiting_months",
                "waiting_p50",
                "waiting_p90",
                "solver_runtime_seconds",
                "solver_failures",
                "window_normalized_shortfall",
            )
            summary = {
                "scenario": scenario,
                "partition": partition,
                "policy": name,
                "episodes": len(runs),
            }
            for field in scalar_fields:
                known = [run[field] for run in runs if run[field] is not None]
                summary["mean_" + field] = float(np.mean(known)) if known else None
            summary["paired_differences"] = {
                reference: paired_difference(
                    values, [by_policy[reference][seed]["terminal_enrolled"] for seed in seeds]
                )
                for reference in names
            }
            statuses = Counter()
            for run in runs:
                statuses.update(run["solver_statuses"])
            summary["solver_statuses"] = dict(statuses)
            summary["max_solver_optimality_gap"] = max(
                (gap for run in runs for gap in run["solver_optimality_gaps"]),
                default=None,
            )
            summary["mean_monthly_conditions"] = [
                {
                    key: float(np.mean([run["monthly_conditions"][index][key] for run in runs]))
                    for key in runs[0]["monthly_conditions"][index]
                }
                for index in range(len(runs[0]["monthly_conditions"]))
            ]
            summary["mean_mentor_workload"] = [
                {
                    "mentor_id": mentor["mentor_id"],
                    **{
                        key: float(np.mean([run["mentor_workload"][index][key] for run in runs]))
                        for key in mentor
                        if key != "mentor_id"
                    },
                }
                for index, mentor in enumerate(runs[0]["mentor_workload"])
            ]
            # Initial-cohort denominators are identical across paired episodes.
            summary["mean_group_access"] = [
                {
                    **group,
                    **{
                        key: float(np.mean([run["group_access"][index][key] for run in runs]))
                        for key in (
                            "unique_offers",
                            "access_rate",
                            "completed_programme_rate",
                            "mean_waiting_months",
                            "terminal_retention_rate",
                        )
                    },
                }
                for index, group in enumerate(runs[0]["group_access"])
            ]
            summaries.append(summary)
    return summaries


def report_markdown(summaries, tiny, manifest):
    lines = [
        "# CMDP v1 simulation results",
        "",
        "All outcomes and programme effects below are synthetic simulation results. "
        "They are not observed school dropout or measured causal effects.",
        "",
        "The planner is a receding-horizon terminal-value allocation heuristic. "
        "MILP optimality refers only to its current monthly assignment objective.",
        "",
        f"Development seeds: {manifest['development_seeds']}. "
        f"Held-out seeds: {manifest['evaluation_seeds']}. No tuning uses held-out outcomes.",
        "",
        "Paired confidence intervals use independent episode seeds as repetitions. "
        "Intervals are pointwise, without multiple-comparison correction.",
        "",
        "| Partition | Scenario | Policy | Mean enrolled | Retention | Difference vs wait (95% CI) | Spend | Programmes |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in summaries:
        difference = row["paired_differences"].get("wait")
        text = "n/a"
        if difference:
            text = f"{difference['mean']:.3f}"
            if difference["ci95_low"] is not None:
                text += f" [{difference['ci95_low']:.3f}, {difference['ci95_high']:.3f}]"
        rate = row["mean_retention_rate"]
        rate_text = f"{rate:.3%}" if rate is not None else "n/a"
        lines.append(
            f"| {row['partition']} | {row['scenario']} | {row['policy']} | "
            f"{row['mean_terminal_enrolled']:.3f} | {rate_text} | {text} | "
            f"{row['mean_spending']:.2f} | {row['mean_programmes']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Exact reference",
            "",
            tiny["scenario"],
            "",
            f"Exact expected terminal enrollment: {tiny['exact_expected_terminal_enrollment']:.9f}. "
            f"Heuristic: {tiny['heuristic_expected_terminal_enrollment']:.9f}. "
            f"Gap: {tiny['objective_gap']:.9f}.",
            "",
            f"Exact first recipients: {tiny['exact_first_student_ids']}; "
            f"heuristic first recipients: {tiny['heuristic_first_student_ids']}.",
            "",
            "## Solver and auditing",
            "",
            "| Partition | Scenario | Policy | Mean solver seconds/episode | Failures | Maximum monthly gap | Window shortfall |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summaries:
        if row["policy"] in ("terminal_value", "fairness"):
            lines.append(
                f"| {row['partition']} | {row['scenario']} | {row['policy']} | "
                f"{row['mean_solver_runtime_seconds']:.5f} | {row['mean_solver_failures']:.2f} | "
                f"{row['max_solver_optimality_gap']} | {row['mean_window_normalized_shortfall']:.3f} |"
            )
    lines.extend(
        [
            "",
            "Machine-readable summaries contain comparisons against every baseline, monthly "
            "condition counts, workload, and access stratified by initial condition and fixed need. "
            "Episode JSONL includes month-zero and monthly summaries with resource usage and "
            "waiting among enrolled, unsupported students, plus waiting distributions, "
            "withdrawal timing, window audits, bounds "
            "and statuses. Access is descriptive; equal allocation across unequal needs is not a fairness conclusion.",
            "",
            "Window shortfall sums max(0, q*N - offers)/N across nonempty comparable-need "
            "groups and windows. Denominators are frozen at window start, including later withdrawals. "
            "Sex and disadvantage-proxy groups overlap and are audited separately.",
            "",
            "Fairness mode, if present, eagerly minimizes current residual window shortfall before "
            "maximizing retention benefit. It remembers prior offers but does not optimize a stochastic "
            "multi-month fairness schedule or guarantee future coverage. Actual end-window shortfalls "
            "remain explicit. Resource constraints stay hard.",
            "",
            "![Mean monthly simulated conditions](monthly_conditions.png)",
            "",
            "![Paired retention differences](paired_retention.png)",
            "",
            "Limitations: fully observed benchmark, one programme per episode, fixed initial need, "
            "identical assumed effects by support type, no peer effects, no uptake/refund model, "
            "and a deterministic enrolled prefix of the existing synthetic population. "
            "Held-out seeds are independent transition worlds, not held-out source students. "
            "The reported confidence intervals exclude uncertainty in the assumed transition model.",
            "",
        ]
    )
    return "\n".join(lines)


def save_plots(summaries, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    selected = [
        row
        for row in summaries
        if row["partition"] == "evaluation" and row["scenario"] == "effect_1_budget_150"
    ]
    if not selected:
        selected = [
            row
            for row in summaries
            if row["partition"] == summaries[0]["partition"]
            and row["scenario"] == summaries[0]["scenario"]
        ]
    figure, axes = plt.subplots(1, 4, figsize=(16, 4), constrained_layout=True)
    for axis, condition in zip(axes, ("stable", "vulnerable", "disengaged", "withdrawn")):
        for row in selected:
            monthly = row["mean_monthly_conditions"]
            axis.plot(
                [item["month"] for item in monthly],
                [item[condition] for item in monthly],
                label=row["policy"],
            )
        axis.set(title=f"Simulated {condition}", xlabel="Month", ylabel="Mean students")
    axes[-1].legend(fontsize=8)
    figure.savefig(output / "monthly_conditions.png", dpi=150)
    plt.close(figure)
    figure, axis = plt.subplots(figsize=(9, 4), constrained_layout=True)
    for index, row in enumerate(selected):
        difference = row["paired_differences"].get("wait")
        if difference is None:
            continue
        error = 0 if difference["ci95_low"] is None else difference["mean"] - difference["ci95_low"]
        axis.errorbar(difference["mean"], index, xerr=error, fmt="o", capsize=4)
    axis.set(
        yticks=range(len(selected)),
        yticklabels=[row["policy"] for row in selected],
        xlabel="Paired difference in terminal enrolled students vs wait (95% CI)",
        title="Synthetic simulation results",
    )
    axis.axvline(0, color="grey", linewidth=1)
    figure.savefig(output / "paired_retention.png", dpi=150)
    plt.close(figure)


def save_reports(output, summaries, tiny, manifest):
    (output / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    (output / "tiny_exact.json").write_text(json.dumps(tiny, indent=2), encoding="utf-8")
    (output / "report.md").write_text(report_markdown(summaries, tiny, manifest), encoding="utf-8")
    save_plots(summaries, output)

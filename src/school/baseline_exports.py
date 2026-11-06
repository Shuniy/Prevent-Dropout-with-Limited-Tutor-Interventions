"""Portable baseline tables and figures derived only from saved episode metrics."""

import csv
import json


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


def summary_table(summaries):
    rows = []
    for summary in summaries:
        row = {key: value for key, value in summary.items() if not isinstance(value, (list, dict))}
        for prefix, key in (("difference_vs_wait", "paired_differences"),
                            ("difference_pp_vs_wait", "paired_percentage_point_differences")):
            for field, value in summary[key].get("wait", {}).items():
                row[prefix + "_" + field] = value
        rows.append(row)
    return rows


def save_tables(output, episodes, summaries):
    identities = ("scenario", "partition", "seed", "policy",
                  "config_hash", "scenario_hash", "budget", "effect_strength", "student_count", "horizon")
    write_csv(output / "episode_results.csv", (
        {key: value for key, value in episode.items() if not isinstance(value, (list, dict))}
        for episode in episodes
    ))
    write_csv(output / "monthly_results.csv", (
        {**{key: episode[key] for key in identities}, **month}
        for episode in episodes for month in episode["monthly_summaries"]
    ))
    write_csv(output / "access_audit.csv", (
        {**{key: episode[key] for key in identities}, **group}
        for episode in episodes for group in episode["group_access"]
    ))
    rows = summary_table(summaries)
    write_csv(output / "policy_comparison.csv", rows)
    write_csv(output / "budget_sensitivity.csv", (row for row in rows if row["effect_strength"] == 1))
    write_csv(output / "effect_sensitivity.csv", (row for row in rows if row["budget"] == 150))


def baseline_report(summaries, manifest):
    lines = [
        "# Baseline allocation experiments", "",
        "Synthetic, fully observed benchmark. Retention is measured after the final monthly transition; "
        "the denominator is the initially enrolled cohort. These are not measured mentoring effects.", "",
        f"Development seeds: {manifest['development_seeds']}. Held-out seeds: {manifest['evaluation_seeds']}.",
        "Development resource, completeness and null-effect checks must pass before held-out evaluation. "
        "Policies have no fitted parameters and are not tuned using held-out outcomes.", "",
        "95% intervals use paired episode-level Student-t differences (sample SD, n−1 degrees of freedom). "
        "Episodes are independent worlds; students sharing resources are not independent repetitions. "
        "Intervals describe Monte Carlo variability under synthetic assumptions and exclude model uncertainty.", "",
        "| Partition | Scenario | Policy | Retained mean (SD) | Retention | Difference vs WAIT [95% CI], students | Difference, pp | Programmes | Spend |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in summaries:
        difference = row["paired_differences"].get("wait")
        pp = row["paired_percentage_point_differences"].get("wait")
        text = "n/a"
        if difference:
            text = f"{difference['mean']:.3f}"
            if difference["ci95_low"] is not None:
                text += f" [{difference['ci95_low']:.3f}, {difference['ci95_high']:.3f}]"
        sd = f"{row['sd_terminal_enrolled']:.3f}" if row['sd_terminal_enrolled'] is not None else "n/a"
        rate = f"{row['mean_retention_rate']:.3%}" if row['mean_retention_rate'] is not None else "n/a"
        pp_text = f"{pp['mean']:.3f}" if pp else "n/a"
        lines.append(
            f"| {row['partition']} | {row['scenario']} | {row['policy']} | "
            f"{row['mean_terminal_enrolled']:.3f} ({sd}) | {rate} | {text} | {pp_text} | "
            f"{row['mean_programmes']:.2f} | {row['mean_spending']:.2f} |"
        )
    lines += ["", "## Policies and limitations", "",
              "WAIT is usual educational support without additional mentoring. Random shuffles eligible "
              "student IDs with an independent seeded generator; it does not sample joint allocations uniformly. "
              "Severity ranks disengaged, vulnerable, stable, without estimating causal benefit. Need priority "
              "uses the repository's fixed initial maximum shared-rule need severity. Longest waiting ranks full "
              "unsupported months survived. Deterministic ties use student ID, then cheaper mentor and mentor ID.", "",
              "All policies use one priority-preserving greedy matcher. A flexible student can consume a "
              "specialist's slot before a restricted student; this is neither maximum-cardinality nor globally "
              "optimal matching. All unserved survivors tie on waiting in the default closed cohort.", "",
              "Eligible waiting means enrolled, unsupported students; empty eligible sets report zero. "
              "Admission and withdrawal stop waiting. Recipient waiting and cost per supported student are "
              "null when no programme is assigned. Episode-wide waiting also includes censored students. "
              "Enrolled student-months sum post-transition enrollment in months 1–T. Access audits use frozen "
              "initial eligible groups stratified by condition and fixed support type. The disadvantage field "
              "is a proxy, not verified poverty. No protected attributes are inferred and no fairness "
              "constraint is imposed.", "",
              "The cohort is a deterministic enrolled prefix of the synthetic source population. Held-out "
              "seeds vary transition worlds, not source students. Effects are assumed identical by support type; "
              "there are no peer effects, uptake/refunds, repeated programmes or learned observations.", "",
              "## Artifacts", "",
              "CSV files contain episode, monthly, policy, budget, effect and access results. JSONL retains "
              "complete episode metrics and representative student trajectories. The manifest records seeds, "
              "matrices and source hashes; existing run directories are never overwritten.", ""]
    for name in ("retention_comparison", "retention_trajectories", "cumulative_withdrawals",
                 "cumulative_spending", "monthly_programmes", "programme_utilization",
                 "budget_sensitivity", "effect_sensitivity"):
        lines += [f"![{name.replace('_', ' ')}](figures/{name}.png)", ""]
    return "\n".join(lines)


def save_baseline_plots(summaries, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = output / "figures"
    figures.mkdir()
    partition = "evaluation" if any(row["partition"] == "evaluation" for row in summaries) else "development"
    rows = [row for row in summaries if row["partition"] == partition]
    scenario = next((row["scenario"] for row in rows if row["scenario"] == "effect_1_budget_150"), rows[0]["scenario"])
    default = [row for row in rows if row["scenario"] == scenario]

    def finish(figure, name):
        figure.savefig(figures / (name + ".png"), dpi=150)
        plt.close(figure)

    for name, field, ylabel in (
        ("retention_trajectories", "enrolled", "Mean enrolled students"),
        ("cumulative_withdrawals", "withdrawn", "Mean cumulative withdrawals"),
        ("cumulative_spending", "cumulative_spending", "Mean cumulative synthetic spending"),
        ("monthly_programmes", "programmes_started", "Mean programmes started"),
    ):
        figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
        for row in default:
            months = row["mean_monthly_summaries"]
            axis.plot([month["month"] for month in months], [month[field] for month in months], label=row["policy"])
        axis.set(xlabel="Month", ylabel=ylabel, title=f"Synthetic benchmark — {partition}")
        axis.legend(fontsize=8)
        finish(figure, name)
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    axis.bar([row["policy"] for row in default], [row["mean_terminal_enrolled"] for row in default])
    axis.set(ylabel="Mean terminal enrolled students", title=f"Synthetic retention — {partition}")
    axis.tick_params(axis="x", labelrotation=20)
    finish(figure, "retention_comparison")
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for axis, field, ylabel in zip(axes, ("mean_programmes", "mean_appointment_slot_utilization"),
                                 ("Mean programmes", "Mean appointment-slot utilization")):
        axis.bar([row["policy"] for row in default], [row[field] for row in default])
        axis.set(ylabel=ylabel)
        axis.tick_params(axis="x", labelrotation=30)
    finish(figure, "programme_utilization")
    for name, fixed, fixed_value, varying, xlabel in (
        ("budget_sensitivity", "effect_strength", 1, "budget", "Episode budget (synthetic units)"),
        ("effect_sensitivity", "budget", 150, "effect_strength", "Assumed intervention strength"),
    ):
        figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
        for policy in sorted({row["policy"] for row in rows}):
            points = sorted((row for row in rows if row["policy"] == policy and row[fixed] == fixed_value),
                            key=lambda row: row[varying])
            axis.plot([row[varying] for row in points], [row["mean_terminal_enrolled"] for row in points],
                      marker="o", label=policy)
        axis.set(xlabel=xlabel, ylabel="Mean terminal enrolled students", title=f"Synthetic sensitivity — {partition}")
        axis.legend(fontsize=8)
        finish(figure, name)

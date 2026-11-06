"""Step 3 diagnostics, computed benefit tables, tiny comparisons and figures."""

from dataclasses import asdict, replace
import json

from .baseline_exports import write_csv
from .cmdp_scenarios import build_environment
from .exact_tiny_mdp import ExactTinyMDP
from .retention_value import expected_terminal_retention, estimate_incremental_benefit
from .scenario_config import ScenarioConfig
from .student_condition import STATES, StudentCondition
from .transition_model import P_WAIT, programme_matrix


def benefit_rows(strengths=(0, 0.25, 0.5, 1)):
    return [
        {"condition": condition.value, "months_remaining": horizon,
         "effect_strength": alpha,
         "wait_terminal_retention": expected_terminal_retention(condition, horizon, P_WAIT),
         "incremental_benefit": estimate_incremental_benefit(
             condition, horizon, P_WAIT, programme_matrix(alpha))}
        for alpha in strengths for condition in STATES for horizon in range(1, 13)
    ]


def tiny_comparisons():
    """Vary budgets, horizons, conditions, costs and skill compatibility.

    Both policy values and spending integrate all future transition outcomes;
    these comparisons do not use Monte Carlo trajectories.
    """
    stable, vulnerable, disengaged = STATES[:3]
    cases = (
        ("reserve_budget", (stable, stable), 3, 5, 1),
        ("zero_budget", (vulnerable, disengaged), 2, 0, 1),
        ("mixed_conditions", (vulnerable, disengaged), 2, 5, 1),
        ("heterogeneous_mentors", (stable, disengaged), 2, 10, 2),
        ("last_month", (stable, vulnerable, disengaged), 1, 10, 2),
    )
    rows = []
    for name, conditions, horizon, budget, mentor_count in cases:
        config = ScenarioConfig(num_students=len(conditions), num_mentors=mentor_count,
                                horizon=horizon, budget=budget, monthly_admissions=1,
                                monthly_appointments=5)
        state = build_environment(config).observe()
        students = tuple(replace(student, condition=condition)
                         for student, condition in zip(state.students, conditions))
        mentors = state.mentors
        if name == "heterogeneous_mentors":
            # The cheap specialist can serve only the first student's support.
            mentors = (replace(mentors[0], cost_per_appointment=2),
                       replace(mentors[1], cost_per_appointment=1,
                               support_types=(students[0].support_type,),
                               compatible_student_ids=(students[0].student_id,)))
        state = replace(state, students=students, mentors=mentors)
        result = ExactTinyMDP(state).compare()
        rows.append({
            "scenario": name, "student_count": len(students), "mentor_count": mentor_count,
            "horizon": horizon, "budget": budget,
            "initial_conditions": [condition.value for condition in conditions],
            **{key: ([asdict(item) for item in value] if key.endswith("_action") else value)
               for key, value in result.items()},
        })
    return rows


def save_planner_artifacts(output, episodes, summaries, manifest):
    benefits = benefit_rows()
    write_csv(output / "benefit_by_condition.csv", benefits)
    identities = ("scenario", "partition", "seed", "policy", "config_hash")
    diagnostics = [
        {**{key: episode[key] for key in identities}, **record}
        for episode in episodes if episode["policy"] == "terminal_value"
        for record in episode["solver_diagnostics"]
    ]
    write_csv(output / "solver_diagnostics.csv", diagnostics)
    tiny = tiny_comparisons()
    write_csv(output / "tiny_exact_comparison.csv", tiny)
    (output / "tiny_exact_comparison.json").write_text(json.dumps(tiny, indent=2) + "\n")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = output / "figures"
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    for condition in STATES:
        points = [row for row in benefits if row["condition"] == condition.value
                  and row["effect_strength"] == 1]
        axis.plot([row["months_remaining"] for row in points],
                  [row["incremental_benefit"] for row in points], label=condition.value)
    axis.set(xlabel="Monthly transitions remaining", ylabel="Incremental terminal retention",
             title="Synthetic programme benefit under WAIT continuation")
    axis.legend()
    figure.savefig(figures / "benefit_by_horizon.png", dpi=150)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    axis.hist([row["runtime_seconds"] for row in diagnostics], bins=30)
    axis.set(xlabel="Monthly planner runtime (seconds)", ylabel="Decision months",
             title="Terminal-retention planner runtime, all scenarios and seeds")
    figure.savefig(figures / "solver_runtime.png", dpi=150)
    plt.close(figure)

    selected = [row for row in summaries if row["partition"] == "evaluation"
                and row["scenario"] == "effect_1_budget_150"]
    if not selected:
        selected = [row for row in summaries if row["partition"] == summaries[0]["partition"]
                    and row["scenario"] == summaries[0]["scenario"]]
    figure, axis = plt.subplots(figsize=(9, 4), constrained_layout=True)
    axis.bar([row["policy"] for row in selected],
             [row["mean_terminal_enrolled"] for row in selected])
    axis.set(ylabel="Mean terminal enrolled students", title="Synthetic retention comparison")
    axis.tick_params(axis="x", labelrotation=20)
    figure.savefig(figures / "terminal_retention.png", dpi=150)
    plt.close(figure)

    with (output / "report.md").open("a", encoding="utf-8") as report:
        report.write("\n## Step 3 validation artifacts\n\n"
                     "[Benefit table](benefit_by_condition.csv), "
                     "[monthly solver diagnostics](solver_diagnostics.csv), and "
                     "[exact policy comparisons](tiny_exact_comparison.csv). "
                     "Exact comparisons integrate all next-state probabilities. "
                     "Monthly MILP optimality does not imply full-horizon optimality.\n\n"
                     "![Benefit by horizon](figures/benefit_by_horizon.png)\n\n"
                     "![Monthly solver runtime](figures/solver_runtime.png)\n")

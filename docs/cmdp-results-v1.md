# Executed CMDP v1 simulation results

## Waiting-time correction and monthly-summary verification

The follow-up implementation excludes the withdrawal month from student and
group-audit waiting times. Every episode now saves complete month-zero through
month-twelve `monthly_summaries`; `--print-monthly` optionally prints the first
development world for each policy/scenario, including its terminal result.
Existing interfaces, keyed draws and the terminal-only objective are retained.

Executed with the existing `.venv`: **107 tests passed**. A fresh full sweep
completed **2,240 episodes with zero solver fallbacks**. Independent output checks
validated all 29,120 monthly summaries, current source hashes and 112 saved
trajectories. Retention, condition counts, resource usage and solver diagnostics
matched `full_003` except for runtime; saved trajectories also matched conditions
and assignments. Waiting metrics intentionally changed, and new summary fields
were added. Historical outputs below retain their original waiting convention.

The printed WAIT-only demonstration (seed 42) started with 80 stable and 20
vulnerable students, printed months 0–12, and finished with 71 enrolled, 29 withdrawn,
71% retention, zero spending and 150 budget units remaining.

Artifacts: [full report](../results/cmdp_v1/waiting_summary_fix_20261105/report.md),
[independent checks](../results/cmdp_v1/waiting_summary_fix_20261105/verification.json),
[printed WAIT-only run](../results/cmdp_v1/waiting_summary_smoke_20261105/cli_output.txt).
See [implementation and runnable commands](cmdp-implementation.md) for output semantics.

## School integration verification

The implementation now lives directly in `src/school`, with `School.run_cmdp(policy)`
and the shared `main.py` entry point. The historical experiment artifacts below
are preserved; their manifests describe the source layout used at execution time.

After integration, **107 tests passed**, including 39 CMDP tests. Both script and
module CLI invocation forms generated real reports without an LLM. A new default
comparison ran all seven policies across 10 development and 30 held-out seeds:
**280 episodes**. Every non-timing episode metric exactly matched the corresponding
pre-refactor result, including enrollment, monthly conditions, allocations' aggregate
resources, group audits, solver statuses and bounds. The new manifest's source hashes
were independently checked against the current school and main files.

See the [school integration report](../results/cmdp_v1/school_integration_001/report.md)
and [current-layout manifest](../results/cmdp_v1/school_integration_001/manifest.json).

## Original sensitivity experiments

Executed on 5 November 2026 using the existing `.venv`: Python 3.14.8, NumPy 2.3.5 and SciPy 1.18.1. The project declares Python 3.12–3.13; neither was available for a supported-interpreter rerun.

All numbers below are synthetic simulation results. They do not measure observed school dropout or real intervention effectiveness.

Final run: [`results/cmdp_v1/full_003/report.md`](../results/cmdp_v1/full_003/report.md). 2240 episodes: eight unique effect/budget scenarios, seven policies, ten development seeds (42–51), and thirty independent held-out world seeds (10042–10071). Each episode contains 100 initially enrolled students and twelve monthly transitions. The same fixed synthetic cohort is used throughout. No policy parameters were fitted or tuned from evaluation outcomes.

## Held-out default scenario

Budget 150 synthetic units; effect strength 1. Mean terminal enrollment is out of 100, so its numerical value also gives the retention percentage. Paired 95% intervals use world-level Student t intervals, without multiplicity correction.

| Policy | Mean terminal enrolled | Difference vs wait, 95% CI | Mean programmes | Mean spend |
| --- | ---: | --- | ---: | ---: |
| fairness | 72.367 | 1.200 [0.841, 1.559] | 30.00 | 150.00 |
| longest_waiting | 71.800 | 0.633 [0.348, 0.919] | 30.00 | 150.00 |
| need_priority | 71.700 | 0.533 [0.299, 0.768] | 30.00 | 150.00 |
| random | 71.700 | 0.533 [0.279, 0.788] | 30.00 | 150.00 |
| severity | 72.700 | 1.533 [1.197, 1.869] | 30.00 | 150.00 |
| terminal_value | 72.633 | 1.467 [1.117, 1.817] | 30.00 | 150.00 |
| wait | 71.167 | 0.000 [0.000, 0.000] | 0.00 | 0.00 |

The terminal-value heuristic differs from severity-first by -0.067 enrolled students (95% CI [-0.161, 0.028]); this run does not establish superiority over that baseline.

## Sensitivity and budget sweep

| Effect strength | Budget | Planner mean terminal enrolled | Difference vs wait, 95% CI |
| ---: | ---: | ---: | --- |
| 0.25 | 150 | 71.467 | 0.300 [0.100, 0.500] |
| 0.5 | 150 | 71.900 | 0.733 [0.381, 1.086] |
| 0 | 150 | 71.167 | 0.000 [0.000, 0.000] |
| 1 | 0 | 71.167 | 0.000 [0.000, 0.000] |
| 1 | 150 | 72.633 | 1.467 [1.117, 1.817] |
| 1 | 300 | 73.300 | 2.133 [1.656, 2.611] |
| 1 | 50 | 71.700 | 0.533 [0.261, 0.806] |
| 1 | 500 | 74.133 | 2.967 [2.391, 3.543] |

In every zero-effect world, the experiment runner checked equality of the complete student-condition trajectory across all seven policies. Zero-budget scenarios also matched wait-only.

## Mathematical reference and diagnostics

Two initially stable students, one mentor, three months, and one funded programme: exact expected terminal enrollment 1.953501435; heuristic 1.949161250; gap 0.004340185. The exact first action waits; the heuristic immediately funds one student. The exact recursion evaluated 144 states. No future draws enter this comparison.

All 2240 final-run episodes completed with 0 solver fallbacks. Resource-only MILPs reported zero monthly optimality gaps; fairness retention MILPs reported relative gaps no larger than 0.000000300, within solver numerical tolerances. Mean default held-out solver time per episode was 0.00911 seconds for terminal-value allocation and 0.03561 seconds for fairness allocation. These bounds concern the monthly objective only, not optimality of the full cohort CMDP.

Prior diagnostic runs (`milestone_1`, `full_001`, `full_002`) are preserved. They exposed sub-micro-unit solver residuals, including tiny negative binary values. Consistent 1e-6 numerical checks plus independent validation of rounded allocations corrected two conservative fairness-stage fallbacks. A regression test covers the issue. The final rerun used the same policy/effect parameters; this was a solver-validation fix, not performance tuning.

Fairness reporting freezes comparable-need cohorts for four-month windows and counts unique appropriate offers, even when students later withdraw. The optional planner eagerly reduces normalized residual coverage shortfall before retention benefit. Actual shortfalls remain in the output; budget exhaustion does not erase them. It does not optimize or guarantee a stochastic multi-month fairness schedule.

## Validation and deliverables

- `python -m unittest discover -s tests`: **102 passed**, including 34 CMDP tests; no live model required.
- Original allocation CLI and `src.basic_examples.cmdp` execution: passed.
- Black formatting check on all new Python files: passed; Git whitespace check: passed.
- Existing source data, LLM workflow and unrelated notebook/results edits were preserved.
- No known failing tests remain. Runtime verification on the project-declared Python versions remains unperformed.
- Milestone 1 is complete. Milestone 2 auditing and the optional window-aware soft coverage mode are implemented and independently tested; globally optimized multi-month fairness scheduling remains deferred. Milestone 3 observation contracts are implemented and tested; LLM-driven closed-loop state estimation remains deferred.

Artifacts: [full comparison report](../results/cmdp_v1/full_003/report.md), [all baseline differences and metrics](../results/cmdp_v1/full_003/summary.json), [seed/dependency/matrix/hash manifest](../results/cmdp_v1/full_003/manifest.json), [exact reference](../results/cmdp_v1/full_003/tiny_exact.json). Full episode metrics and representative trajectories are saved alongside these files. Results directories follow the repository's existing Git ignore rule.

![Paired terminal retention](../results/cmdp_v1/full_003/paired_retention.png)

![Monthly condition counts](../results/cmdp_v1/full_003/monthly_conditions.png)

For the module map, exact objective and constraint formulae, assumptions register, limitations and executable commands, see [CMDP implementation](cmdp-implementation.md).

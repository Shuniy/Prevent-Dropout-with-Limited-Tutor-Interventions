# Executed Step 3 results — 5 November 2026

The constrained terminal-retention planner and its validation experiments are
implemented. This report records actual executions; prior Step 1 and Step 2
artifacts remain available. All outcomes are synthetic simulation results.

## Executed commands

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m src.main \
  --config configs/cmdp_planner_v1.toml \
  --policies wait random severity need_priority longest_waiting terminal_value \
  --suite full --output results/cmdp_planner_v1/step3_20261105

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/verify_cmdp_planner.py \
  results/cmdp_planner_v1/step3_20261105 --write
```

The full experiment completed **1,920 episodes**: eight scenarios, six policies,
ten development seeds (42–51) and thirty held-out seeds (10042–10071). Every
episode has 100 initially enrolled students and twelve transitions. Development
resource/completeness/null-effect validation passed before held-out execution.
No parameters were fitted or tuned on held-out results.

The final full test suite passed **139 tests in 38.855 seconds**. New regression
coverage verifies cost minimization, input-order invariance, exact decimal
accounting, all conditions/horizons/effect strengths, adverse and zero effects,
current-condition replanning, solver failures and refinement limits, empty
feasible actions, manual two-month Bellman values, policy-order reproducibility,
and generated artifacts. Focused editor diagnostics reported no errors in the
planner, monetary helper, value estimator, exporter, acceptance tests or verifier.

The independent saved-output audit passed **24,960 monthly summaries**, recomputed
**576 paired confidence intervals** and **192 benefit values**, checked **3,840
planner decision records**, and verified all **51 source hashes**. All 600 solved
monthly allocation hierarchies completed optimally, with zero reported MIP gap.
The other months were 480 zero-benefit decisions and 2,760 no-candidate decisions.
There were no solver fallbacks or feasibility-validation failures.

## Six-policy comparison

Held-out default: alpha 1, budget 150. Mean terminal enrollment is out of 100,
so its numerical value also gives retention percent. Differences and Student-t
95% intervals use the thirty paired independent episodes.

| Policy | Mean terminal enrolled | Difference vs WAIT [95% CI] | Programmes | Spending |
| --- | ---: | --- | ---: | ---: |
| WAIT | 71.167 | 0.000 [0.000, 0.000] | 0.00 | 0.00 |
| Random feasible | 71.967 | 0.800 [0.469, 1.131] | 30.00 | 150.00 |
| Highest severity | 72.700 | 1.533 [1.197, 1.869] | 30.00 | 150.00 |
| Need priority | 71.700 | 0.533 [0.299, 0.768] | 30.00 | 150.00 |
| Longest waiting | 71.800 | 0.633 [0.348, 0.919] | 30.00 | 150.00 |
| Terminal-retention planner | 72.700 | 1.533 [1.197, 1.869] | 30.00 | 150.00 |

In this default scenario, canonical ID tie-breaking makes planner decisions match
severity-first. This experiment establishes no advantage over that baseline.
The source cohort is fixed; held-out seeds vary transition worlds, not students.

## Budget sensitivity

Alpha 1, thirty held-out seeds per row. Full waiting-time, utilization and solver
metrics are available in the linked CSV and monthly records.

| Budget | Mean retained | Difference vs WAIT [95% CI] | Programmes | Spending | Unused budget | Admission months |
| ---: | ---: | --- | ---: | ---: | ---: | --- |
| 0 | 71.167 | 0.000 [0.000, 0.000] | 0.00 | 0.00 | 0.00 | None |
| 50 | 71.500 | 0.333 [0.154, 0.512] | 10.00 | 50.00 | 0.00 | 1 |
| 150 | 72.700 | 1.533 [1.197, 1.869] | 30.00 | 150.00 | 0.00 | 1–2 |
| 300 | 73.400 | 2.233 [1.756, 2.711] | 60.00 | 300.00 | 0.00 | 1–3 |
| 500 | 74.433 | 3.267 [2.520, 4.013] | 99.33 | 496.67 | 3.33 | 1–5 |

The default budget funds twenty students in month one and ten in month two. At
budget 500, twenty are supported in each of months one through four and an
average 19.33 in month five. Withdrawals before support and one-programme
eligibility leave no further candidates, explaining the small unused balance.
The heuristic does not reserve budget for future state-dependent opportunities.

## Intervention-strength sensitivity

Budget 150, thirty held-out seeds per row. Estimated benefit is the sum of the
selected monthly rollout benefits, not a realized reward or a full-horizon value.

| Alpha | Mean retained | Difference vs WAIT [95% CI] | Programmes | Spending | Estimated benefit |
| ---: | ---: | --- | ---: | ---: | ---: |
| 0 | 71.167 | 0.000 [0.000, 0.000] | 0.00 | 0.00 | 0.000000 |
| 0.25 | 71.467 | 0.300 [0.100, 0.500] | 30.00 | 150.00 | 0.409681 |
| 0.5 | 71.933 | 0.767 [0.404, 1.129] | 30.00 | 150.00 | 0.819361 |
| 1 | 72.700 | 1.533 [1.197, 1.869] | 30.00 | 150.00 | 1.638722 |

At alpha zero the planner allocates no programmes and retains the entire budget.
The runner checked complete student-condition trajectory equality across policies
in every zero-effect and zero-budget world.

## Benefit-by-horizon diagnostic

Alpha 1. Values are calculated from the supplied transition matrices. The full
CSV contains all twelve decision horizons for all four effect strengths.

| Condition | 12 months | 6 months | 3 months | 1 month |
| --- | ---: | ---: | ---: | ---: |
| Stable | 0.013565452 | 0.012491890 | 0.007677750 | 0.003000000 |
| Vulnerable | 0.054075851 | 0.051764445 | 0.033852500 | 0.010000000 |
| Disengaged | 0.088127128 | 0.104138973 | 0.100834500 | 0.070000000 |
| Withdrawn | 0 | 0 | 0 | 0 |

Benefits depend on the remaining horizon and need not be monotonic. The
disengaged benefit peaks at an intermediate horizon under these assumptions.

## Exact versus approximate policies

Both values use complete joint-transition enumeration, including all future
decisions. First actions include mentor assignments in the exported JSON/CSV.

| Scenario | Exact expected enrollment | Heuristic expected enrollment | Absolute gap | Exact first action | Heuristic first action |
| --- | ---: | ---: | ---: | --- | --- |
| Two stable students, 3 months, budget 5 | 1.953501435 | 1.949161250 | 0.004340185 | WAIT | Support one student |
| Vulnerable + disengaged, 2 months, budget 0 | 1.671500000 | 1.671500000 | 0 | WAIT | WAIT |
| Vulnerable + disengaged, 2 months, budget 5 | 1.762750000 | 1.762750000 | 0 | Support disengaged | Same |
| Heterogeneous mentors, 2 months, budget 10 | 1.823850000 | 1.823850000 | 0 | Support disengaged | Same |
| Three conditions, final month, budget 10 | 2.895000000 | 2.895000000 | 0 | Support vulnerable + disengaged | Same |

The first scenario has relative gap **0.222175%**. Expected programme spending is
4.9997332 for the exact policy and 5 for the heuristic. Waiting preserves the
option to target a student who deteriorates; the rollout objective does not
explicitly value that option. All other tested scenarios have zero gap up to
floating-point precision. Computation times and expenditure are recorded for
every tiny scenario.

## Solver diagnostics and reproducibility

The maximum candidate and variable count was 200. Across every planner decision,
including empty decisions, mean runtime was **0.006238 seconds** and maximum
runtime **0.076285 seconds**. Mean default held-out runtime summed over the
twelve-month episode was **0.093701 seconds**. All completed monthly MIP gaps
were zero. No full-cohort CMDP optimality claim is made.

Execution used Python **3.14.8**, NumPy **2.3.5**, SciPy **1.18.1**, pandas **2.2.3**
and Matplotlib **3.11.2**. The manifest and lock file retain these exact versions,
solver settings, configurations, matrices, seeds and source hashes. The project
declares Python 3.12–3.13; these runs do not certify those interpreters.
Reproducibility checks compare decisions and trajectories while excluding timing.

## Files and artifacts

New implementation and validation files:

- [Exact monetary helpers](../src/school/money.py)
- [Planner exports and tiny comparison grid](../src/school/planner_exports.py)
- [Step 3 acceptance tests](../tests/test_step3_acceptance.py)
- [Independent saved-output verifier](../scripts/verify_cmdp_planner.py)
- [Versioned planner configuration](../configs/cmdp_planner_v1.toml)
- [Mathematical formulation, constraints, solver settings and limitations](cmdp_planner_v1.md)

Existing modules updated: [value estimator](../src/school/retention_value.py),
[planner](../src/school/constrained_planner.py),
[MILP resource rows](../src/school/optimization.py),
[independent validator](../src/school/constraints.py),
[environment ledger](../src/school/cmdp_environment.py),
[greedy accounting](../src/school/greedy_matching.py),
[decision snapshot](../src/school/decision_state.py),
[allocation diagnostics](../src/school/allocation_result.py),
[scenario configuration](../src/school/scenario_config.py),
[policy factory](../src/school/allocation_policies.py),
[exact reference](../src/school/exact_tiny_mdp.py),
[experiment runner](../src/school/cmdp_experiments.py),
[metrics](../src/school/cmdp_metrics.py), [reports](../src/school/cmdp_reports.py)
and [README](../README.md). The existing [School facade](../src/school/school.py)
coordinates the planner and environment through its unchanged policy interface.

Generated results:

- [Full experiment report](../results/cmdp_planner_v1/step3_20261105/report.md)
- [Policy comparison](../results/cmdp_planner_v1/step3_20261105/policy_comparison.csv)
- [Budget sensitivity](../results/cmdp_planner_v1/step3_20261105/budget_sensitivity.csv)
- [Effect sensitivity](../results/cmdp_planner_v1/step3_20261105/effect_sensitivity.csv)
- [Benefit table](../results/cmdp_planner_v1/step3_20261105/benefit_by_condition.csv)
- [Exact comparisons](../results/cmdp_planner_v1/step3_20261105/tiny_exact_comparison.csv)
- [Monthly solver diagnostics](../results/cmdp_planner_v1/step3_20261105/solver_diagnostics.csv)
- [Independent verification](../results/cmdp_planner_v1/step3_20261105/verification.json)
- [Figures](../results/cmdp_planner_v1/step3_20261105/figures/)

The result directory also contains episode/monthly CSVs, JSONL records,
representative trajectories, configuration/seed/source manifests and the numerical
dependency lock. Existing results were preserved. Transition assumptions remain
synthetic; the experiment does not establish real-world dropout reduction.

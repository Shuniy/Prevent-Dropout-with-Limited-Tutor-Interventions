# Step 4 execution and acceptance

## Implementation and validation

The initial suite passed **139 tests** before implementation. The final complete
suite passed **162 tests in 44.111 seconds**:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The selected environment was Python 3.14.8. This is the already configured local
runtime, outside the project's declared Python 3.12/3.13 support range. This run
verifies the implementation on that recorded dependency stack; it does not certify
a new supported Python release. No packaging requirement was changed.

The tests include strict/soft coverage, decimal ceiling, equal normalized cell
weighting, the 10+10-student hand example, exhaustive deterministic tiny-schedule
comparison, whole-window exact budget/capacity checks, canonical ties, failures,
announced future slots, withdrawal destroying a feasible forecast, frozen strata,
unknown/empty/small cohorts, historical admissions, overlapping audits, independent
coverage evaluation, null-effect trajectories, unchanged immediate benefits and
source preservation. A complete small experiment grid was run twice, comparing
all nontiming episode metrics and byte-identical access/window-history tables.
Development failure prevents held-out execution and retains explicit context.

Existing fairness tests now evaluate one active attribute at a time and the new
integer/frozen-condition definitions; the historical-admission test uses a
zero-effect matrix so canonical timing is hand-checkable. The audit regression
explicitly checks undefined empty-cell waiting rather than dividing by zero.
Step 1–3 operational/transition/planner tests continue to pass.

## Files and integration

New implementation files:

- [fairness_window.py](../src/school/fairness_window.py): frozen ledger.
- [window_optimization.py](../src/school/window_optimization.py): shared-rule
  time-indexed model and independent schedule validation.
- [fairness_experiments.py](../src/school/fairness_experiments.py): frozen paired
  grid, episode statistics, export and figures.
- [cmdp_fairness_v1.toml](../configs/cmdp_fairness_v1.toml): explicit assumptions.
- [run_cmdp_fairness.py](../scripts/run_cmdp_fairness.py) and
  [verify_cmdp_fairness.py](../scripts/verify_cmdp_fairness.py): execution and
  independent saved-result reconciliation.
- [test_fairness_step4.py](../tests/test_fairness_step4.py) and
  [test_fairness_experiments.py](../tests/test_fairness_experiments.py).

Extended existing components:

- [fairness_planner.py](../src/school/fairness_planner.py) replaces the eager
  current-month heuristic with the rolling MILP and declared objective hierarchy.
- [fairness_audit.py](../src/school/fairness_audit.py) adds integer targets,
  operational cohort construction, explicit unknown/empty/small cells, waiting
  disparities and retention audits independent of solver objectives.
- [allocation_policies.py](../src/school/allocation_policies.py),
  [scenario_config.py](../src/school/scenario_config.py),
  [allocation_result.py](../src/school/allocation_result.py),
  [decision_state.py](../src/school/decision_state.py),
  [cmdp_environment.py](../src/school/cmdp_environment.py),
  [cmdp_simulation.py](../src/school/cmdp_simulation.py),
  [cmdp_experiments.py](../src/school/cmdp_experiments.py),
  [cmdp_reports.py](../src/school/cmdp_reports.py) and
  [optimization.py](../src/school/optimization.py) connect configuration,
  announced calendars, schedule diagnostics, integer slack and actual ledgers.
- [student.py](../src/school/student.py) and
  [student_observation.py](../src/school/student_observation.py) preserve unknown
  proxy/audit values.
- [test_cmdp_fairness.py](../tests/test_cmdp_fairness.py) and
  [test_cmdp_evaluation.py](../tests/test_cmdp_evaluation.py) update the old audit
  assumptions. README, architecture, contracts, design, implementation and roadmap describe
  the final interfaces.

The unchanged [School facade](../src/school/school.py) runs the injected fairness
policy through `School.run_cmdp`. The resource-only planner, retention estimator,
transition matrices, source datasets and previous results are preserved.

## Experiment protocol

Command:

```bash
.venv/bin/python scripts/run_cmdp_fairness.py --output results/cmdp_fairness_v1
.venv/bin/python scripts/verify_cmdp_fairness.py results/cmdp_fairness_v1
```

The frozen grid contains 25 policy/scenario settings, with 100 students, two
mentors, twelve months and five appointments per admission. It uses ten development
worlds (42–51) and thirty held-out worlds (10042–10071): 1,000 episodes in total.
The default target .3 was frozen before held-out outcomes. All comparisons below
use held-out episodes; retention differences and confidence intervals are paired
across identical worlds. The complete [configuration](../results/cmdp_fairness_v1/experiment_config.json)
records dependencies, seeds, objective/projection assumptions and source/population
hashes. See [the mathematical formulation](cmdp_fairness_v1.md) for denominator,
shortfall and projection definitions.

The first-window eligible counts are identical across seeds and policies:

| Disadvantage proxy | Stable N / K at q=.3 | Vulnerable N / K | Disengaged N / K |
| --- | --- | --- | --- |
| False | 69 / 21 | 12 / 4 | 0 / 0 |
| True | 11 / 4 | 8 / 3 | 0 / 0 |
| Unknown | 0 / 0 | 0 / 0 | 0 / 0 |

Thus q=.3 requires 32 admissions in the first window after cell-level ceilings,
whereas budget 150 funds only 30. Later-window denominators vary by policy/seed;
every cell count is retained in the group-access and window-history tables.

## Resource-only comparison and target sweep

Held-out means at budget 150, alpha=1; each row contains 30 paired episodes.
Shortfall counts sum integer unmet obligations over three windows, rather than
counting distinct students across the entire episode. Access gaps are averaged
within frozen condition strata and then across windows at the episode level.

| Policy/target | Retained (%) | Difference vs resource-only (percentage points, 95% CI) | Mean access gap (%) | Unmet student obligations | Sum normalized shortfall |
| --- | ---: | --- | ---: | ---: | ---: |
| Resource-only | 72.700 | reference | 1.216 | 59.267 at q=.3 | 5.452 at q=.3 |
| q=0 | 72.700 | 0.000 [0.000, 0.000] | 1.216 | 0 at q=0 | 0 at q=0 |
| q=.1 | 72.767 | +0.067 [-0.070, +0.203] | 1.101 | 18.600 | 3.039 |
| q=.2 | 72.567 | -0.133 [-0.323, +0.056] | 1.546 | 30.967 | 4.250 |
| q=.3 | 72.467 | -0.233 [-0.538, +0.072] | 1.794 | 45.767 | 5.106 |
| q=.4 | 72.533 | -0.167 [-0.478, +0.145] | 4.262 | 67.767 | 6.285 |

All these allocation policies spend 150 and admit 30 students. At the common q=.3
obligation, fairness reduces mean unmet student obligations from 59.267 to 45.767,
and normalized shortfall from 5.452 to 5.106. The mean access gap **increases** from
1.216% to 1.794%. Minimum coverage and parity are different properties. Increasing
q does not monotonically reduce disparity or retention. All default-budget paired
retention intervals in this target sweep include zero.

The q=0 admissions and entire student trajectories equal resource-only exactly.
Its zero policy-specific shortfall is trivial; use the exported common-.3 reference
shortfall for a like-for-like obligation comparison. The unweighted mean eligible
cell access rate is 15.002% for resource-only and 8.833% for q=.3. This average is
sensitive to small cells and later-window cohort composition; it is not the
percentage of all episode students supported (30% for both).

The independent verifier passed all **1,000 episodes, 12,000 decision months and
27,000 group/window cells**, including exact frozen denominators, admission
counts, integer thresholds, money ledgers and current source/population hashes.
There were **zero operational validation failures, solver fallbacks or incomplete
optimization hierarchies**. Of the decision months, 1,623 solved a nontrivial fair
MILP to the complete hierarchy; the remaining fair months had no actionable
candidates or delegated at q=0.

A second complete 1,000-episode execution reproduced **every nontiming episode
column**, including allocation and full trajectory hashes. The final run includes
the exact-original-price and actionable-ledger fixes, whose source hashes differ
from the first run; all configured prices are 1.0, so those fixes leave this
benchmark's allocations/outcomes unchanged. See
[the reconciliation](../results/cmdp_fairness_v1/verification.json) and
[the repeat comparison](../results/cmdp_fairness_v1/reproducibility.json).

The five baseline terminal-retention means are WAIT 71.167%, random feasible
71.967%, severity 72.700%, existing need priority 71.700%, and longest waiting
71.800%. Complete estimates are in [the policy comparison](../results/cmdp_fairness_v1/policy_comparison.csv)
and [the trade-off dataset](../results/cmdp_fairness_v1/fairness_retention_tradeoff.csv).

## Budget sensitivity

Alpha=1, q=.3 for the fair policy, 30 held-out episodes per row pair.

| Budget | Resource retention (%) | Fair retention (%) | Paired difference (pp, 95% CI) | Resource/Fair unmet obligations | Resource/Fair students admitted |
| ---: | ---: | ---: | --- | --- | --- |
| 0 | 71.167 | 71.167 | 0.000 [0.000, 0.000] | 90.067 / 90.067 | 0 / 0 |
| 50 | 71.500 | 71.333 | -0.167 [-0.339, +0.006] | 78.500 / 75.300 | 10 / 10 |
| 150 | 72.700 | 72.467 | -0.233 [-0.538, +0.072] | 59.267 / 45.767 | 30 / 30 |
| 300 | 73.400 | 74.033 | +0.633 [+0.247, +1.019] | 28.100 / 27.100 | 60 / 60 |
| 500 | 74.433 | 74.833 | +0.400 [+0.112, +0.688] | 0 / 0 | 99.333 / 99.033 |

Resources stay hard. Spending is exactly the budget through 300; at budget 500,
mean spending is 496.667 for resource-only and 495.167 for fairness. Corresponding
programme-capacity utilization is 0%, 4.167%, 12.5%, 25%, and approximately
41.389%/41.264% for resource/fair at 500. Larger budgets do not create capacity or
bring withdrawn students back. The fair policy's forecast is infeasible in all
12 decision months at budgets 0, 50 and 150, in eight months at budget 300, and in
zero months at 500. At budget 500 all recorded q=.3 window targets are achieved;
that is an observed result in these worlds, not a guarantee for other worlds.

The positive retention differences at higher budgets include within-window
scheduling effects as well as coverage requirements. See
[the complete budget table](../results/cmdp_fairness_v1/budget_sensitivity.csv).

## Intervention-strength sensitivity

Budget 150, q=.3, 30 held-out episodes per row pair.

| Alpha | Resource retention (%) | Fair retention (%) | Paired difference (pp, 95% CI) | Resource/Fair spending |
| ---: | ---: | ---: | --- | --- |
| 0 | 71.167 | 71.167 | 0.000 [0.000, 0.000] | 0 / 150 |
| .25 | 71.467 | 71.467 | 0.000 [-0.139, +0.139] | 150 / 150 |
| .5 | 71.933 | 71.867 | -0.067 [-0.376, +0.242] | 150 / 150 |
| 1 | 72.700 | 72.467 | -0.233 [-0.538, +0.072] | 150 / 150 |

At alpha=0 the immediate benefit is zero, resource-only waits throughout, and
fairness still admits 30 students. Full monthly student-condition trajectories,
not just terminal means, are identical under the matched keyed draws. Access
pressure alone does not manufacture an intervention effect. See
[the complete effect table](../results/cmdp_fairness_v1/effect_sensitivity.csv).

## Windows, infeasibility and uncertainty

At default budget 150, the .3 target is already projected infeasible in the first
window: discrete cell ceilings can require more than the 30 funded admissions.
The policy minimizes the remaining normalized deficit and uses the budget in the
first window; later windows retain their own frozen obligations with no remaining
funds. Targets are never lowered. The q=.1/.2 forecasts are feasible in the first
window but become infeasible in the eight later decision months. The
[monthly window ledger](../results/cmdp_fairness_v1/window_history.csv) records
frozen counts, prior/new admissions, actionable candidates, withdrawals, integer
requirements, actual deficits and tentative coverage separately.

The mean initial-forecast-minus-final-actual coverage gap for the q=.3 policy is
zero at budgets through 300 and +0.300 students at budget 500. Replacement
allocations can hide losses of individual planned recipients in a count-level gap;
this does not imply every original tentative student was served. The withdrawal
regression directly tests an initially feasible schedule becoming infeasible.
Resource-only supplies no future forecast, so its corresponding negative gaps
reflect later admissions beyond its initial current-month plan.

Strict mode is checked with the manual 10+10-student example: six funded programmes
permit three per group; four funded programmes yield `fairness_infeasible`, without
an operational violation. Soft mode schedules four and reports two unmet students,
normalized aggregate .2. Further tests cover loss of compatibility, future capacity
and enrolled students withdrawing before their planned intervention.

All reported confidence intervals are simulation uncertainty. Small-cell flags,
undefined empty rates and unknown groups remain visible. Mean gaps alone do not
establish fairness. These results use a synthetic population and assumed effects;
they provide no causal or real-world equity claim.

## Outputs and figures

All requested files are in [the versioned results directory](../results/cmdp_fairness_v1/):
[episodes](../results/cmdp_fairness_v1/episode_results.csv),
[months](../results/cmdp_fairness_v1/monthly_results.csv),
[group access](../results/cmdp_fairness_v1/group_access.csv),
[shortfalls](../results/cmdp_fairness_v1/fairness_shortfalls.csv),
[targets](../results/cmdp_fairness_v1/fairness_targets.csv),
[solver diagnostics](../results/cmdp_fairness_v1/solver_diagnostics.csv),
[mentor workload](../results/cmdp_fairness_v1/mentor_workload.csv),
[group retention](../results/cmdp_fairness_v1/group_retention.csv),
[configuration](../results/cmdp_fairness_v1/experiment_config.json),
[completion record](../results/cmdp_fairness_v1/COMPLETED.json), and
[independent verification](../results/cmdp_fairness_v1/verification.json).

The existing application CLI also completed its two-policy smoke comparison:

```bash
.venv/bin/python -m src.main --config configs/cmdp_fairness_v1.toml \
  --students 6 --months 4 --development-seeds 1 --stage development \
  --policies terminal_value fairness --output results/cmdp_fairness_v1_cli
```

![Coverage and retention trade-off](../results/cmdp_fairness_v1/figures/fairness_retention_tradeoff.png)

![Group access](../results/cmdp_fairness_v1/figures/group_access_comparison.png)

![Window coverage](../results/cmdp_fairness_v1/figures/coverage_by_window.png)

![Budget sensitivity](../results/cmdp_fairness_v1/figures/budget_vs_fairness.png)

![Retention by policy](../results/cmdp_fairness_v1/figures/retention_by_policy.png)

## Acceptance criteria

| # | Requirement | Evidence |
| ---: | --- | --- |
| 1 | Authorized attributes and provenance | Configuration and provenance discussion in the formulation |
| 2 | Comparable-need eligibility | One axis, broad oracle conditions, shared compatibility; cohort tests |
| 3 | Fairness windows | Four-month windows and shorter-horizon truncation |
| 4 | Frozen denominators | Immutable memberships; condition/withdrawal tests; saved-result verifier |
| 5 | Unique admission access | History-based recipient sets; five appointments count once; overlap test |
| 6 | Configurable targets | Versioned TOML plus all five target experiments |
| 7 | Strict and shortfall-aware modes | Hand-checkable feasible/infeasible examples |
| 8 | Integrated shared MILP | Shared candidates, resource rows, solver and validators |
| 9 | Lexicographic order | Normalized slack, retention, cost, canonical bits; tiny enumeration |
| 10 | Earlier admissions and remaining opportunities | Ledger plus time-indexed rolling schedule; history/projection tests |
| 11 | Hard operational limits | Exact original mentor prices, per-month capacities and independent validation |
| 12 | Explicit infeasibility diagnostics | Strict status, integer realized deficits, projected feasibility and cell counters |
| 13 | 100-student/12-month episode | Full 1,000-episode grid |
| 14 | Resource-only preserved | Planner source unchanged; q=0 exact decisions and full regression tests |
| 15 | Independent auditor | Actual recorded allocations and saved-result reconciliation |
| 16 | Access, wait, retention, shortfall | Per-cell/group/window and workload CSVs |
| 17 | Target experiments | q=0, .1, .2, .3, .4 with held-out means and paired intervals |
| 18 | Budget sensitivity | 0, 50, 150, 300, 500 |
| 19 | Effect sensitivity | 0, .25, .5, 1; exact null-trajectory equality |
| 20 | Resource/fair comparisons | Target, policy, budget and effect tables and five figures |
| 21 | Prior/new regressions | 162 tests passed; existing application CLI smoke completed |
| 22 | Reproducibility | Frozen config, source/population hashes, keyed draws, repeated grids and output verification |

The implementation stops at Step 4. Optimistic future enrollment, no funds reserved
for later windows, small synthetic cohorts, fixed one-programme effects and the
recorded-runtime support-range mismatch remain explicit limitations. Step 5's LLM
feedback and estimated-state integration are not implemented.

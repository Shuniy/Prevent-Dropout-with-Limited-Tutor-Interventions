# Step 2 — Baseline allocation policies and comparative experiments

The implementation reuses the existing `CMDPEnvironment`, `School`, Student,
Mentor and SupportType contracts. It adds no transition model, optimizer, fairness
constraint or LLM integration. Historical optimizer/fairness code remains opt-in.
Step 1's existing CMDP tests were run before editing: 43 tests passed.

## Policies and matching

`AllocationPolicy.plan(DecisionState) -> AllocationResult` remains the structural
interface. Observations are frozen decision-time snapshots with current condition,
enrollment, fixed need/support type, programme history, waiting, mentors,
compatibility, admissions, slots, costs and remaining budget. No future draws,
future conditions or evaluator tables are passed to policies. Partial observations
can replace current conditions without changing the matching algorithms.

All five `BaselinePolicy` modes call `rank_students`, then the same
`greedy_matching.assign_feasible`. This follows the repository's existing single
policy class convention rather than duplicating five classes.

| Policy | Student priority |
| --- | --- |
| `wait` | Empty programme proposal; everyone takes the monthly WAIT transition |
| `random` | Shuffle eligible students in stable ID order with an independent local seeded RNG |
| `severity` | Disengaged, vulnerable, stable, then stable student ID |
| `need_priority` | Descending initial `Student.need_score`, then student ID |
| `longest_waiting` | Descending `waiting_months`, then student ID; no severity tie-break |

Need priority is authoritative: `Student.need_score` selects the maximum severity
from `needs.calculate_needs`. The shared rules use source learning gap/failures,
initial attendance/engagement, internet/travel/study routine, family relationship,
health and explicitly verified financial need when available. Need/support type
are frozen at environment initialization, not updated using unchanged source data.
Support-type ties use the existing concern-name ordering. Neither severity nor
need priority estimates causal programme benefit.

The matcher chooses each student's cheapest feasible mentor, then mentor ID. It
checks enrollment, no previous programme, support/compatibility, one admission,
five available slots, full five-session cost, no duplicate student and all remaining
resource limits. Local reservations do not mutate environment state; `step`
independently validates before applying resources and transitions. Omitted students
take WAIT. Withdrawn students stay withdrawn.

Greedy matching is not maximum-cardinality or globally optimal: if a flexible
student consumes mentor A's only slot and a later student can use only A, it may
assign one student when a rearrangement could assign two. A representative test
demonstrates this limitation. Random priority is over students, not mentor edges;
it is not a uniform draw from all feasible joint allocations. Policy version is
`student_priority_v2`; older random-baseline results used a different algorithm.

## Reproduce the experiments

Use a project environment with the existing requirements installed. Default
configuration is `configs/cmdp_baselines_v1.toml`, numerically the Step 1 scenario:
100 students, 2 mentors, 12 months, 10 admissions and 50 slots per mentor/month,
5 appointments/programme, appointment price 1, budget 150, effect strength 1.
No extra dependency was added.

```sh
# All offline tests, including existing environment and new baseline tests.
MPLCONFIGDIR=/private/tmp/cmdp-baselines-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-baselines-cache \
  .venv/bin/python -m unittest discover -s tests

# Development only: 10 seeds, all eight sensitivity scenarios, five policies.
MPLCONFIGDIR=/private/tmp/cmdp-baselines-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-baselines-cache \
  .venv/bin/python -m src.main --suite full --stage development \
  --output results/cmdp_baselines_v1/my_development

# After inspecting development: rerun development validation, then 30 held-out seeds.
MPLCONFIGDIR=/private/tmp/cmdp-baselines-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-baselines-cache \
  .venv/bin/python -m src.main --suite full \
  --output results/cmdp_baselines_v1/my_comparison

# Single policy, custom starting seed/budget/effect; default suite uses overrides.
.venv/bin/python -m src.main --policies random --seed 80 --budget 50 \
  --effect-strength 0.5 --output results/cmdp_baselines_v1/my_random
```

`--seed` sets the first development seed; defaults are 42–51. Held-out seeds start
10,000 later, default 10042–10071. Counts can be reduced with
`--development-seeds` (1–10) and `--evaluation-seeds` (1–30). Each scenario/world
builds the source cohort and mentors once, then each policy environment copies
those identical inputs. SHA-256 keyed environmental draws use episode seed,
student ID, month and event type. Policy randomness uses an independent local
generator seeded by policy version, episode seed and decision month. Policy
instances do not retain mutable RNG state across episodes.

The full suite fixes effect sensitivity at budget 150 with alpha
0, 0.25, 0.5, 1, and budget sensitivity at alpha 1 with budgets
0, 50, 150, 300, 500. The shared default scenario is run once (eight total
scenarios). Full-suite budget/effect grids intentionally override those CLI fields.
Other scenario settings remain configurable. No realized monotonicity is forced.

Development ledger, completeness, identical-start and full student-trajectory
null checks pass before evaluation begins. `development_summary.json` and
`development_validation.json` are written before the first held-out episode.
An invalid allocation fails rather than being repaired. `failure.json` records
world/policy/error details; partial episode results remain available and no
completion marker is written. Every successful run validates all expected manifest
identities: missing policies/worlds/scenarios and duplicate episodes are errors.
No held-out tuning is performed.

## Metrics and interpretation

Terminal retention counts non-withdrawn students after transition T and divides
by the initially enrolled cohort, excluding source rows not initially enrolled.
All default cohorts contain 100 initially enrolled students. Enrolled student-months
sum enrollment after transitions 1–T, excluding month zero. Monthly summaries
include month zero, each categorical condition, new/cumulative withdrawals,
enrollment, programme starts, sessions, spending, remaining funds and mentor usage.
Version 1 completes all five sessions in the admission month.

Waiting counts full unsupported months survived; admission and withdrawal stop the
counter without counting that month. Eligible waiting statistics use enrolled,
unsupported students only; empty eligible sets return zero mean/max and an empty
distribution. All-student waiting statistics retain censored counters, and
recipient waits are recorded before admission. Recipient mean wait and cost per
supported student are null if no programme is admitted. All unserved survivors tie
on waiting in this closed cohort; this limits how informative that baseline is.
Utilization denominators sum actual available monthly capacity/slots, not usage.

Access audits describe offers by existing source sex and disadvantage proxy,
stratified by initial condition and fixed support need. Denominators are explicitly
frozen initial eligible counts and include later withdrawals. The disadvantage
proxy is not verified poverty; no attributes are inferred from notes. No fairness
constraints are enforced.

Summary sample SDs use independent episodes. Paired student-count and percentage-
point differences match seeds and use a two-sided 95% Student-t interval with
n−1 degrees of freedom. A single episode has undefined sample SD/CI. Intervals
are pointwise, with no multiple-comparison correction. Students within a constrained
world are not independent repetitions. Intervals describe Monte Carlo variability
under synthetic transitions, not real-world causal-effect uncertainty.

## Files and outputs

Production additions: `greedy_matching.py`, `baseline_validation.py`, and
`baseline_exports.py` under `src/school`. Updated: baseline policy/factory,
environment month records, metrics, experiment runner/reports and CLI. Added
`configs/cmdp_baselines_v1.toml`, `tests/test_baseline_policies.py`, and
`tests/test_baseline_evaluation.py`. README, architecture, contracts, roadmap and
CMDP implementation documentation describe the current workflow.

Each new output directory contains:

- `episode_results.csv`, `monthly_results.csv`, `policy_comparison.csv`,
  `budget_sensitivity.csv`, `effect_sensitivity.csv`, and `access_audit.csv`.
- `manifest.json` / `experiment_config.json` with configuration, exact seeds,
  policy versions, matrices, dependencies, source population/code hashes and conventions.
- `episodes.jsonl` with full metrics; `sample_trajectories.jsonl` with first-seed
  trajectories per partition/policy/scenario; `summary.json` and `report.md`.
- `development_summary.json`, `development_validation.json`, and `COMPLETED.json`.
- Eight PNGs under `figures/`: `retention_comparison`, `retention_trajectories`,
  `cumulative_withdrawals`, `cumulative_spending`, `monthly_programmes`,
  `programme_utilization`, `budget_sensitivity`, and `effect_sensitivity`.
  Existing `monthly_conditions.png` and `paired_retention.png` are also retained.

Episode/monthly CSV rows carry policy/version, world seed, scenario/version,
configuration/scenario hashes, budget, effect, cohort size and horizon. Episode
rows include resource validation diagnostics. Nested monthly mentor utilization
and waiting distributions are JSON cells. Access denominators are explicit in the
separate audit table. Summary CSVs include sample SDs and paired count/percentage-
point differences and intervals. `summarize(episodes, manifest)` reconstructs
summaries solely from saved episode JSONL. Existing directories are never overwritten.
Outputs follow the repository's ignored `results/` convention.

## Acceptance verification

The execution results below record the completed development and held-out runs.
Acceptance criteria 1–15 correspond to the tests and artifacts as follows:

| Criteria | Evidence |
| --- | --- |
| 1–3: five policies, existing environment, common feasibility/matching | `test_baseline_policies`, existing integration tests |
| 4–5: hard limits and complete 100-student, 12-month episodes | Environment validator, independent episode ledger audits, full suite |
| 6–9: reproducibility, paired evaluation, zero budget/effect | Reproducibility tests, policy-order tests, full-trajectory checks in runner |
| 10: retention, utilization, waiting | Existing evaluation/transition tests plus new denominator/distribution tests |
| 11–12: development and held-out execution | Separate development run, gate records and complete manifest grid |
| 13–14: comparison tables and plots | Six CSV exports, summary/report and ten PNGs |
| 15: passing new tests | Full offline unittest suite |

The local `.venv` uses Python 3.14.8, while the project declares Python 3.12–3.13;
this execution does not verify supported-interpreter compatibility. All effects
are synthetic assumptions, source cohort selection is deterministic, and held-out
seeds vary worlds rather than source students. These limitations do not establish
real-world mentoring effectiveness or global allocation optimality.

## Executed results — 5 November 2026

All **125 offline tests passed**, including 18 new baseline tests. A separate development-only run completed **400 episodes** before inspection. The final comparison then completed **1,600 episodes**: eight scenarios × five policies × (10 development + 30 held-out seeds). All 15 acceptance criteria above passed in the tested environment.

Independent saved-output checks verified 20,800 month-zero/monthly summaries, reproduced all 80 summaries exactly, recomputed all 400 paired count confidence intervals, and replayed 960 representative months through the existing environment. All source hashes matched; no resource violation, missing episode or duplicate episode was found. The runner checked full student-level null trajectories across every policy in all zero-effect and zero-budget worlds.

[Full report](../results/cmdp_baselines_v1/comparison_20261105/report.md), [independent verification](../results/cmdp_baselines_v1/comparison_20261105/verification.json), [development gate](../results/cmdp_baselines_v1/comparison_20261105/development_validation.json), [separate development run](../results/cmdp_baselines_v1/development_20261105/report.md).

Default held-out comparison (100 students, budget 150, alpha 1, 12 months):

| Policy | Mean retained (SD) | Retention | Paired difference vs WAIT [95% CI] | Programmes | Spending |
| --- | ---: | ---: | --- | ---: | ---: |
| wait | 71.167 (3.475) | 71.167% | 0.000 [0.000, 0.000] | 0.00 | 0.00 |
| random | 71.967 (3.548) | 71.967% | 0.800 [0.469, 1.131] | 30.00 | 150.00 |
| severity | 72.700 (3.650) | 72.700% | 1.533 [1.197, 1.869] | 30.00 | 150.00 |
| need_priority | 71.700 (3.426) | 71.700% | 0.533 [0.299, 0.768] | 30.00 | 150.00 |
| longest_waiting | 71.800 (3.478) | 71.800% | 0.633 [0.348, 0.919] | 30.00 | 150.00 |

Because N=100 here, paired student-count differences and intervals have the same numerical values in percentage points. All four active baselines deliver 150 appointments, support 30 distinct students, and use 12.5% of annual mentor admissions/slots. The final eligible mean waiting time is 12 months for every default policy; pre-admission waiting is reported separately in the CSV.

Budget sensitivity, mean terminal enrolled at alpha 1:

| Budget | WAIT | Random | Severity | Need priority | Longest waiting |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 71.167 | 71.167 | 71.167 | 71.167 | 71.167 |
| 50 | 71.167 | 71.467 | 71.500 | 71.467 | 71.333 |
| 150 | 71.167 | 71.967 | 72.700 | 71.700 | 71.800 |
| 300 | 71.167 | 73.100 | 73.400 | 72.733 | 72.833 |
| 500 | 71.167 | 74.400 | 74.433 | 73.867 | 74.267 |

Budget resource results (WAIT always has zero programmes, spending and utilization):

| Budget | Policy | Mean supported | Mean spending | Admission/slot utilization | Final eligible mean wait |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | random | 0.000 | 0.000 | 0.000% | 12.000 |
| 0 | severity | 0.000 | 0.000 | 0.000% | 12.000 |
| 0 | need_priority | 0.000 | 0.000 | 0.000% | 12.000 |
| 0 | longest_waiting | 0.000 | 0.000 | 0.000% | 12.000 |
| 50 | random | 10.000 | 50.000 | 4.167% | 12.000 |
| 50 | severity | 10.000 | 50.000 | 4.167% | 12.000 |
| 50 | need_priority | 10.000 | 50.000 | 4.167% | 12.000 |
| 50 | longest_waiting | 10.000 | 50.000 | 4.167% | 12.000 |
| 150 | random | 30.000 | 150.000 | 12.500% | 12.000 |
| 150 | severity | 30.000 | 150.000 | 12.500% | 12.000 |
| 150 | need_priority | 30.000 | 150.000 | 12.500% | 12.000 |
| 150 | longest_waiting | 30.000 | 150.000 | 12.500% | 12.000 |
| 300 | random | 60.000 | 300.000 | 25.000% | 12.000 |
| 300 | severity | 60.000 | 300.000 | 25.000% | 12.000 |
| 300 | need_priority | 60.000 | 300.000 | 25.000% | 12.000 |
| 300 | longest_waiting | 60.000 | 300.000 | 25.000% | 12.000 |
| 500 | random | 97.167 | 485.833 | 40.486% | 0.000 |
| 500 | severity | 99.333 | 496.667 | 41.389% | 0.000 |
| 500 | need_priority | 97.500 | 487.500 | 40.625% | 0.000 |
| 500 | longest_waiting | 97.200 | 486.000 | 40.500% | 0.000 |

At budget 500, unsupported students withdraw before admission in some worlds, so not every policy spends the full budget. Eligible waiting is zero when no unsupported enrolled students remain; this does not imply that all initial students were supported.

Intervention-strength sensitivity, mean terminal enrolled at budget 150:

| Alpha | WAIT | Random | Severity | Need priority | Longest waiting |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 71.167 | 71.167 | 71.167 | 71.167 | 71.167 |
| 0.25 | 71.167 | 71.400 | 71.467 | 71.267 | 71.400 |
| 0.5 | 71.167 | 71.667 | 71.933 | 71.567 | 71.533 |
| 1 | 71.167 | 71.967 | 72.700 | 71.700 | 71.800 |

At every effect strength the active policies support 30 students, deliver 150 appointments, spend 150 units and use 12.5% of annual admissions/slots. At alpha 0 their student trajectories exactly match WAIT despite those resource costs.

[Budget CSV](../results/cmdp_baselines_v1/comparison_20261105/budget_sensitivity.csv), [effect CSV](../results/cmdp_baselines_v1/comparison_20261105/effect_sensitivity.csv), [policy comparison CSV](../results/cmdp_baselines_v1/comparison_20261105/policy_comparison.csv).

Figures were visually checked for readable labels and complete layout. Files are under `results/cmdp_baselines_v1/comparison_20261105/figures/`:

![Terminal retention](../results/cmdp_baselines_v1/comparison_20261105/figures/retention_comparison.png)

![Monthly enrollment](../results/cmdp_baselines_v1/comparison_20261105/figures/retention_trajectories.png)

![Budget sensitivity](../results/cmdp_baselines_v1/comparison_20261105/figures/budget_sensitivity.png)

This completes Step 2. No optimizer, fairness allocation or LLM functionality was added in this change. Existing historical results retain their original policy versions and were not overwritten.

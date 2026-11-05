# CMDP v1 implementation

The language-free retention simulator is implemented in `src/school` and exposed
through the existing `School` facade and `main.py`.
It reuses school domain models and matching rules without changing the existing
recorded-intervention workflow. All outcomes are synthetic simulation results.
No course-failure label is interpreted as observed school withdrawal.

## Implementation map

| Existing component | Reuse and boundary |
| --- | --- |
| `school.student`, `student_simulation`, `needs` | Source measurements, disadvantage proxy, source sex, initial support type and maximum need severity; source records remain unchanged |
| `school.loading` | Typed CSV conversion, generalist mentor creation, unique IDs, and `mentor_can_take` compatibility |
| `school.mentor`, `mentor_availability`, `mentor_assignment` | Skills, appointment prices, monthly availability and immutable programme records |
| `basic_examples.cmdp` | Preserved teaching example; its expected-resource occupancy LP is not the realized-resource planner |
| `intervention.intervention_result` | Existing immutable, allowlisted reported-outcome contract; adapted only to evidence, never truth |

| New module(s) in `src/school` | Responsibility |
| --- | --- |
| `scenario_config`, `cmdp_scenarios` | Validated versioned TOML, deterministic enrolled population prefix, existing mentor generation, episode loop |
| `student_condition`, `transition_model` | Four simulated conditions, assumed stochastic matrices, sensitivity interpolation, stable keyed draws |
| `cmdp_environment`, `month_record` | Private condition, one transition per cohort student per month, admission history, atomic charges, immutable history |
| `student_observation`, `mentor_resource`, `decision_state` | Immutable controller snapshots with scalar source-derived context and current resources |
| `constraints`, `allocation_result` | Candidate pairs, independent feasibility validation and solver diagnostics |
| `retention_value`, `optimization`, `constrained_planner` | Terminal rollout values, SciPy MILP with hard constraints, monthly replanning |
| `baseline_policy` | Wait, random, severity, fixed source-need priority, longest waiting |
| `exact_tiny_mdp` | Exact feasible-action Bellman recursion and exact expectation of the production monthly heuristic |
| `access_cohort`, `fairness_audit`, `fairness_planner` | Frozen comparable-need cohorts, window audits, optional lexicographic eager coverage |
| `condition_estimate`, `structured_observation`, `observation_adapter` | Explicit estimated conditions, temporally validated existing extraction results, no truth mutation |
| `cmdp_metrics`, `cmdp_experiments`, `cmdp_reports` | Episode metrics, paired experiment execution, independent report/plot generation and version manifests |
| `allocation_policy`, `allocation_policies`, `cmdp_simulation` | Small policy protocol, policy construction, monthly coordination behind `School.run_cmdp` |

Each production class has its own file, following `Guidance.md`. SciPy is now an
explicit dependency; it was already installed and used by the teaching examples.
There is no new LLM, retrieval system, dashboard or orchestration framework.

## School integration and responsibilities

`School.create_cmdp_environment(config=...)` constructs a synthetic world from
that school's existing students and mentors. `School.run_cmdp(policy, config=...)`
runs it and returns a `CMDPSimulation` containing the completed environment,
initial snapshot and frozen audit cohorts. With no configuration supplied, it
derives the horizon, budget, seed and programme size from the school. An explicit
configuration must agree with those school settings.

The school-facing method delegates monthly coordination; policies implement only
`AllocationPolicy.plan(state) -> AllocationResult`. The protocol is structural:
a new policy needs no inheritance or changes to the monthly coordinator. Environment
transitions, feasibility validation, value estimation, optimization, metrics and
file export remain separate responsibilities. The coordinator depends on the small
policy interface and receives its policy explicitly. These boundaries follow SOLID
without adding a service container or a hierarchy of abstract classes.

CMDP results own their copied resources and simulated condition/budget history.
They do not overwrite the school's source measurements or the recorded-intervention
workflow's performance and attendance records. The CLI chooses the workflow before
creating any LLM client. There is no separate `src/cmdp` package or CMDP CLI module.

```python
from src.school import School
from src.school.baseline_policy import BaselinePolicy

school = School(num_students=100, num_mentors=2, num_months=12, budget=150)
simulation = school.run_cmdp(BaselinePolicy("severity"))
print(simulation.environment.terminal_reward())
```

## Objective and mathematics

Use twelve transitions by default, zero intermediate reward and discount 1:

\[
\max_\pi \mathbb E[R_T],\qquad
R_T=\sum_{i\in I_0}1[s_{i,T}\ne\mathrm{withdrawn}],\qquad
\mathrm{RetentionRate}=R_T/|I_0|.
\]

`I_0` is the initially enrolled cohort. Direct construction reports excluded IDs;
the default scenario loader selects the first 100 enrolled synthetic records.
Known enrollment, attendance and engagement are required even for excluded input
records. Source grades and assumed participation measures never evolve.

With `e = [1, 1, 1, 0]`, the deterministic terminal value is

\[
V_h^{wait}=P_{wait}^h e,\qquad
\Delta_h=(P_{programme}-P_{wait})P_{wait}^{h-1}e.
\]

Here `h` includes the current monthly transition. The effect applies during
admission only. Both rollouts assume no later programmes; `Delta` is not an
optimal CMDP action value. The monthly MILP maximizes `sum Delta_i*x_im` with:

\[
\sum_m x_{im}\le1,\quad
\sum_i x_{im}\le C_m,\quad
5\sum_i x_{im}\le A_m,\quad
\sum_{i,m}5c_m x_{im}\le B_t.
\]

Only compatible, enrolled, previously unused student/mentor pairs get variables.
The programme delivers and charges five appointments in its admission month.
`B_next = B_current - sum programme_cost`; money is not subtracted from reward.
Admission and appointment capacities reset next month. Hours are not an additional
constraint: existing generated mentors use zero hours and no session duration.
Initial active mentor caseloads are rejected rather than silently cleared.

Every allocation is independently checked again against the environment's current
state. Solver limits, infeasibility, missing/fractional/invalid incumbents and
validated feasible incumbents have explicit statuses. Unusable results fall back
to wait. A feasible incumbent is never called optimal. Runtime, monthly objective,
MIP gap and objective bound are recorded. Numerical integrality/continuous slack
tolerance is `1e-6`; independent cost/capacity and realized coverage checks retain
their tighter tolerances. Budget roundoff within `1e-7` is clamped to zero.

The exact reference enumerates feasible joint allocations and all independent
next-state combinations, caching the finite-horizon Bellman recursion. It accepts
at most four students and three remaining months, with integer programme costs
and budgets. Future mentor resources may be supplied explicitly; otherwise the
current monthly resources repeat. It evaluates the actual production heuristic
at every hypothetical state, including solver tie choices, without future draws.

## Policies, randomness and waiting

- `wait`: no additional programme.
- `random`: shuffle eligible students in stable ID order with a local generator
  seeded by policy version, episode seed and current month. Mentor compatibility
  does not affect the student order. This is not uniform sampling of joint actions.
- `severity`: disengaged, vulnerable, stable, then student ID and cheaper mentor.
- `need_priority`: maximum initial shared-rule need severity, then the same ties.
  It does not use the evolving simulated condition or a fitted risk score.
- `longest_waiting`: elapsed full months before admission, then the same ties.
  All unserved survivors tie in this closed cohort because everyone enters together.
- `terminal_value`: monthly constrained terminal-retention benefit maximization.
- `fairness`: optional window-aware eager coverage, described below.

Waiting starts at zero and increments only after an unsupported month in which
the student remains enrolled. Admission and withdrawal stop the counter; neither
the admission month nor the withdrawal month increments it. Condition changes do
not reset it. Group audits apply the same rule within their assessment window.
Reports retain recipient waits separately from censored waits. Enrolled
student-months count enrollment after each monthly transition, excluding month zero.

Environmental draws use SHA-256 keys `(seed, student_id, month, event_type)`;
the random baseline uses its own local generator. Assignment counts/order do not shift
another student's draws. Zero-effect worlds therefore have identical full condition
trajectories across policies, not merely similar averages. Policies receive neither
the environment object nor future draws. Solver timings can vary on repetition;
statistical outcomes and assignments reproduce with the recorded dependency stack.

## Fairness auditing and optional constraint mode

Audits use only source sex and the existing disadvantage proxy. The latter is not
verified economic disadvantage. Comparable-need strata use the available condition
at assessment start and the fixed initial support type. Each group's eligible
cohort contains enrolled, unused students, independently of whether the current
budget can fund them. This prevents an exhausted budget from erasing unmet demand.

Freeze denominators at the start of each four-month window, including the shorter
last window if configured. Previously offered students are excluded from the new
window's eligible cohort. Subsequent withdrawals remain in the frozen denominator.
Count unique offers; in v1 every offer is accepted, fully delivered and completed.

The optional planner tracks prior offers in the current window and solves:

\[
\min\sum_g\xi_g/|E_g|,\qquad
\mathrm{priorOffers}_g+\sum_{i\in E_g,m}x_{im}+\xi_g\ge q|E_g|.
\]

It then maximizes retention benefit subject to the minimum shortfall. Groups are
weighted equally after normalizing by their frozen size. Source-sex and proxy
axes overlap and both contribute. Default `q=0.2` is an illustrative policy
assumption, applied only when fairness mode is requested. The hard resource
constraints always take precedence; no coverage promise overrides them.

This is an **eager, window-aware soft fairness heuristic**: it tries to close the
remaining window target now and remembers prior offers in later decisions. Actual
end-window shortfalls are independently recomputed from records. It does not
optimize a stochastic multi-month fairness schedule, reserve future window funds,
or guarantee zero shortfall. That stronger planner remains deferred. Small strata
and unequal needs require care; descriptive access rates are not fairness proofs.

## Observation interface and LLM boundary

`observe()` explicitly returns a fully observed benchmark. Ordinary partial-mode
snapshots use `observe(fully_observed=False)`: `condition` is `None` unless an
explicit current-month `ConditionEstimate` is supplied. Enrollment is assumed to
be a known administrative observation in both modes. Snapshots contain tuples of
frozen scalar records; no hidden condition map, source records or future events
are exposed. Retention and severity policies fail clearly if required estimates
are absent. Need, waiting and random policies can operate without hidden condition.

`observation_from_result(result, current_month)` accepts the existing validated
`InterventionResult`. A result becomes available only after its admission month.
It returns allowlisted reported outcomes as evidence and supplies no condition,
transition probability, risk reduction or outcome mutation method. A future
estimator must justify its evidence-to-condition mapping and emit explicit
`ConditionEstimate` records. No rule equates reported helpfulness with a causal
effect. The current experiment runner uses fully observed snapshots throughout;
LLM-driven closed-loop evaluation is not implemented.

## Assumptions register

| Assumption | Status and limitation |
| --- | --- |
| Both transition matrices, independence, absorption | Synthetic; no longitudinal school-withdrawal or causal-effect calibration |
| Alpha 0, 0.25, 0.5, 1 | Sensitivity scenarios, not empirical effect intervals |
| Initialization thresholds and participation inputs | Explicit synthetic assumptions; course failures are not withdrawal labels |
| Fixed primary need, equal effect by all support types | Reuses source need matching, does not estimate type-specific effectiveness |
| Five appointments, full uptake, admission-month delivery | No missed-session, incomplete-dose or refund model |
| One programme per student | Configured as `max_programmes_per_student=1`; other values fail with an extension message |
| Generalist mentors, capacities, unit prices, 150-unit budget | Synthetic resources and units; no actual local currency or verified prices |
| Exact administrative enrollment, oracle/explicit estimated condition | Benchmark and interface assumptions, not a validated observation model |
| Disadvantage proxy, source sex, illustrative q | Source-based audit context and configurable policy assumptions; no inference from notes |
| Monte Carlo worlds | Independent transition seeds on a fixed synthetic cohort; do not measure source-population or parameter uncertainty |

Programme history is a tuple of admission months to preserve a clean future
extension point. Repeated support, cooldowns, adverse/heterogeneous effects,
shared shocks, peer effects, learned observation models and globally optimal
multi-month allocation remain future work.

## Commands and output files

Use a project Python environment with `requirements.txt` installed. The project
declares Python 3.12–3.13. The available local `.venv` currently runs Python 3.14.8;
the executed checks passed there, but a supported-interpreter rerun remains an
environment verification item. No supported interpreter was installed here.

```sh
# Run all existing and new tests, with no live LLM.
.venv/bin/python -m unittest discover -s tests

# Focus on the CMDP tests.
.venv/bin/python -m unittest discover -s tests -p 'test_cmdp*.py'

# Default 100-student, twelve-month comparison; 10 development + 30 held-out seeds.
MPLCONFIGDIR=/private/tmp/cmdp-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-cache \
  .venv/bin/python -m src.main --output results/cmdp_v1/my_default_run

# Full effect-strength/budget sweep and optional fairness comparison: 2,240 episodes.
MPLCONFIGDIR=/private/tmp/cmdp-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-cache \
  .venv/bin/python -m src.main --suite full \
  --policies wait random severity need_priority longest_waiting terminal_value fairness \
  --output results/cmdp_v1/my_full_run

# A small CLI smoke run.
MPLCONFIGDIR=/private/tmp/cmdp-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-cache \
  .venv/bin/python -m src.main --development-seeds 1 --evaluation-seeds 1 \
  --output results/cmdp_v1/my_smoke_run

# Print initialization, every month and terminal results for WAIT-only.
MPLCONFIGDIR=/private/tmp/cmdp-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-cache \
  .venv/bin/python -m src.main --policies wait --development-seeds 1 \
  --evaluation-seeds 1 --print-monthly --output results/cmdp_v1/my_wait_run
```

Output destinations must be new; existing directories are never overwritten.
Omit `--output` to create a timestamped destination. Both `python src/main.py`
and `python -m src.main` work, as does the installed `school-dropout`
entry point. `--config` accepts another
versioned TOML matching `configs/cmdp_v1.toml`. Full-suite variations intentionally
use the specified effect strengths and budgets, while retaining other configuration.

Before Step 2 completion, each output included `manifest.json` with seeds, dependency versions, matrices,
population/code hashes; `episodes.jsonl` with complete per-episode metrics;
`sample_trajectories.jsonl` with the first development/evaluation world per policy
and scenario; `summary.json` with all paired baseline comparisons, monthly counts
and group audits; `tiny_exact.json`; `report.md`; and two standalone PNG plots.
The current baseline CSVs/figures and optional exact output are described below.
Each episode's `monthly_summaries` contains month zero and all realized months:
four condition counts, newly and cumulatively withdrawn students, enrollment,
retention/dropout rates, eligible students, programmes, appointments, monthly and
cumulative spending, remaining budget, mentor capacities/utilization and mean
waiting among enrolled, unsupported students. The latter is zero when none are
eligible; retention/dropout rates are `null` for an empty cohort. Month zero uses
the initial first-month mentor capacities with zero usage. The existing
`monthly_conditions` field keeps its months 1–T shape for compatibility.
`--print-monthly` prints the first development seed for each policy/scenario,
including its terminal result; full summaries are saved for every episode regardless.
Episode restart, terminal-only reward and SHA-256 keyed draws keep their existing
interfaces. Historical outputs retain their earlier waiting-time convention;
new results exclude the withdrawal month, so waiting metrics can differ while
retention trajectories and allocation choices remain reproducible.
Results directories follow the existing Git ignore convention; concise executed
findings are also preserved in [cmdp-results-v1.md](cmdp-results-v1.md).

## Step 2 baseline completion

The current default is the five-policy Step 2 comparison, using
`configs/cmdp_baselines_v1.toml` and timestamped `results/cmdp_baselines_v1/` outputs.
The numerical scenario is unchanged from Step 1. The commands above with explicit
paths and opt-in optimizer policies continue to work; the earlier six-policy
default and two-plot-only output description record the previous workflow.

`BaselinePolicy.rank_students` feeds `greedy_matching.assign_feasible` for all five
baselines. Matching preserves priority and chooses the cheapest feasible mentor,
then mentor ID; it does not maximize cardinality. Each paired world builds its
source school once and gives copied identical inputs to every policy environment.
`MonthRecord` additionally retains frozen student and recipient waiting counters.
Summarized condition trajectories now include month zero; the per-episode
`monthly_conditions` compatibility field remains months 1–T.

`--stage development` ends after development export; default `--stage both`
validates the development grid, resource ledgers, identical initial states and
full null-effect/zero-budget trajectories before any held-out episode. Failed
episodes are recorded and propagate, never repaired or silently omitted.
`summarize(episodes, manifest)` detects missing policies, worlds, scenarios and
duplicates. CSV exports add explicit episode identifiers, configuration hashes,
sample SDs, paired student-count/percentage-point intervals, waiting distributions,
pre-admission waiting, unit costs, resource diagnostics and descriptive group access.
Eight baseline figures supplement the two existing plots. See
[Step 2 details and executed results](cmdp_baselines_v1.md).

With the default seed, ten development seeds are 42–51 and thirty held-out world
seeds are 10042–10071. `--seed` sets the development start; held-out worlds start
at that seed plus 10000. Shared CLI flags (`--students`, `--mentors`, `--months`,
`--sessions`, `--capacity`, `--budget`, `--seed`) override only explicitly supplied
CMDP configuration fields. The recorded-workflow defaults do not replace values
from the CMDP configuration.
They are non-overlapping Monte Carlo partitions, separate from the repository's
student-record training/test split. Confidence intervals use paired episode-level
differences and Student's t distribution. They are pointwise and unadjusted for
multiple comparisons. The implementation performs no fitting or tuning on either
partition; solver validation fixes do not change effect or policy parameters.

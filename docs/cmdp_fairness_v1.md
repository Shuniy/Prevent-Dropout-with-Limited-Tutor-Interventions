# Step 4: fairness-constrained programme access

This benchmark extends the existing school CMDP with minimum admission coverage
among eligible students with comparable support needs. Terminal retention remains
the educational outcome. Fairness is an explicit coverage constraint with a
separate audit, never a demographic bonus inside the retention reward. The 30%
target is an illustrative research assumption, not a validated fairness standard.

## Definition, eligibility and provenance

The active audit dimension is selected explicitly in
[the versioned configuration](../configs/cmdp_fairness_v1.toml):

- `disadvantage_proxy`: the existing analyst-defined Boolean
  `disadvantage_proxy_count >= 2`, using low parental education, no home internet
  and a long commute. It is **not verified poverty or economic disadvantage**.
  Missing component inputs produce an unknown proxy. Missing verified financial
  need neither establishes affluence nor supplies this audit group.
- `sex_source`: the authorized structured source field, copied from the source
  bootstrap anchor. Only recorded F/M values are used; missing or unsupported
  values remain `unknown`. Names, dialogue, notes and generated language are unused.

See [the provenance register](references/audit_v1/provenance_register.csv),
`student_dataset` and `synthetic_student_population` rows for `sex_source`,
`disadvantage_proxy_count`, `disadvantage_proxy_group` and
`verified_economic_disadvantage`. Bootstrap copies are not independent population
observations. The older register's *simulator configuration* rows describe an older
weekly proposed model; this Step 4 configuration explicitly uses monthly decisions
and frozen conditions. No source/provenance data is rewritten.

Analyze one dimension at a time. The default experiment uses the disadvantage
proxy. Switching to source sex requires a separate named run and frozen config;
intersectional policy optimization is outside this version. The audit utility can
count overlapping supplied cohorts without duplicating actual admissions or costs,
but the configured optimizer uses a single partitioning axis.

At decision months 1, 5 and 9, freeze the enrolled, programme-unused students with
at least one compatible operational mentor slot announced within that window.
Shared budget affordability is not a cohort criterion: budget exhaustion must not
erase unmet demand. Compatibility reuses fixed support needs, mentor skills,
announced admissions/appointments and the existing programme eligibility rules.
Students with no compatible slot are excluded from the coverage denominator and
explicitly counted in the window history. Their retention is still reported in
the all-initially-enrolled group audit.

Need strata are the three broad conditions Stable, Vulnerable and Disengaged at
window start, obtained only through `fully_observed_benchmark`, the labelled oracle
observation interface. Support type controls compatibility, not stratification.
There are no 13-support-type subdivisions. Missing conditions and partially
observed snapshots cannot initialize this benchmark fairness policy. The group,
condition and denominator remain frozen through withdrawal, condition change,
admission and temporary mentor incompatibility. Each new window excludes students
already admitted in this episode. The last window is truncated for shorter horizons.
All nine possible group/condition cells, including unknown and empty cells, are
reported. No cells are suppressed; cells below 30 eligible students are flagged.

## Ledger and coverage constraints

[The ledger](../src/school/fairness_window.py) records window boundaries, immutable
cohort memberships, targets, distinct actual recipients, currently affordable
candidate IDs, uncovered withdrawals and outstanding obligations. It reconstructs access from the
student's committed `programme_months`; tentative schedules never enter history.
[The school coordinator](../src/school/cmdp_simulation.py) also maintains independent
window ledgers for *every* policy and records monthly before/new/after counters.

One START_PROGRAMME admission counts once per student. Five appointments are one
programme; v1 assumes full delivery in the admission month. The `unique_offers`
column remains only as a legacy alias for admissions. It does not identify a
separately measured offer or acceptance event.

For frozen cohort E[g,k,w], fractional target q and actual distinct access C:

```text
K[g,k,w] = ceil(q * |E[g,k,w]|)
C[g,k,w] + xi[g,k,w] >= K[g,k,w]
realized shortfall = max(0, K - C)                    [integer students]
normalized shortfall = max(0, K - C) / |E|           [nonempty cells only]
```

Decimal ceiling avoids floating-point boundary errors. Both q and K are exported.
Strict mode (`allow_shortfall=false`) fixes xi=0 by omitting the slack variables.
If the remaining-window model is infeasible, it reports `fairness_infeasible` and
executes WAIT. It never relaxes resources. Soft mode (`allow_shortfall=true`, the
recommended initial research mode) uses nonnegative **integer** slack variables.
Positive slack is a measured unmet target, not a minimum-coverage guarantee.

## Rolling MILP and objective order

[The fairness planner](../src/school/fairness_planner.py) extends the
[Step 3 planner](../src/school/constrained_planner.py) with tentative binary
`y[i,m,tau]` for each remaining decision month in the active window:

```text
sum_(i in E[g,k,w]) (h[i,w,t] + sum_(m,tau) y[i,m,tau]) + xi[g,k,w] >= K[g,k,w]
sum_(m,tau) y[i,m,tau] <= 1                         [one programme per student]
sum_i y[i,m,tau] <= admissions[m,tau]               [each month]
5 * sum_i y[i,m,tau] <= appointments[m,tau]          [each month]
sum_(i,m,tau) 5 * price[m] * y[i,m,tau] <= remaining episode budget
```

Historical admissions h contribute once and are ineligible for further allocation.
[The model extension](../src/school/window_optimization.py) reuses Step 3 candidate
generation, per-month resource rows, exact decimal/integer monetary accounting and
independent assignment validation. A separate validator checks each tentative
month plus global uniqueness and total budget. The environment independently
validates the current slice again before charging it. Monthly capacities reset;
only actual expenditure reduces the episode budget. Programmes have no configured
hour duration in v1, so the established `required_hours=0` rule remains applicable;
this version adds no invented hour or student effect model.

Both the window-wide budget row and its independent validator recompute exact
five-appointment costs from mentor prices. Rounded display floats in assignment
records are not used to establish tentative schedule affordability.

The hierarchy is fixed and recorded in the configuration comments and manifest:

1. Minimize `sum_(nonempty g,k) xi[g,k,w] / |E[g,k,w]|`. Every group/condition cell
   has coefficient one after normalization: a large group does not dominate solely
   through headcount. Empty cells carry zero weight.
2. Preserve that optimum within `1e-8` aggregate normalized units and maximize
   estimated incremental terminal retention across the tentative schedule.
3. Preserve retention within `1e-10` expected retained students and minimize cost.
4. Fix cost, then choose canonical month/student/mentor bits using the existing
   20-bit block convention. No arbitrary demographic or epsilon reward is added.

The total monthly solver limit is shared across all stages, using the Step 3
SciPy/HiGHS backend and zero relative MIP gap. Time-limited incumbents, incomplete
refinements and fallback failures have explicit statuses and are not labelled as
a completed optimal hierarchy. The last validated incumbent survives a failed
refinement. Strict infeasibility is a declared model result, not a solver fallback.

For q=0, or disabled fairness, the planner delegates **exactly** to the unchanged
resource-only planner, including its objective and canonical decisions. For
positive q, fairness may require zero-benefit or adverse-benefit admissions. Cost
minimization cannot undo the established fairness/retention objectives.

Only `assignments`, the current-month schedule slice, execute. The full
`tentative_assignments` schedule is disposable and reserves no future resources.
The next month replans after observing the new state. The immutable decision
snapshot adds only a preannounced mentor resource calendar; it exposes no future
student truth or keyed random draws. Without an announced calendar, the planner
uses only the current month, rather than inventing future capacity.

For offset d and current observed condition s, future benefits are projected as:

```text
Delta_now(s,h) = [(P_programme - P_wait) @ P_wait**(h-1) @ e][s]
Delta_hat(s,d,h) = sum_s' [P_wait**d][s,s'] * Delta_now(s',h-d)
e = [1, 1, 1, 0]
```

Immediate values use the existing estimator unchanged. Audit attributes never
enter either formula. The future value integrates possible WAIT conditions,
including absorbing withdrawal. Coverage planning nevertheless optimistically
keeps currently eligible students as potential future recipients. It is an
approximate deterministic schedule, not an optimal stochastic fair CMDP or a
realized coverage guarantee. Withdrawals can destroy a projected feasible plan.

Positive targets introduce this within-window timing model, while q=0 deliberately
preserves Step 3's monthly decisions. Differences versus Step 3 can therefore
reflect timing as well as binding coverage constraints. The planner does not
reserve funds for later windows: early-window retention optimization can exhaust
the episode budget. Window histories expose that consequence.

## Independent evaluation and experiments

[The auditor](../src/school/fairness_audit.py) recomputes unique admissions, integer
shortfall, shortfall rate, within-condition access gaps, mean/maximum waits and
waiting disparities from actual records. Empty rates are undefined (`null` in
JSON, blank in CSV), not zero. Gaps require at least two defined groups.
Waiting starts at the window boundary, counts full unsupported months, and is
censored at admission, the transition into withdrawal or window end. These are
censored descriptive waits, not a survival estimator.

Cell retention uses the frozen eligible cell as denominator and the episode's
final recorded condition. The additional group-retention table uses **all
initially enrolled students** by the selected audit attribute, including students
with no compatible mentor. Mentor workloads report programmes, appointments and
capacity utilization; the episode table adds the maximum-minus-minimum programme
count. Workload is audited without an additional optimization constraint.

[The experiment runner](../src/school/fairness_experiments.py) reuses Step 2/3 world
construction, `School.run_cmdp`, policy factories, independent episode validation,
keyed exogenous randomness and paired episode-level Student-t confidence intervals.
The same world is built once per scenario/seed for every compared policy. The
full grid is frozen before execution:

- Five baselines, resource-only, and q = 0, .1, .2, .3, .4 at budget 150, alpha=1.
- Resource-only versus q=.3 at budgets 0, 50, 150, 300, 500.
- Resource-only versus q=.3 at alpha = 0, .25, .5, 1 and budget 150.
- Ten development seeds 42–51; thirty held-out seeds 10042–10071. Duplicated
  default scenarios are run once: 25 settings × 40 worlds = 1,000 episodes.

Every development world must pass the frozen-grid, resource, identical-world,
zero-target allocation equality and null-effect trajectory checks before any
held-out run. Held-out targets are not selected from the outcomes. Confidence
intervals use episodes, not individual students, as independent replication units.
They are pointwise simulation intervals without multiplicity adjustment.

In addition to policy-specific q shortfalls, a `reference_normalized_shortfall`
column audits every policy against the common illustrative .3 target. Otherwise
q=0's trivially zero obligation would be misleading in a cross-target comparison.
The trade-off plot uses realized within-condition access disparity. Smaller gaps
are descriptive and do not establish equitable outcomes.
Later windows can contain different cohorts under different policies because
earlier admissions and transitions differ. Reported means weight defined cells
equally; they are not standardized to a common later-window population.

```bash
# Full frozen grid; choose a new destination to preserve previous runs.
python scripts/run_cmdp_fairness.py --output results/cmdp_fairness_v1

# Development-only smoke run.
python scripts/run_cmdp_fairness.py --stage development --development-seeds 1 \
  --output results/cmdp_fairness_v1_smoke

# Selected policies through the existing application entry point.
python -m src.main --config configs/cmdp_fairness_v1.toml \
  --policies terminal_value fairness --output results/cmdp_fairness_v1_custom

python -m unittest discover -s tests -v
```

The output includes all requested episode/month/group/shortfall/target/trade-off/
budget/effect/solver CSVs, the manifest and five PNG figures. Additional files
include monthly window histories, mentor workload, group retention, allocation
and trajectory hashes, sample trajectories, summaries and partition validation
records. `projected_vs_realized_coverage_gap` compares each window's first-decision
coverage forecast with its final actual admissions; it is signed and can be
negative if later replanning admits more students. Every monthly projected and
actual count is also available separately. Wall-clock runtimes need not reproduce;
allocations and outcomes reproduce with the recorded dependency stack.

## Scope and evidence

Minimum access coverage is not demographic parity, equalized odds, equal outcomes
or individual fairness. Frozen cohorts can be small, unknown-group information is
incomplete, the population is synthetic and intervention effects are assumed.
These simulation experiments establish no real-world intervention effectiveness
or equitable outcomes. No LLM feedback, estimated-state updates, RAG/QLoRA change,
new intervention effect, repeated programme or partially observed optimization
is implemented in Step 4.

See [the execution and acceptance report](cmdp_fairness_v1_results.md) for the
actual test counts, 30-seed comparisons, sensitivity results and all 22 acceptance
criteria. Prior Step 1–3 results remain in their original locations.

# Step 3: constrained terminal-retention allocation

The planner reuses the CMDP environment, five baseline policies, paired experiment
runner and `School.run_cmdp(policy, config=...)`. Simulation does not change source
student measurements or recorded intervention outcomes. The fully observed
benchmark sees current conditions and resources, never future random draws.

## Mathematical formulation

The complete CMDP state contains joint student conditions, remaining budget,
programme histories and mentor resources. Its terminal reward is the number of
initially enrolled students who have not withdrawn after the final transition;
intermediate rewards are zero. Withdrawal is absorbing. The condition component
alone has `4**100` states for the default cohort, making exact full-cohort dynamic
programming impractical.

Use state order Stable, Vulnerable, Disengaged, Withdrawn and `e = [1, 1, 1, 0]`.
With `h` remaining transitions, including the current month:

```text
V_wait(h) = P_wait**h @ e
Delta(h)  = (P_programme - P_wait) @ V_wait(h - 1), h >= 1
P_alpha   = P_wait + alpha * (P_programme - P_wait)
```

Horizon zero returns `e`. Matrices and horizons are validated. Backward propagation
and a cached table share calculations across all twelve decision months. The
configured effective programme matrix is used, including the zero-effect case.
The estimator also supports negative benefits with an explicitly supplied adverse
transition matrix.

Both action values assume WAIT in every subsequent month. This is a rollout
benefit, not an optimal action advantage. Monthly replanning does not price the
opportunity cost of spending today or optimize later intervention opportunities.
Withdrawal risk, need severity, mentor preference and source course-failure
probability are distinct from estimated intervention benefit.

One binary variable `x[i,m]` represents each eligible, compatible student–mentor
pair with positive benefit. Nonpositive-benefit programmes are excluded even if
free. A programme delivers all five appointments in its admission month, following
the existing scenario contract.

```text
maximize sum Delta_i * x[i,m]
subject to:
    sum_m x[i,m] <= 1                             for each student
    sum_i x[i,m] <= available admissions_m        for each mentor
    5 * sum_i x[i,m] <= available appointments_m  for each mentor
    sum 5 * price_m * x[i,m] <= remaining budget
```

The existing 13 support types and compatibility rules are retained. Only enrolled
students without programme history qualify. Initially non-enrolled students are
excluded from the retention cohort. No session duration is configured, so legacy
zero-hour fields impose no extra hour constraint in this appointment-only model.

## Solver, ties and failures

SciPy `optimize.milp` / HiGHS solves a documented hierarchy:

1. Maximize incremental terminal retention.
2. Preserve that objective within an absolute tolerance of `1e-10` expected
   enrolled students and minimize programme expenditure.
3. Fix minimum expenditure, then lexicographically prefer selected pairs in
   `(student_id, mentor_id)` order. Twenty-bit integer-weight blocks are solved
   and fixed successively. This produces a unique canonical assignment without
   cohort-sized exponential weights or arbitrary programme-selection bonuses.

The objective tolerance is many orders below the simulation's Monte Carlo
precision. Each refinement is independently checked against the retained benefit
and expenditure bounds. Input ordering cannot change the canonical allocation.

The default total monthly solve limit is ten seconds across all stages, with
zero relative MIP gap. A feasible primary incumbent without proof is
`feasible_limit`. Missing incumbents, infeasible models, numerical failures,
invalid incumbents and unexpected errors have explicit statuses. Experiment
configuration defaults to `planner_failure_mode = "raise"`; explicitly setting
`"wait"` enables a logged empty-allocation fallback. Direct planner construction
retains that existing fallback default for compatibility.

If cost or tie refinement fails, the last validated incumbent is retained with
an incomplete-stage status and `lexicographic_complete = false`. Such a result is
not reported as a completed optimal hierarchy. No policy call mutates resources
or student state. Optimality always concerns the monthly model, not the full CMDP.

## Exact accounting and execution

Monetary inputs are interpreted as exact decimal scenario units using their string
representations. The environment carries a Decimal ledger and exposes both the
existing float budget and its exact decimal value in the immutable observation.
Programme costs are independently recomputed from mentor appointment prices.

Solver costs are integer multiples of their greatest common divisor; available
budget is floored to that expenditure unit. This is exact because every achievable
expenditure is a multiple of that unit. Integer coefficient ranges exceeding exact
solver precision fail visibly. The independent validator compares decimal sums
without a financial tolerance. There is no negative-balance clamp. Compatibility
discovery does not use floating-point affordability.

Every month observes, plans, independently validates, commits budget and programme
history, then samples one transition per student using the existing keyed draws.
Unsupported survivors accumulate waiting time. Mentor capacities renew monthly;
budget and programme histories persist. Null-effect and zero-budget decisions
match WAIT-only trajectories.

## Tiny exact reference

`ExactTinyMDP` enumerates feasible joint actions and complete joint next-condition
probabilities. Memoized Bellman recursion tracks conditions, programme-used flags,
budget and month under the same eligibility, compatibility and resource rules.
The reference supports up to four students and three remaining transitions with
integer budgets and programme costs. Future resources repeat current resources
unless an explicit schedule is supplied. The production heuristic is also
evaluated by exact transition enumeration, rather than sampled trajectories.

Five exported scenarios vary budgets, conditions, horizons, mentor prices and
compatibility. They include a real counterexample: two stable students, three
months and one funded programme. The exact policy initially waits while the
heuristic intervenes. Outputs include both values, absolute and relative gaps,
complete first actions, expected and first-month expenditure, runtimes and cached
state counts. Expected expenditure integrates all future transition outcomes.

## Commands and outputs

Use the project's configured Python environment and existing dependencies. The
six-policy command explicitly selects the new planner, preserving Step 2's
five-baseline default. Existing result directories are never overwritten.

```sh
.venv/bin/python -m unittest discover -s tests

.venv/bin/python -m src.main --config configs/cmdp_planner.toml \
  --policies wait random severity need_priority longest_waiting terminal_value \
  --suite full --output results/cmdp_planner_v1/my_run
```

The full sweep uses alpha 0, 0.25, 0.5 and 1 at budget 150, plus budgets 0, 50,
300 and 500 at alpha 1. Six policies, ten development seeds and thirty independent
held-out seeds produce 1,920 episodes. Development validation precedes held-out
execution; policy configurations are frozen and never tuned on held-out outcomes.

Shared outputs include policy, episode, monthly, budget and effect CSVs; complete
JSONL episode metrics; representative trajectories; paired episode-level Student-t
95% intervals; a report; and retention, spending, utilization and sensitivity
figures. Step 3 adds:

- `benefit_by_condition.csv`: four conditions, twelve horizons, four alphas.
- `solver_diagnostics.csv`: every planner month, including empty allocations,
  counts of candidates/variables/eligible students/available mentors, remaining
  budget, horizon, objective, spending, runtime, gaps, statuses, validation failures,
  solver settings.
- `tiny_exact_comparison.csv` and `.json`: all five exact comparisons.
- `figures/terminal_retention.png`, `benefit_by_horizon.png`, `solver_runtime.png`.
- `experiment_config.json` and `manifest.json`: seeds,
  matrices, solver settings and source hashes.

Episode metrics also record maximum monthly runtime, total estimated benefit,
appointments, unused budget, waiting, mentor utilization and withdrawals. Monthly
outputs show when budget is spent. Episodes, not students sharing resources,
are the independent statistical repetitions.

## Assumptions and limits

Transition probabilities and effects are synthetic assumptions, not causal
estimates. All programme types share one effect matrix. Mentor resources and
prices are synthetic. Support is limited to one programme per student, with full
uptake in the admission month. This fully observed Step 3 implementation adds no
fairness constraints, language extraction, RAG or LLM feedback. Existing optional
modules remain separate.

The monthly heuristic can perform worse than a severity baseline or an exact
dynamic policy. Monte Carlo intervals condition on the model and fixed synthetic
cohort. They do not quantify real-world causal uncertainty or establish that
school dropout would be reduced.

Executed checks and experiment findings are recorded in
[Step 3 results](cmdp_planner_v1_results.md).

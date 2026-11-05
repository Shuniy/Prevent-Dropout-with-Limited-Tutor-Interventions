# Research evaluation protocol v1

Frozen before the first Step 6 development/held-out research execution on 2026-11-06.
The executable settings are [research_evaluation_v1.toml](../configs/research_evaluation_v1.toml).
The runner records this document, configuration and source SHA256 in its immutable manifest.
Changes after held-out inspection require an appended amendment; never rewrite the original manifest.

## Questions, hypotheses and priorities

RQ1: How do incomplete, delayed, misleading and contradictory language-derived
observations change beliefs, WAIT-continuation withdrawal risk, assignments,
simulated retention and comparable-need access? RQ2: Does finite-scenario robust
fair allocation improve the effectiveness/equity trade-off? RQ3: What differences
come from unavailable observations, note corruption, extraction, estimation and
optimization respectively? The directional hypothesis is that robustness can help
under group-dependent information errors, but loss or no detectable change are
valid findings. No algorithmic novelty or real-world causal claim is prespecified.

The PRIMARY contrast is FairRobust minus FairPoint on terminal month-12 retention
rate in group-dependent noisy note-supported observations (D-matched), 30 paired
world seeds 1000–1029. Both receive exactly the same initial authorized information
and exogenous streams. After different actions, each creates observations from its
own trajectory. D-matched uses exact note-supported facts, not an LLM. It is the
computationally feasible uncertainty-optimization experiment; actual LLM extraction
is independently benchmarked and exercised in a separately labeled sparse C/D
secondary comparison. The primary experiment alone does not identify LLM error.

Key SECONDARY outcomes, in order: summed normalized frozen-cell minimum-coverage
shortfall; maximum comparable-need access gap; worst nonempty cell access;
waiting-time disparity. Report all alongside retention. A superior trade-off
requires positive retention evidence and no adverse fairness evidence; descriptive
means alone do not establish superiority. No equivalence claim from an interval
containing zero. Report operational magnitude in percentage points and students.

## Simulator and information conditions

Reuse existing synthetic enrolled source-prefix cohort, initial-condition mapping,
mentor generation, four-state WAIT/programme transitions and alpha interpolation.
100 students, two mentors, 12 transitions, budget150, five appointments/programme,
10 admissions and50 appointment slots per mentor/month. The 10/50 capacity matches
the Step6 brief and ScenarioConfig defaults; Step5's sparse 1/5 runs differ.
Population is a fixed source-prefix cohort across seeds, so episode replication
covers stochastic transitions/observations, not independent sampled populations.
Programme alpha1, at most one programme/student. Fixed needs and authorized
disadvantage_proxy groups come from source records, never note inference.

Oracle has current truth only, no future draws. Structured B uses all available
model records. B-matched contains only ordinary note-supported facts. C extracts
those exact notes with existing real Qwen/strict evidence validation. D extracts
corrupted notes. D-matched exposes exactly D's supported facts, preserving source,
content, provenance, event and availability timestamps. Structured observation
missing=.05, delay=.10, misleading=.05 remain as declared Step5 assumptions.
Ordinary notes omit=.10. Primary False group has note omission=.10, conflict=.10,
misleading=.05, delay=.10; True has .40/.20/.10/.25. Unknown group uses False rates.
These are synthetic assumptions, not empirical group measurements. Note loss is
also accompanied by ambiguity, negation of assignment difficulty, and partial
reporting, each with probabilities .05 for False and .10 for True. Precedence is
ambiguity, applicable negation, then partial reporting, after omission/misreporting;
conflict insertion and delay are independent keyed mechanisms.
These declared corruption mechanisms do not change latent simulator truth. Loss is
in addition to observation-model missingness. Contradictions remain unresolved;
unknown and explicit no-contact are different observations.

Information-mode comparisons hold FairPoint fixed. Compare oracle/B/B-matched/
D-matched in five held-out seeds. Real C/D comparison is limited to seed1000,
one rotating note/month, paired sparse B-matched and D-matched controls, both
FairPoint/FairRobust: it is a low-precision feasibility/propagation diagnostic.
Do not compare sparse C directly to full-note B-matched to identify extraction
error. Frozen observed eligibility is enrollment/no prior programme/compatibility;
need strata use MAP >=.6, otherwise uncertain. Denominators freeze per four-month
window within each trajectory. Export memberships and expose cross-mode differences.
Minimum access .2, equal-cell normalized shortfall weights, hard resources shared.

## Methods and uncertainty set

Reuse monthly rolling-window fairness MILP. Lexicographic objectives: minimize
sum cell slack/denominator, maximize benefit, minimize exact cost, canonical bits.
FairPoint uses b(P_programme-P_WAIT)P_WAIT^(h-1)e, e=(1,1,1,0).
FairRobust maximizes eta with eta <= sum_i,m Delta_i,k x_i,m for every finite
scenario k. It is a robust rolling heuristic, not an exact POMDP solution.
Only current-month assignments execute. Forecast enrollment remains optimistic.

Uncertainty is declared synthetic, not empirically calibrated. Nominal plus up to
four scenarios shift the documented or poorly documented subset separately toward
the enrolled state with minimum/maximum current-horizon model benefit. Poorly
documented means missing current signal or positive observation age. Other subset
beliefs remain nominal. Mix rho_i=min(1,radius * missingness_multiplier_if_missing *
(1+min(age,3)/3)); radius=.25, multiplier1.5. No observation defaults age3.
Mixes are valid distributions, preserve known withdrawn mass and do not access
truth. Oracle point states stay exact. Record construction and parameters.
Zero-radius ablation deliberately ignores uncertainty; .1/.5 test sensitivity.
This set covers selected reliability regimes, not all arbitrary joint state errors.

Use SciPy/HiGHS existing tolerances: MILP mip gap0, fairness tolerance1e-8,
benefit tolerance1e-10 (actual code setting recorded in manifest), ten-second total
monthly solve deadline, deterministic canonical ties. Record exact versions,
statuses, incomplete stages and fallbacks. Feasible incomplete solutions remain
explicit; no silent infeasibility or constraint relaxation.

## Stages, separation and controls

First regression-test Steps1–5. Freeze protocol/configuration. Run ten development
seeds0–9 for correctness/runtime checks, with no held-out tuning. Gate primary on
unit tests and development feasibility. Execute primary before secondary analyses.
Five held-out secondary seeds1000–1004 support bounded missingness(0,.1,.25,.4),
budget(50,150,300), alpha(0,.25,.5,1), radius(0,.1,.25,.5) sweeps and ResourceOnlyPoint
fairness ablation. Shared default cells reuse already executed trajectories.
At alpha0 assert exact entire truth-trajectory equality across allocation policies
under keyed draws. Repeated runs and reversed policy order must reproduce actions,
beliefs, resources and truth (exclude wall-clock timing). Independent extraction
benchmark protocol freezes before live inference and records lineage/template
separation limitations. No human annotation or confidence calibration is claimed.

## Scoring and inference

Replication unit is episode seed, not student. Paired Student-t95% intervals use
sample SD(ddof1)/sqrt(n), report n, raw means and differences in percentage points.
Insufficient n gives no interval. Secondary/subgroup/sensitivity comparisons are
exploratory without multiplicity-adjusted confirmatory claims.

Belief multiclass Brier is mean(sum_s(b_s-onehot_true_s)^2), range0–2; also accuracy,
confusion, clipped NLL, entropy, missingness and observation age, by group/cutoff.
Risk target is P(terminal withdrawal | current belief, WAIT continuation). Score
against evaluator's exact current-state WAIT matrix reference q, not actual treated
outcomes. Report probability MSE and expected Bernoulli Brier/logloss under q,
reliability plots and binned errors. Fractional q is not an observed binary label;
no empirical AUC is claimed. State scores evaluate actual operational oracle
point masses rather than the oracle controller's unused filter.

Static snapshots use the same world/cutoff/feasible set, separate fresh planners,
and no later re-use of notes across trajectories. Report selection/mentor overlap,
priority rank correlation (average ties), eligibility and benefit changes.
Failure selection is deterministic: largest negative policy difference, largest
belief error, extraction omission/conflict and observed fairness shortfall where
present, preserving full event-note-facts-belief-benefit-action-outcome traces.
Do not label an intervention unnecessary solely from later withdrawal.

## Interpretation and validity

Report primary estimate regardless of sign. Wide intervals are inconclusive,
not equivalence. Narrow Monte Carlo intervals do not validate causal dynamics.
Withdrawal is simulated, source course failure is not dropout, transition effects
are assumptions, risk differs from treatment benefit, access differs from outcome
parity, and oracle is an approximate planner diagnostic. Exact grammar extraction
cannot establish performance on unrestricted real mentor prose. Sparse real-LLM
closed-loop comparisons cannot replace full-cohort multi-seed C/D evaluation.
Resource limits and failed inference are recorded as incomplete acceptance items.

## Amendments

None at initial freeze. Any subsequent dated amendments are appended here and
copied to a separate run amendment file without replacing the frozen protocol.

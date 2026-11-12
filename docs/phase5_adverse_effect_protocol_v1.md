# Phase 5 adverse-effect follow-up v1

Frozen on 2026-11-13 before any outcomes from this follow-up. This corrects the
v1/v2 protocol's statement that adverse effects are unsupported. The existing
weekly contract accepts explicitly supplied valid absorbing transition matrices;
an adverse matrix does not require a new simulator. Delayed and individually
heterogeneous causal effects remain outside the current implementation.

This is a separate exploratory stress test, not an amendment to the executed
primary estimate or a new model-selection opportunity. Keep the completed v2
study and its matching source archive unchanged. Use the same source-test cohort
of 48, population seed 55000, two mentors and group-dependent F/M documentation
condition. Use worlds 2000–2004, already declared as secondary worlds in v2.

Compare WAIT, FairPoint and FairRobust. The usual-support matrix is unchanged.
Set effect strength to one and supply this deliberately assumed tutoring matrix:

```
             stable  vulnerable  disengaged  withdrawn
stable        .968      .025        .004        .003
vulnerable    .040      .890        .050        .020
disengaged    .010      .040        .870        .080
withdrawn     .000      .000        .000       1.000
```

Relative to usual support, withdrawal probability increases in each enrolled
row, paid for by the same row's diagonal probability. Actual delivered service
alone selects the adverse matrix. Notes and predictions do not change effects.
Existing uptake, delivery, cancellation, schedules, budgets, eligibility and
soft offer-fairness rules remain intact. Fairness goals may therefore conflict
with retention in this artificial world; no real-world effect claim follows.

Record raw four-layer scorecards and world-level paired retention, worst-group
retention, normalized shortfall, offer/completion rates and costs versus WAIT.
Report all five pairs, regardless of direction. These are exploratory intervals,
with no confirmatory or equivalence claim. An optional positive-world trained
model must abstain on the changed reference law; no new model is fitted here.
Save full matrices, protocol, provenance, ledgers, outcomes and exact replays in
a separate immutable directory. The v2 primary protocol and results are not
overwritten or relabelled.

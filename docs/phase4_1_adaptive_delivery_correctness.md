# Phase 4.1 adaptive delivery protocol, version 1

Amendment to `phase4_delivery_protocol_v1.md`, dated 2026-11-09. The original
protocol and monthly contracts remain historical records. New episodes use
`scheduled_weekly/replay/v2` and `scheduled_weekly/policy/v2`. The synthetic world,
event accounting, observation validator and fairness priorities retain v1 meanings.

## Adaptive support

At every cutoff every active accepted programme is valued from the current
estimated belief. Continue means its remaining RESERVED sessions, not a second
offer. Cancellation means no future effects from that programme. Forecasts use
attendance times delivery probability, and carry joint active/inactive mass
through programme-level cancellation before service; acceptance is one for an
already accepted programme. Historical delivery is represented in the belief.

Let C be expected incremental terminal retained students from remaining sessions.
Let V(R) maximize the minimum scenario aggregate benefit of feasible new full
programmes starting strictly after today's cutoff, with fixed public resources R,
current beliefs, and continued eligibility assumed. Opportunity O is
max(0, V(R with this programme released) - V(R)). Cancel only if O > C + .001,
fresh genuinely new condition evidence was successfully assimilated, the programme
is at least one week old, and both opportunity solves prove optimality. Otherwise
continue. The configurable .001 margin has units of expected terminal retained
students and is an assumed continuity tolerance, not an estimated effect size.
It prevents numerical ties/churn. Sequential canonical reviews consume the
hypothetical release once; a failed solve preserves support. No evidence means no
new cancellation recommendation. Naturally changing horizon values remain visible.

Random, priority, point and fair point share nominal continuation and opportunity
valuation; their new-offer rules retain their original differences. Fair robust
uses the same reviews and feasible actions, its declared scenarios, robust V,
and the largest C across scenarios as a conservative continuity protection.
WAIT makes no offers or cancellations and honors accepted obligations if supplied
externally. Cancellation does not change historical offers, delivery or spending.
Actual offers always use the unreleased ledger: released capacity is usable only
after cancellation is executed and independently validated, at a later cutoff.
Fairness priority applies to new-offer optimization; opportunity valuation itself
uses retention, not a shadow price claiming to encode fairness.

## Information-sensitive uncertainty

Reuse the monthly `UncertaintyScenarioConfig` assumptions: base radius .25,
missingness multiplier 1.5, freshness three protocol months = twelve weeks.
For source age a = cutoff - 1 - latest successfully assimilated source, define
rho = min(1, base * 1.5^missing * (1 + min(a,12)/12)). With no assimilated
source use age twelve. Missing refers to the previous interval; relevant conflict
or rejected measurement also sets missing. Duplicate evidence never refreshes
source time or counts as new. Entropy is recorded for audit but is not combined
with the uncalibrated mixture radius as though it were another independent error.
All students, including active recipients, receive immutable cutoff/estimate-linked
uncertainty records with clipping and fallback information.

Scenarios are nominal plus low/high enrolled-state mixtures shifting one of the
fresh and missing/stale documentation subsets at a time. Preserve known withdrawn
mass. Endpoints use current-start marginal benefit; the same student belief is
shared across all mentors/start weeks within a scenario. This solves a finite
scenario max-min aggregate expected benefit approximation, not full rectangular
min-max optimization or a stochastic CMDP. Zero radius reduces to nominal values.
New-offer order remains normalized fairness deficit, benefit, exact cost, canonical
bits. Uncertainty does not imply guaranteed allocation changes or robust superiority.

## Risk targets

`WeeklyRisk.probability` retains usual-support terminal non-enrollment semantics.
`WeeklyCommittedRisk` is a separate versioned target under continuation of known
accepted schedules and no new offers, using the same current estimate identity.
The expected-delivery operator splits active and inactive state mass, transfers
cancellation mass once per week, and mixes tutoring/usual transitions only in
remaining session weeks. It never reads future attendance draws. Cancelled,
completed and missed past sessions add no future effect. Calibration must be
evaluated separately against the specified reference regime.

## Frozen fairness feasibility

Keep all frozen eligible students. Independently optimize a joint full-calendar
reservation packing at each window's initial snapshot. Report maximum unique
offers, minimum total count shortfall, and a single jointly feasible cohort witness.
The shortfall bound minimizes count deficits; it does not change the policy's
normalized-cell fairness objective. Fix existing commitments, current eligibility
and budget; assume no future cancellations, refusals or withdrawals. Thus these
are conditional feasibility results, not guaranteed realizable coverage and not
an assertion that a later dynamic policy failed. Additional realized shortfall is
max(0, actual count shortfall - minimum model shortfall). Report nonoptimal solves
without inventing exact bounds. No-carryover terminal windows may have zero starts
despite a nonempty denominator. Completion remains in the original offer cohort.

## Reproducibility and compatibility

The v1 artifact reader verifies seals and identities. Exact replay of old episodes
requires the original source/dependency fingerprints; use that archived checkout
and runtime. V2 execution preserves the same strict source/runtime guards, records
reviews, uncertainty, both risks and resource events, and verifies every prefix
ledger. Replay also independently regenerates the saved summary, including risk
labels and joint fairness bounds; a consistent integrity seal alone does not
prove those scientific quantities correct. No historical output is overwritten.
Offline CI uses synthetic inputs and no external inference. This document states assumed mechanisms, not calibrated
educational effects or evidence of statistical policy superiority.

## Root causes and implementation changes

The original `WeeklyDeliveryPolicy.plan` produced offers without invoking the
existing cancellation action. Notes could change an active student's belief but
could not change their remaining support. Robust values used one global .25
mixture; successful assimilation, missingness and conflicts did not affect it.
The controller supplied only WAIT-matrix terminal risk, even with accepted future
sessions. Fairness reported realized deficits without a joint calendar bound.
CI ran tests but neither produced retained acceptance episodes nor replayed them.
Additionally, initializing a controller after delivery omitted past delivered
actions; initializing with explicit known actions now preserves those transitions.
Repeated preparation at the same cutoff retains the same new-evidence audit,
while duplicates at later cutoffs do not become new measurements.

| File | Revised responsibility |
|---|---|
| `src/school/delivery_forecasts.py` | Pure joint active/inactive forecast and separate typed committed-support risk |
| `src/school/delivery_uncertainty.py` | Monthly-assumption adaptation, student audit records, coherent subset scenarios |
| `src/school/delivery_reassessment.py` | Continuation gains, joint replacement opportunity, continuity protections |
| `src/school/delivery_policy.py` | Shared review action space and scenario-aware allocation, original lexicographic order |
| `src/school/delivery_contracts.py` | Immutable review/uncertainty records on actions and decision contract v2 |
| `src/school/delivery_controller.py` | Genuine assimilation provenance, relevant conflicts, quarantine, cutoff idempotence |
| `src/school/delivery_environment.py` | Matching public forecasts and explicit observation-model configuration |
| `src/school/state_estimator.py` | Optional known actions at initialization; unchanged monthly default |
| `src/school/delivery_fairness.py` | Exact joint cardinality and count-shortfall optimization with one cohort witness |
| `src/school/delivery_experiments.py` | Sealed v2 episodes, verified v1 reader, independent regenerated summaries |
| `src/school/delivery_acceptance.py` | Reproducible single-fact counterfactual, negative controls, four matched information/policy conditions |
| `tests/test_delivery_adaptive.py` | 33 new regressions and independent finite-instance checks |
| `requirements-offline.txt`, `.github/workflows/offline-tests.yml` | Frozen offline dependencies, Python 3.12/3.13 test matrix, 3.12.12 acceptance and artifact upload |
| `README.md`, this amendment, `phase4_1_acceptance_results.json` | Reproduction commands and retained measured evidence |

## Mathematical specification

With usual matrix W, tutoring matrix T and q = attendance * delivery, set
M_w = qT + (1-q)W in remaining session weeks and M_w = W otherwise.
For accepted programmes start A = identity, I = zero; for a new offer use
A = acceptance * identity, I = (1-acceptance) * identity. At each forecast week,
transfer D = c_w A to inactivity, then update A = (A-D)M_w and I = (I+D)W.
Here c_w is the declared cancellation probability after the offer week until
the last remaining scheduled session, zero otherwise. This preserves survival
dependence across sessions. Neither attendance nor cancellation is sampled.

From the same current belief b, usual risk is b W^(H-t+1) e_withdrawn and committed
risk is b(A+I)e_withdrawn. Nominal continuation value is their difference. Robust
continuity protection uses the maximum continuation value across declared
scenarios; replacement V uses the minimum scenario aggregate benefit. Both retain
units of expected terminal retained students. The hypothetical release changes
future slots/caseload and outstanding liability, never actual spending.

For new-offer assignments j and scenarios s, optimize eta subject to
eta <= sum_j delta_js x_j, with original full-future-resource binary packing and
frozen fairness constraints. Nominal point uses one scenario. The preceding
normalized-cell-deficit priority and following exact-cost/canonical-bit priorities
are unchanged. Independent enumeration tests compare this precise finite-scenario
objective with the selected schedule, not a claimed rectangular robust optimum.

For each frozen group/need cohort c, K_c = ceil(target * N_c) under the existing
required-access rule. The fairness diagnostic separately maximizes unique selected
students and minimizes sum_c max(0, K_c - covered_c), under joint resources. It
then maximizes unique coverage at that minimum deficit to provide a shared witness.
Independent feasible-subset enumeration verifies the bounds on tiny instances.
The policy itself retains its different normalized deficit objective.

## Executed counterfactual

The bounded fixture has three students, one mentor with one weekly slot and one
concurrent student, budget 11, eight weeks, five sessions, certain acceptance and
delivery, and no exogenous cancellation. Weekly transition/effect assumptions
remain `synthetic_weekly_v1`, strength one. All initial monitoring notes share the
same controlled low-participation report. Only student `fictional-00`'s source-week
1 note differs, available at cutoff 2. These are controlled noisy information
conditions; they are not oracle condition labels. The separate accurate comparison
uses unmodified authorized synthetic emissions, extracted without note corruption.

Initial truth, notes/history before the changed observation, mentor calendar,
accepted week-1 programme, resource ledger, seed 41, policy and estimator are
identical. Both remaining students are eligible at cutoff 2. Every changed fact
passes the actual controlled-language schema, evidence-span validator and filter.
Beliefs are ordered stable, vulnerable, disengaged, withdrawn.

| Executed quantity at cutoff 2 | Regular participation | Low participation |
|---|---:|---:|
| Posterior stable | .4501433264 | .0495271653 |
| Posterior vulnerable | .3448643523 | .2223683871 |
| Posterior disengaged | .2049923213 | .7281044476 |
| Posterior withdrawn | 0 | 0 |
| Usual-support non-enrollment risk | .0816230027 | .1821499354 |
| Committed-support non-enrollment risk | .0530234138 | .1176639765 |
| Remaining continuation value | .0285995889 | .0644859589 |
| Released-capacity opportunity | .0709601194 | .0709601194 |
| Fixture continuity margin | .01 | .01 |
| Decision | cancel | continue |
| Subsequent alternative offer | week 3 | week 4 |
| Total delivered to original recipient | 1 | 2 |
| Total delivered to alternative recipient | 5 | 5 |
| Actual episode expenditure | 6.2 | 7.2 |
| Terminal retained | 3/3 | 3/3 |

The low-participation arm is reassessed again with genuinely new later information;
continuing at cutoff 2 does not guarantee continuation forever. In the regular arm,
cancellation releases four remaining service liabilities. Spending stays 1.1 at
that cutoff and the original offer/delivered session remain recorded. New offers
cannot borrow the release in the cancelling action. At cutoff 3 the independent
validator approves the alternative's full five-week reservation.

The negative control compares the insufficient-evidence sentence with the same
sentence plus unsupported follow-up prose. Both yield posterior
(.1620112904, .3127831225, .5252055871, 0), continuation value .0517680302,
no new usable condition signal, and the same complete decision history. Hidden
trajectories are checked against the actual delivered-week transition and matching
keyed uniform draw, without using note claims as outcome labels. The unchanged
terminal reward in the two positive arms is an observed result, not omitted evidence.

The four fair-point/fair-robust by accurate/stale-missing conditions use paired
seeds 41 and 42 with identical world/observation assumptions. At cutoff 2, recent
usable evidence gives radius .25; retaining only source-week 0 gives .40625.
For seed 41 the active student's nominal continuation value changes from
.0644859589 to .0517680302; robust protected continuation changes from .0680381804
to .0627070487. The discrete offers agree in this small comparison. Values and
uncertainty respond to information quality; these examples establish no robust
retention advantage. Full per-cutoff estimates, risks, reviews, actions, service
events and true synthetic outcomes are in the generated sealed acceptance report.

## Verification record and commands

Executed locally on CPython 3.12.12 with the 25 exact dependency versions in
`requirements-offline.txt`. The pre-edit revision
`7cf26d07246216573e4c779f3dc8369455bd1436` passed all 393 tests in an isolated clean
checkout (100.720 seconds). Four initial new reproductions failed because the
review, uncertainty audit, committed risk and feasibility interfaces were missing.
The existing 43 delivery tests passed before edits. An exploratory run in the
pre-existing Python 3.14 environment correctly failed supported-runtime provenance
checks; that environment was not used for acceptance.

Final revised execution: 426/426 full-suite tests passed (95.931 seconds),
76/76 delivery tests passed (2.764 seconds), and 116/116 Phase 1–3 named regressions
passed (52.907 seconds). There were no final test failures. Tiny robust/fairness
instances proved optimal and matched independent feasible-subset enumeration.
Nonoptimal opportunity solves are tested to preserve existing support.
All twelve acceptance episodes completed exact replay, including independently
regenerated summary diagnostics. Every executed offer and every historical resource
prefix passed the unchanged independent validators. The original v1 episode was
also generated and replayed exactly in the archived original checkout, then read
and seal/identity-verified successfully with the revised v1/v2 reader.

Reproduce from a repository checkout using a supported interpreter:

```sh
python3.12 -m venv /tmp/school-phase41
/tmp/school-phase41/bin/python -m pip install -r requirements-offline.txt
MPLCONFIGDIR=/tmp/school-phase41-mpl /tmp/school-phase41/bin/python -m unittest discover -s tests -p 'test_phase*.py'
MPLCONFIGDIR=/tmp/school-phase41-mpl /tmp/school-phase41/bin/python -m unittest discover -s tests -p 'test_delivery_*.py'
MPLCONFIGDIR=/tmp/school-phase41-mpl /tmp/school-phase41/bin/python -m unittest discover -s tests
/tmp/school-phase41/bin/python -m src.school.delivery_acceptance --output results/phase4_1_fresh_run
/tmp/school-phase41/bin/python -m src.school.delivery_experiments --replay results/phase4_1_fresh_run/regular --output results/phase4_1_fresh_replay
git diff --check
```

Use new output names on repetition. The local executed interpreter was
`/tmp/phase41-venv/bin/python`; commands and counts are retained in the small
source-controlled `docs/phase4_1_acceptance_results.json`. Complete synthetic
artifacts can be regenerated by the acceptance entry point; CI retains those
episodes and logs as artifacts. GitHub CI is configured but has not been run or
claimed successful. Local Python 3.13 execution was not performed; the CI matrix
retains it. No commit, push or merge was performed.

## Remaining scientific limits

Weekly transition matrices, observation emissions, effect strength, uptake,
attendance, delivery and cancellation probabilities remain explicit synthetic
assumptions. Radius and continuity margins are uncalibrated sensitivity parameters.
The cancellation opportunity freezes beliefs/eligibility, assumes no later releases,
and optimizes retention without a fairness shadow price; it is not an optimal
sequential policy. Review order is canonical and conservative; it does not solve
all possible joint cancellation combinations. No new evidence preserves support
even when a later purely time-driven reallocation might improve this approximation.
One accepted programme per student, no switching, rescheduling or carryover remain
bounded scenario restrictions. Shared subset scenarios do not span all independent
student uncertainties. Conditional fairness bounds cannot be called guaranteed
dynamic coverage or proof of a policy's failure. No empirical calibration,
statistical policy ranking or real educational effect is established here.
All requested implementation workstreams are exercised locally; remote CI success
and empirical/statistical research evaluation remain external validation tasks.

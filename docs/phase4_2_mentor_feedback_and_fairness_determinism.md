# Phase 4.2 mentor feedback and deterministic fairness

Amendment dated 2026-11-09. This protocol extends Phase 4.1; historical monthly
and weekly artifacts retain their original contracts and source/runtime guards.

New weekly artifacts use `scheduled_weekly/replay/v3` and decision snapshots use
`scheduled_weekly/decision/v3`. Mentor measurements use
`weekly_mentor/independent_same_likelihood/v1`; fairness preparation uses
`explicit_post_assimilation_preparation/v1`. The allocation rule remains policy v2.

## Root causes and interfaces

The weekly world generated school-monitoring emissions without assignment
context. Session lifecycle notes recorded operational delivery but contained no
condition measurement. The Phase 4.1 counterfactual therefore changed a school
note, rather than an observation from an actual mentor session. Passing active
assignments into the monthly model would incorrectly mark every session as
programme completion. The new session observation path never uses that flag.

Previously, `observe()` froze fairness cohorts using its first caller's estimates,
including fallback priors. A read before filtering could permanently change need
strata. It also advanced the current window before incorporating the preceding
window's last authorized offers. Explicit preparation now finalizes all historical
offer counts before opening a new window.

| File | Responsibility |
|---|---|
| `src/school/delivery_observations.py` | Typed session observations, private generation boundary, rendering, public provenance checks |
| `src/school/delivery_environment.py` | Emit only after actual delivery; pure `observe()`; explicit `prepare_decision()` and direct-step adapter; retain initialization inputs |
| `src/school/delivery_controller.py` | Validate session sources, extract and assimilate mentor facts, prepare fairness after filtering, independently validate histories |
| `src/school/delivery_contracts.py` | Weekly note session/delivery identities, decision v3 and explicit preparation flag |
| `src/intervention/feedback_notes.py` | Mentor controlled-language vocabulary and independently keyed note rendering |
| `src/intervention/observation_extractor.py` | Weekly grammar extension using the existing entailment/span/schema validators; monthly grammar and system prompt preserved |
| `src/school/state_estimator.py` | Recognize weekly mentor phrases with the declared matching likelihood; source-event deduplication unchanged |
| `src/school/delivery_policy.py` | Clearly reject allocation from an unprepared read-only snapshot; policy v2 valuation unchanged |
| `src/school/delivery_experiments.py` | Versioned mentor sources and fairness initialization inputs; strict exact replay and scientific protocol checks |
| `src/school/delivery_feedback_acceptance.py` | Actual-session decision-boundary, unsupported-prose and extra-read executions with exact replay |
| `src/school/delivery_acceptance.py` | Explicitly disable the new channel in the historical school-note counterfactual, preserving its meaning |
| `tests/test_delivery_feedback_integration.py` | Session, provenance, timing, likelihood, freshness, read-order, accounting and adversarial replay regressions |
| `tests/test_delivery_lifecycle.py` | Extend explicit observation-channel fixture configuration; direct-step tests retained |
| `tests/test_delivery_science.py` | Migrate decision calls to preparation; preserve group totals across evidence-derived need strata |
| `tests/test_delivery_adaptive.py` | Migrate decision calls to preparation and assert the new weekly replay version |
| `.github/workflows/offline-tests.yml` | Retain Python 3.12/3.13 offline tests and artifact upload; add the Phase 4.2 acceptance output |

## Measurement model and source correlation

For each actual `session_delivered` event, after that week's educational transition,
the environment samples a separate qualitative end-of-interval mentor measurement.
Its identity is `<session_id>:mentor-observation:v1`; it records the actual student,
mentor, programme, session, delivery event, source week, availability week, and
observation contract. A missed, refused, cancelled or unoffered session produces
no substantive post-session measurement. Missingness can also suppress an emission.

Both school and mentor channels explicitly use the **same** configured likelihood
L = (1 - misleading_probability) * emissions + misleading_probability / 4.
Rows correspond to stable, vulnerable, disengaged and withdrawn latent states;
columns correspond to regular participation, assignment difficulty, low participation
and lack of contact. Mentor lack of contact concerns contact outside the delivered
session. Every default row overlaps. Neither channel observes a deterministic
condition label, dropout probability, causal effect or recovery outcome.

The distinct school and mentor emissions are assumed conditionally independent
given the same post-transition latent state. They are separate synthetic
measurements, even when they happen to report the same signal category. Their
joint likelihood is the product of their two declared likelihood columns.
This strong, explicit assumption is not evidence of real-world independence.
Do not copy a real shared signal into both channels under different source IDs.
Copies of one generated measurement retain its original event identity; the
existing evidence ID hash and one-signal-per-source-event filter prevent an
additional likelihood update. Conflicting signals citing the same event are
excluded as a correlated conflict, not averaged as independent evidence.

Mentor measurement signal, missingness and delay have separate keys under
`weekly_mentor_observation/v1:<role>:<session_id>`. Note omission, ambiguity,
misleading prose, conflict and rendering delay use the distinct
`weekly_mentor_note/v1:<session_id>:` namespace. Educational transitions retain
`weekly_environment_transition/v1`; acceptance, attendance, actual delivery and
cancellation retain their existing programme/session keys. Adding or suppressing
mentor notes cannot consume a transition or delivery draw.

The source time is the end of session week t. Measurement availability is
t + 1 + a configured observation delay; rendering can add its separate declared
delay. Historical `delay_months` fields mean **week indices only within the named
weekly adapter**, as in Phase 4.1. The dated note has a deterministic UTC weekly
creation timestamp. No session-week decision can read its later measurement.
Notes arriving late are assimilated at their original source time when filtering
today's posterior. Saved earlier decisions are never recomputed or overwritten.

The renderer receives only the emitted observable record. Before and after the
existing extraction validator, the controller checks the public source chain:
delivery exists, is actually delivered, has become authorized, and matches all
student/mentor/programme/session/source identities and timestamps. It rejects
forged or prematurely available sources. The extractor still validates exact
sentence semantics, offsets, source time, evidence identity and schema. It never
receives simulator truth. Unsupported prose supplies no condition likelihood;
invalid extraction is quarantined. Lifecycle events may attest workflow completion
but cannot attest educational recovery or another educational-condition signal.

Successful mentor assimilation updates the posterior, evidence IDs and latest
source time. That same estimate feeds the existing information-sensitive
uncertainty rule, usual-support risk, committed-support risk and programme review.
The continuity/opportunity rule, .01 fixture margin, cancellation semantics,
reservation validation and later-cutoff reallocation remain Phase 4.1 mechanisms.
Absence of a measurement cannot establish treatment failure. Actual delivered
service alone selects the existing tutoring transition matrix for that week;
an offer, note, positive claim or completion flag cannot select it.

## Explicit fairness lifecycle

`observe()` is a pure public read. Before preparation it returns a provisional
snapshot with no new frozen cohort and `decision_prepared=False`; the public prior
is descriptive, not an allocation input. It never filters evidence, initializes
windows, advances time, changes histories or consumes randomness. At a prepared
cutoff it returns the cached immutable decision snapshot. Allocation from a
provisional snapshot raises a clear preparation-precondition error.

`WeeklyFeedbackController.prepare_decision_snapshot()` collects authorized notes
and registry/delivery records, validates/extracts evidence, filters each student,
and computes estimate uncertainty metadata and both risk targets. It calls
`env.prepare_decision(estimates=..., risks=...)` with complete current identities.
That operation constructs and validates the public state, applies authorized
unique offer history to existing windows, freezes a new cohort once at weeks
1, 5, 9, ... when needed, and validates the finalized decision snapshot. The
policy then computes its scenario sets and allocates. Scenario construction
does not determine cohort membership. Frozen need strata use the processed
authorized estimates, never simulator conditions or incidental fallback reads.

Each initialization retains the complete immutable input snapshot: estimates,
risks, resource ledger and authorized event IDs. `controller.validate()` checks
it against the actual decision input, re-freezes its cohort independently and
reconstructs unique offers from public events. Frozen group/need denominators
do not change during the window; refusal still counts as an offer, withdrawal
cannot shrink a denominator, later completion belongs to the original offer,
and physical infeasibility remains visible. The final week of a previous window
is updated before the next cohort opens. No terminal extra window is created.

For direct workflows, `env.prepare_decision()` without estimates invokes a
persistent fixture-extraction controller using the same authorized evidence,
transition/filter model and preparation path. `env.step(action)` invokes that
documented adapter if the cutoff has not already been prepared. Direct execution
therefore retains the supported step interface without a hidden prior-dependent
fairness freeze. Use `policy.plan(env.prepare_decision())` for direct planning.

Given identical authorized history and cutoff, filtering, grouping and source
identities are deterministic. Additional reads cannot affect any input to this
operation. The executable fairness regressions compare entire runs, including
both sides of the week 4–5 boundary, estimates, required counts, offers, resource
decisions, delivered sessions, hidden evaluator trajectories and final scorecards.

## Matched actual-session demonstration

The fixture has three fictional students, one mentor, one weekly slot and
concurrent recipient, eight weeks, five required sessions, budget 11, certain
acceptance/attendance/delivery, no exogenous cancellation and seed 41. All arms
share initial hidden states, calendars, school-note information, policy, budget
and random streams. The policy selects and delivers the initial accepted
programme in week 1; no action or posterior is injected. Only the focal student's
actual source-week 1 mentor measurement is controlled: regular versus low
participation, both supported observations under the overlapping likelihood.
The evaluator-owned override is applied at the private emission boundary, saved
in evaluator replay inputs and never supplied to the allocator.

At cutoff 2 the school note for that student contains no condition signal, so
the new information comes exclusively from the actual delivered-session note.
The complete source note, validated fact, filter update, uncertainty, both risks,
review, allocation, future ledger, delivery events, window initialization inputs
and realized synthetic trajectory are saved in `acceptance_report.json` and
each sealed episode. Unsupported prose and the same prose with an unsupported
follow-up sentence form matched negative controls. A fifth execution adds public
reads before controller construction, before filtering and between cutoffs.

| Cutoff-2 quantity | Regular mentor observation | Low mentor observation |
|---|---:|---:|
| Posterior stable | .4501433264 | .0495271653 |
| Posterior vulnerable | .3448643523 | .2223683871 |
| Posterior disengaged | .2049923213 | .7281044476 |
| Usual-support terminal non-enrollment risk | .0816230027 | .1821499354 |
| Committed-support terminal non-enrollment risk | .0530234138 | .1176639765 |
| Remaining continuation benefit | .0285995889 | .0644859589 |
| Released-capacity opportunity | .0709601194 | .0709601194 |
| Decision with margin .01 | cancel | continue |
| Later alternative offer | week 3 | week 4 |
| Original recipient's total delivered sessions | 1 | 2 |
| Alternative recipient's total delivered sessions | 5 | 5 |
| Final actual expenditure | 6.2 | 7.2 |
| Realized terminal retained students | 3/3 | 3/3 |

Cancellation leaves the original delivered session and expenditure 1.1 intact,
releases only four undelivered liabilities, and permits the replacement offer
at the later cutoff. The low arm is reviewed again after new later mentor
evidence; a week-2 continuation does not guarantee permanent continuation.
Unsupported information leaves the source-0 freshness unchanged at cutoff 2
(radius .40625), whereas successfully assimilated source-1 mentor evidence has
radius .25. Different supported observations also change entropy and the
estimate-linked uncertainty identity; they need not change the radius itself.
The common retained outcome is a measured result, not evidence of causal or
policy superiority. This deliberately chosen case establishes that an actual
session's valid mentor evidence **can**, not must, cross a feasible decision boundary.

## Versioning, reproduction and verification

Weekly replay v3 adds session observations, exact mentor/source metadata, channel
enablement/configuration, evaluator-owned controlled signal overrides, full
fairness initialization inputs and the explicit lifecycle contract. Replay
regenerates observations and checks note metadata before accepting recorded
prose or extraction outcomes. It then compares every estimate/uncertainty history,
review, decision, event, resource ledger, cohort, summary and hidden trajectory.
Even a consistently resealed forged source, availability, signal, cohort or
protocol is rejected. Future recordings are only applied when their source is
generated; they cannot reconstruct an earlier decision.

The existing monthly default grammar, system prompt, estimator configuration,
transition semantics and replay version are unchanged. Weekly v1/v2 artifacts
remain readable with their original integrity/protocol checks; exact execution
requires their archived matching source and runtime, as before. Old artifacts
are not overwritten or relabeled. The original school-note acceptance explicitly
disables the new channel; its 12 examples keep their scientific interpretation.

Use a fresh output path for every retained run:

```sh
python3.12 -m venv /tmp/school-phase42
/tmp/school-phase42/bin/python -m pip install -r requirements-offline.txt
MPLCONFIGDIR=/tmp/phase42-mpl /tmp/school-phase42/bin/python -m unittest discover -s tests -p 'test_delivery_feedback_integration.py'
MPLCONFIGDIR=/tmp/phase42-mpl /tmp/school-phase42/bin/python -m unittest discover -s tests -p 'test_delivery_*.py'
MPLCONFIGDIR=/tmp/phase42-mpl /tmp/school-phase42/bin/python -m unittest discover -s tests -p 'test_phase*.py'
MPLCONFIGDIR=/tmp/phase42-mpl /tmp/school-phase42/bin/python -m unittest discover -s tests
/tmp/school-phase42/bin/python -m src.school.delivery_feedback_acceptance --output results/phase4_2_fresh_acceptance
/tmp/school-phase42/bin/python -m src.school.delivery_acceptance --output results/phase4_2_legacy_examples
/tmp/school-phase42/bin/python -m src.school.delivery_experiments --config configs/delivery_weekly_v1.toml --output results/phase4_2_delivery_demo
/tmp/school-phase42/bin/python -m src.school.delivery_experiments --replay results/phase4_2_fresh_acceptance/regular --output results/phase4_2_fresh_replay
git diff --check
```

Repeat the test commands in a separate Python 3.13 environment using the same
pinned offline dependencies. The measured local verification record is retained
in `docs/phase4_2_acceptance_results.json`; full logs and sealed artifacts are
under `results/phase4_2_verification_20261109` and the corresponding acceptance
directories. CI retains the existing synthetic-only workflow and upload process,
adding the new acceptance examples. Local verification does not claim a remote
GitHub workflow succeeded.

Measured local results (CPython 3.12.12 and 3.13.5, pinned offline dependencies):

| Check | Result |
|---|---|
| Pre-edit complete suite, Python 3.12.12 | 426 passed, 114.840 s |
| Pre-edit delivery baseline | 76 passed, 2.700 s |
| Initial defect reproductions | 2 failures and 1 missing-interface error, before fixes |
| Final new mentor/fairness/replay regressions | 27 passed, 2.855 s |
| Final Phase 4/4.1/4.2 delivery tests | 103 passed, 5.457 s |
| Final named Phase 1–3 regressions | 116 passed, 60.195 s |
| Final complete suite, Python 3.12.12 | 453 passed, 112.247 s |
| Final complete suite, Python 3.13.5 | 453 passed, 109.195 s |
| Actual-session mentor acceptance, each Python version | 5/5 episodes and exact replays |
| Historical school-note examples | 12/12 episodes and exact replays |
| Bounded delivery demonstrations | 7/7 episodes and exact replays |
| Independent saved-artifact validation | 29/29 episodes: executable offers, prefix/final ledgers, note sources, extraction and frozen cohorts |

All final tests passed without skips. The extra-read experiments compared all
serialized episode fields, evaluator draws, trajectories and scorecards, including
weeks 4 and 5 (and a third window at week 9 in the adversarial regressions).
Every executed opportunity solve was optimal or analytically empty; all MILP
allocations reported `weekly_rollout_milp_optimal`. Random/priority/wait and
no-candidate decisions retain their existing statuses. Existing finite-instance
enumeration and nonoptimal-solve continuity protections still pass. Retained
protocol-bearing weekly v1 and v2 artifacts passed their historical readers.

An intermediate full-suite run caught the extractor importing a simulator type;
the final implementation selects the weekly grammar through the note adapter
contract, preserving the extraction-layer boundary. The failed attempt logs are
retained alongside the final successful logs. No commit, push, merge or remote CI
success is claimed.

## Scientific limits

Observation emissions, conditional independence, reporting quality/delays,
transition matrices, tutoring effects, service probabilities, uncertainty radius
and continuity tolerance remain explicit synthetic assumptions. They are not
empirically validated educational causal effects. The synthetic source state is
post-transition/end-of-interval, not a measured real student's condition at an
exact session instant. Acceptance uses zero additional note-rendering corruption;
its filter likelihood matches the actual sampled source signal. As in earlier
phases, nonzero `NoteQuality` misreporting is a deliberately misspecified stress
condition: the filter does not estimate or correct an unknown prose-corruption
channel. Source-level misleading noise in `ObservationConfig` is included in L.
The existing finite-scenario rollout and conservative
opportunity review remain approximate sequential decisions; fairness feasibility
bounds remain conditional on their frozen public model. The examples establish
engineering behavior and reproducibility, not statistical policy ranking,
real-data calibration or optimality of the entire intervention process.

# Phase 4: weekly delivery, commitments and offer fairness

Implementation and acceptance record, 2026-11-09. This extends the existing
architecture alongside the atomic monthly benchmark. Synthetic mechanisms and
small demonstration results do not establish effects on real educational outcomes.

## A. Implementation summary

Added `scheduled_weekly/v1`: a weekly environment, immutable delivery events and
public snapshots, full-schedule reservations, observed delivery-driven treatment,
ongoing-programme feedback, four-week unique-offer fairness, six allocation
policies and sealed offline replay. The existing `atomic_monthly` remains the
default for all old scenarios. Its five-appointment admissions, immediate charge,
monthly transitions and historical admission-based fairness have not been changed.

The implementation verified the old path before editing: `candidate_assignments`
sets both `sessions` and `completed_sessions` to five, `validate_allocation`
requires them in the admission month, and `CMDPEnvironment.step` charges the whole
programme and chooses the treatment matrix for admissions. `_mentor_resources`
explicitly uses no programme-hours requirement. These contracts remain intact.

No source datasets, synthetic population files, monthly configurations, historical
results, historical protocol or original replay definitions were rewritten.
No new dependency, prediction model or orchestration framework was introduced.
Work remains in the current working branch; there is no merge or push.

## B. Actual architecture and call paths

```text
src.main --runner delivery
  -> DeliveryConfig.load -> run_demonstration
  -> WeeklyDeliveryEnvironment + WeeklyDeliveryPolicy
  -> WeeklyFeedbackController.run_episode
       prepare_decision_snapshot:
         authorized emissions/events -> WeeklyNote
         -> injected extractor -> existing validate_batch
         -> StudentStateEstimator(weekly_delivered_v1)
         -> independent SimulatedWithdrawalRiskEstimator
         -> weekly estimate/risk wrappers -> environment.observe
       policy.plan(WeeklyDecisionState) -> DeliveryAction
       validate_offers -> environment.step -> validate_offers again
         reserve every offered schedule -> charge administration -> resolve uptake
         -> continuation/cancellation -> actual current sessions
         -> event-derived ledger -> weekly transition -> authorized observations
       next cutoff consumes newly available records; earlier snapshots stay frozen
  -> independent controller.validate -> scorecard
  -> save_delivery_episode: stage -> validate -> seal -> verify -> publish once
  -> replay_delivery_episode: verify -> rebuild world/policy/filter/extractions
     -> rerun every decision -> compare complete payload and evaluator trajectories
```

`WeeklyDeliveryEnvironment.from_students` adapts existing authorized source
profiles while keeping reset conditions private. The bounded demonstration uses
wholly fictional profiles. Explicit cohort/staff counts must match configuration.
`Mentor` and `MentorAvailability` are converted into immutable weekly calendars;
zero-hour calendars with positive session slots are rejected. Missing future
calendar entries mean zero hours/slots, never unlimited resources.

The environment owns latent categorical conditions and realized stochastic
outcomes. The controller owns observations, extraction outcomes, beliefs, risks,
actionable-evidence diagnostics and persisted decisions. Policies receive frozen
weekly records containing public profiles, registry enrollment, estimates/risks,
observed programme status, prior offers, waiting, calendars and commitments.
Future scheduled slots are public; future realized attendance and state are not.

The event ledger is authoritative. `audit_delivery_events` independently rebuilds
resource usage, lifecycle transitions and every monetary liability from original
calendars/events. It receives no claimed planner spending or capacity counters.
`validate_offers` separately reconstructs the entire proposed schedule against
the public snapshot, and publication checks each historical decision-prefix
ledger against the corresponding event prefix.

## C. Files changed

| Area | Files and role |
|---|---|
| Configuration/contracts | [delivery_config.py](../src/school/delivery_config.py), [delivery_contracts.py](../src/school/delivery_contracts.py), [delivery_weekly_v1.toml](../configs/delivery_weekly_v1.toml): explicit world/time/version, assumptions and immutable records |
| Environment/resources | [delivery_environment.py](../src/school/delivery_environment.py), [delivery_resources.py](../src/school/delivery_resources.py): lifecycle, schedule validation, independent exact ledger |
| Allocation | [delivery_policy.py](../src/school/delivery_policy.py): shared baselines, weekly rollout value, full-future-resource MILP and finite-scenario robust extension; reuses existing MILP solver |
| Fairness | [delivery_fairness.py](../src/school/delivery_fairness.py): frozen four-week cohorts, unique actual offers, original-offer-window acceptance/completion, shortfall/disparity/waiting reports |
| Feedback | [delivery_controller.py](../src/school/delivery_controller.py): validated weekly notes, source-time filtering, exact risk identities, extraction quarantine and actionable diagnostics |
| Experiments/replay | [delivery_experiments.py](../src/school/delivery_experiments.py): fictional fixture, six policy comparisons, sealed replay contract and scorecards |
| Small compatibility extensions | [cmdp_environment.py](../src/school/cmdp_environment.py): reject weekly config; [scenario_config.py](../src/school/scenario_config.py): nonserialized legacy mode/time properties; [state_estimator.py](../src/school/state_estimator.py): explicit opt-in for multiple delivered-week actions, preserving default serialized identity |
| CLI | [main.py](../src/main.py): explicit delivery runner and weekly horizon; reject monthly units in that runner |
| Tests | [test_delivery_lifecycle.py](../tests/test_delivery_lifecycle.py), [test_delivery_science.py](../tests/test_delivery_science.py): lifecycle, exact accounting, adversarial reconstruction, tiny-instance enumeration, fairness, information boundary, reproducibility and replay |
| Documentation | This report, [weekly protocol v1](phase4_delivery_protocol_v1.md), and [README](../README.md) navigation |

## D. Mathematical and operational model

### Weekly clock and lifecycle

For cutoff t, incorporate only records available by t with source week below t;
compute estimates and independent risk; freeze a new fairness cohort if needed;
plan and independently validate offers. Reserve all proposed programmes before
resolving any refusal. Charge administration; resolve uptake; retain accepted
schedules and release refused service liabilities. Execute current sessions of
accepted programmes, except programmes cancelled before that service. Charge
only the declared realized activities; apply one state transition; emit dated
observations and advance. Week-t information becomes available at t+1 or later.

An accepted programme is scheduled, then active. Completion requires all n
configured sessions to have actually been delivered. Missed sessions stay missed
without rescheduling. At the final scheduled slot a partial programme is
`INCOMPLETE`, not completed. Explicit or exogenous cancellation yields
`CANCELLED`, releases unused current/future slots, and preserves spending.
Withdrawal after a transition cancels only future service; this week's already
delivered session is retained. Refusal yields `REFUSED` with zero delivered service.
One accepted programme per student/episode is supported; refused offers may recur.

Immutable event records distinguish offer, uptake/refusal, reservation, scheduling,
delivery, miss, administration, release, active status, completion, cancellation,
incompletion and an outcome-follow-up record. Every event names its student,
mentor, programme, event, relevant session, source/availability week and provenance.
Programme outcome follow-up explicitly leaves educational success unknown;
condition signals after transitions are separate noisy authorized observations.

### Hard constraints and money

A candidate j is a student–mentor–start triple. Let S_j be its configured session
weeks and I_j the interval from its first to last session. Binary x_j denotes a
new start, including tentative future starts for fair planners. Enforce:

* At most one selected start per eligible student; tutoring skill compatibility.
* For every mentor/week, fixed occupied slots plus `sum(j: week in S_j) x_j`
  cannot exceed its calendar's session slots.
* The same occupied-session count times the exact session duration cannot exceed
  that week's working hours.
* Fixed concurrent students plus `sum(j: week in I_j) x_j` cannot exceed caseload,
  including non-session weeks between appointments.
* Every session fits the announced calendar and episode horizon. No carryover.
* Committed schedules are fixed, not optional future optimization variables.

Let B be the episode budget, E actual cumulative expenditure, L outstanding
service liabilities and A the administration temporarily reserved for offers.
Spendable money is `B - E - L - A`, always nonnegative. Offer commitment is
`administration + n * session_price`. The model reserves this worst case for all
offers before uptake, even when refusal is likely. Administration is charged
once per actual offer and stays spent after refusal.

On delivery, `L -= price; E += price`. On a miss, `L -= price; E += missed_charge`,
and record `price - missed_charge` as a released obligation. The missed slot and
time remain wasted. Refusal/cancellation releases only undelivered liabilities.
No event can charge or release a session twice; actual spending is never refunded.
Cumulative released obligations may exceed B across repeated refused offers;
this is turnover in reservations, not a refund or extra budget.

Authorization and auditing use Decimal amounts; solver cost/hour rows use exact
integer multiples and are independently rechecked. Money is one shared episode
pool, with reserved/spent/released/admin amounts attributed by mentor and service
week; there are no invented independent mentor budgets. Ledger cells separately
report hours, slots, actual delivery, missed/wasted capacity and caseload.

### Treatment and valuation

`synthetic_weekly_v1` contains directly declared weekly matrices W and T. It is
not the monthly matrices repeated weekly or an undocumented rate conversion.
The effective matrix is `W + alpha*(T-W)`. A week with actual delivered tutoring
uses that matrix once; all other weeks use W. Absorbing withdrawal is unchanged.
Offers, acceptance, missed delivery and note interpretation do not trigger T.

The separately named expected-delivery rollout conditions on programme-level
acceptance p, then uses `q*T + (1-q)*W` in scheduled weeks, with
`q = attendance_probability * delivery_probability`. An active/inactive mixture
keeps acceptance correlated across all sessions and transfers active mass to
inactive before later weeks with the declared cancellation probability. Apply W
before a projected start and after completion. Terminal retained indicator is
`e=(1,1,1,0)`. Gain is expected retention for this offered schedule minus WAIT
retention from the same current belief. No realized future outcome enters gain.

Point maximizes aggregate current-start rollout gain. Fair point projects starts
through the current assessment window while accounting for their complete future
commitments. Robust uses nominal and two coherent global enrolled-belief mixture
scenarios (radius .25), with lower/higher current-start reference gains; the same
student belief in a scenario applies to all candidate mentors/start weeks. It
maximizes eta subject to `eta <= sum_j gain[j,scenario]*x_j` for every scenario.

The fair lexicographic sequence is minimum `sum_cell(shortfall / frozen_size)`,
maximum point/worst-scenario rollout gain, minimum exact commitment cost, then
canonical sorted start bits. Slack is explicit and integral. Strict infeasibility
is reported without overbooking; timeout/incomplete stages retain explicit status.
An optimal solver status applies to this deterministic approximation only.

### Four-week offers and observation adapters

At weeks 1, 5, 9, etc., freeze authorized eligible tutoring students, source group
and need stratum. Use enrolled MAP if its probability is at least .6, otherwise
uncertain. Include students whose coverage is resource-infeasible, so the deficit
remains visible. Group membership/denominators remain fixed after refusal or
withdrawal. A partial terminal window is explicitly flagged.

For each frozen cell, required access is exact decimal
`ceil(target * frozen_size)`. Unique actual offers plus shortfall must cover that
requirement. Refusals count; repeated offers and session events do not add unique
coverage. Acceptance and completion are separate. Completion stays attributed to
the original offer cohort, with a separate within-offer-window count. A programme
finishing in week 5 does not become a new offer in weeks 5–8. Empty rates are null,
small cells are flagged, and observed shortfalls/disparities/waits are reported.

Existing extraction/filter payloads retain their historical `source_month` and
`as_of_month` fields inside an explicitly labeled week-index adapter. New public
contracts use weekly names; `WeeklyNote` supplies seven-day synthetic dates.
This avoids changing historical Note/EstimatedStudentState serialization.
Filter actions in weekly mode are unique **observed delivery weeks**; the default
atomic action contract still permits its one historical admission. Workflow
facts do not refresh condition evidence. Quarantined/empty/conflicting observations
retain their diagnostics without a gold fallback or hidden-state write.

## E. Verification and acceptance results

Interpreter: CPython 3.12.12, `/tmp/phase1-python312/bin/python`. The automatically
configured workspace environment was Python 3.14.8, outside the supported range;
the initial baseline there had 95 provenance-guard errors. No compatibility guard
was weakened to allow that interpreter. Targeted legacy checks then passed on 3.12.

Commands:

```bash
/tmp/phase1-python312/bin/python -m unittest tests.test_delivery_lifecycle tests.test_delivery_science tests.test_entrypoints -q
/tmp/phase1-python312/bin/python -m unittest discover -s tests -q
/tmp/phase1-python312/bin/python -m src.school.delivery_experiments --output results/phase4_delivery_20261109_v3
```

Focused final pre-acceptance check: **46 tests passed**, including 42 new weekly
checks and four existing entrypoint tests. Independent derivations verify a
two-mentor/three-student ledger, expected-delivery matrix multiplication, and
exhaustive feasible-subset agreement with the tiny fair scheduling MILP.

An intermediate full run passed 380 of 381 tests and rejected one experiment
whose source fingerprint changed during concurrent edits. This was diagnosed as
the intended provenance guard. Final full acceptance is rerun with source fixed;
its result is recorded in the final acceptance addendum below.

The expanded deterministic demo exposed a second, genuine replay bug after that
suite: restoring integer-valued exact calendar/price strings through floats
changed `2` to `2.0`, altering ledger strings and snapshot identities. A new
regression reproduced the failure before correction. Replay now restores those
fields as exact Decimal amounts. The resulting focused weekly/filter check
passed **51 tests**. The failed v2 demonstration was quarantined without a
successful destination; final artifacts use v3.

Additional tested cases include no instant completion, no service after refusal,
partial/missed/cancelled service, horizon rejection, separate slot/hour/caseload
limits, calendar reductions, zero-price services at zero budget, tiny decimal
overspending rejection, retained delivered charges, fresh-identity double-charge
rejection, repeated offers, cross-window completion, frozen withdrawal denominators,
strict infeasibility, zero effect under matched streams, non-delivery with a
nonzero treatment contrast, authorized-only snapshot equality after private truth
changes, absent future draws, delayed evidence, exact estimate/risk identity,
failed extraction, unchanged unrelated-student keyed draws, deterministic histories
and offline replay with every lifecycle branch. Editor diagnostics report no errors
in the modified implementation and focused test files.

## F. Bounded trace and scorecards

Final artifacts: [versioned demonstration](../results/phase4_delivery_20261109_v3/),
[scorecard](../results/phase4_delivery_20261109_v3/scorecard.md),
[full scorecards](../results/phase4_delivery_20261109_v3/scorecards.json).
Each policy directory contains initial profiles, full configuration/calendars,
immutable decisions, observations, notes, extractions, filter updates, lifecycle
events, resource snapshots and frozen cohorts. Its `evaluator_only` subdirectory
contains initial truth, realized hidden trajectories and random-stream records.
Each replay directory contains the verified replay identity/result.

The default run uses 12 fictional students/two mentors/12 weeks, five sessions,
two simultaneous students per mentor and nonzero refusal, misses and cancellation
probability. It compares WAIT, random, priority, point, fair point and fair robust
using the same seed, authorized information model and resource rules. This is one
development episode per policy, not a statistical ranking. See the addendum for
the executed numerical scorecard.

| Policy | Offers | Accepted / started | Delivered | Missed | Completed | Cancelled / incomplete | Spent | Unspent | Retained |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| WAIT | 0 | 0 / 0 | 0 | 0 | 0 | 0 / 0 | 0 | 40 | 12/12 |
| Random feasible | 10 | 8 / 8 | 30 | 10 | 1 | 0 / 7 | 31.0 | 9.0 | 12/12 |
| Risk/wait priority | 10 | 8 / 8 | 28 | 12 | 0 | 0 / 8 | 29.0 | 11.0 | 12/12 |
| Resource point | 10 | 8 / 8 | 28 | 12 | 0 | 0 / 8 | 29.0 | 11.0 | 12/12 |
| Fair point | 12 | 8 / 8 | 27 | 13 | 0 | 0 / 8 | 28.2 | 11.8 | 12/12 |
| Fair robust | 12 | 8 / 8 | 27 | 13 | 0 | 0 / 8 | 28.2 | 11.8 | 12/12 |

All terminal reserved balances are zero; every mentor's peak simultaneous
caseload is at most two. Each has 24 available hours. Random delivers 16/14 hours
by mentor, priority 14/14, point 12/16 and fair methods 12/15; missed slots are
retained as wasted capacity. Every resource audit passed. All ordinary runs have
12/12 terminal retention in this seed, so there is no retention advantage to infer.

| Policy | Weeks 1–4 unique offers / denominator | Weeks 5–8 | Weeks 9–12 | Eventual completions by offer window | Cell shortfalls by window |
|---|---:|---:|---:|---|---|
| WAIT | 0/12 | 0/12 | 0/12 | 0, 0, 0 | 5, 6, 6 |
| Random feasible | 5/12 | 4/8 | 0/4 | 0, 1, 0 | 1, 0, 2 |
| Priority | 5/12 | 4/8 | 0/4 | 0, 0, 0 | 1, 1, 2 |
| Resource point | 5/12 | 4/8 | 0/4 | 0, 0, 0 | 1, 1, 2 |
| Fair point | 6/12 | 4/8 | 0/4 | 0, 0, 0 | 0, 1, 3 |
| Fair robust | 6/12 | 4/8 | 0/4 | 0, 0, 0 | 0, 1, 3 |

These pooled ratios supplement the actual group/need-cell rows, not replace them.
Required access is rounded up per frozen cell, so pooled coverage above .3 does
not imply all cell targets were met. Denominators may change only at a new window;
they remain fixed within it. No five-session programme can start in weeks 9–12
without crossing the horizon, so late-window shortfalls remain visible.

The guaranteed trace uses four students, identity transitions and explicit
exogenous fixtures: student 00 refuses; 01 misses week 2 and finishes partial;
02 cancels before week-2 service; 03 completes all five sessions. Source group
does not control any probability. These deterministic overrides are saved with
stream identities in evaluator records and reproduced without a live LLM.

The [guaranteed lifecycle episode](../results/phase4_delivery_20261109_v3/guaranteed_lifecycle/episode.json)
and [verified replay](../results/phase4_delivery_20261109_v3/guaranteed_lifecycle_replay/replay_result.json)
show the four distinct outcomes:

| Week-1 student | Final programme status | Delivered sessions | Session weeks |
|---|---|---:|---|
| fictional-00 | REFUSED | 0 | 1–5 reserved, then released |
| fictional-01 | INCOMPLETE | 4 | 1, 3, 4, 5 delivered; week 2 missed |
| fictional-02 | CANCELLED | 1 | week 1 delivered; weeks 2–5 released |
| fictional-03 | COMPLETED | 5 | 1–5 delivered |

At week 1 all four potential schedules are conservatively checked: 20 service
units plus .4 administration. After refusal and first sessions, actual spend is
3.4, outstanding service liability 12.0. At week 2 the cancellation releases four
future service units; the miss releases one and consumes its slot. Across the
episode, student 00 makes eight actual refusals, which count once in each source
window: 11 total offers, three acceptances/starts, ten delivered sessions, one
miss, one completion, one cancellation and one incomplete programme. Actual final
spend is 11.1 (10 delivered + 1.1 administration), remaining budget 38.9 from 50,
and reserved balance zero. First-window offer coverage is 4/4, acceptance coverage
3/4 and eventual completion coverage 1/4; within-window completion is zero.

The separate hand-verified case uses three students, two mentors, one hour/slot
and one simultaneous student each, eight weeks, session price .2, administration
.1 and budget 3. Start s0/m0 and s1/m1 in week 1. The commitment is 2.2 total;
week 1 spends .6 and retains 1.6; weeks 2–5 spend .4 each. Both complete; final
spend is 2.2, liabilities zero, spendable .8. A third overlapping programme is
infeasible. Frozen groups are False={s0,s2}, True={s1}; at target 1, coverage is
1/2 and 1/1, required access 2 and 1, shortfalls 1 and 0. Eventual completion
coverage equals 1/2 and 1/1; within the original weeks 1–4 it is zero because
both programmes complete in week 5. Tests assert each quantity independently.

## G. Compatibility and replay

Old TOML files retain their meanings, monthly matrices and unit assumptions.
`ScenarioConfig` adds mode/unit properties without adding serialized dataclass
fields, preserving the old configuration identity. The default estimator's
configuration dictionary also remains identical. New weekly configs are rejected
by the atomic environment; weekly configs reject monthly time/transition settings,
automatic rescheduling and unsupported charging assumptions.

Monthly feedback replay contract 3 and its tests remain in place. As before,
exact historical replay requires the recorded source/dependency versions; this
checkout does not bypass that guard to replay older code with changed semantics.
New episodes use the separately named `scheduled_weekly/replay/v1`, with manifest
identity, full frozen weekly protocol, exact runtime/dependencies/source hashes,
inventory seal and evaluator separation. Replay reconstructs actual policy
decisions as well as outcomes, using recorded validated extraction outcomes;
it does not just copy a previously selected action list.

All publication uses existing staged/sealed artifact conventions and exclusive
destinations. The earlier development v1 directory is retained unchanged; final
acceptance is a new v3 path; failed v2 remains quarantined. No historical
experiment is amended in place.

## H. Research limitations

Uptake, attendance, successful service, cancellation and weekly transition matrices
are transparent synthetic assumptions, not fitted educational relationships.
Equal offers need not produce equal acceptance, completion, learning or retention.
The small cohort has no power to establish planner superiority. Completion means
delivered sessions only; it is not proof of successful educational response.

The optimizer uses expected schedule value and optimistic availability of today's
eligible students for projected future starts. It does not solve the stochastic
CMDP/POMDP, anticipate future evidence, or optimize the uptake-contingent recourse
tree. Full accepted commitments are fixed. The new robust method has a bounded
three-scenario uncertainty set, rather than the monthly planner's documentation-
dependent uncertainty scenarios; extending/calibrating that model is future work.

The weekly adapter reuses controlled-language extraction and the existing
categorical likelihood/filter. Its emission/weekly-transition assumptions need
sensitivity analysis. The demonstration uses the offline fixture extractor;
live unrestricted mentor-language performance and model calibration are not
validated here. Injected extractors use the same evidence validation/quarantine
boundary and can be replayed without live inference.

The implementation supports tutoring, no rescheduling/carryover, one accepted
programme per episode, one session per cadence week, and no student re-entry.
Non-tutoring source needs do not acquire invented action contracts. No private
response coefficients, predictive socioeconomic uptake relationships or direct
enrollment overwrites are introduced.

## I. Remaining tasks

No additional action contracts or empirical conclusions are claimed. Broader
multi-seed educational sensitivity studies, documentation-aware weekly robust
scenario design/calibration, live-model extraction evaluation, rescheduling and
carryover are research extensions rather than required lifecycle functionality.
Final acceptance outcomes and any genuine blockers are listed below.

## Final acceptance addendum

Final source-fixed full suite: **393 tests passed in 112.576 seconds** on
CPython 3.12.12 (350 existing tests plus 43 new weekly tests). The final focused
weekly/filter run passed 51 tests in 1.793 seconds. `git diff --check` and editor
diagnostics passed. No outstanding test failures or implementation blockers remain.

The final v3 development demonstration completed all six ordinary policy episodes
plus the guaranteed lifecycle fixture. **All seven exact offline replays passed**,
comparing decisions, immutable snapshots, estimates/risks, note/extraction outcomes,
event ordering, schedules, resource balances, fairness records, random-stream
identities and evaluator-owned trajectories. Every independent resource audit
passed. Terminal reservations were zero and no mentor was overbooked.

The implementation remains uncommitted on working branch
`fix/phase-4-realistic-intervention-delivery`; no branch was merged or pushed.
All prior datasets/results were preserved. The failed v2 attempt is retained in
the existing quarantine convention, and v1 development output is unchanged.
Use the v3 artifacts linked above for final acceptance. Replay of any retained
version continues to require its recorded source and dependency versions.

The remaining limitations are those in section H: expected-value scheduling,
bounded robust scenarios, synthetic mechanisms and offline controlled-language
evaluation. They are explicitly reported, rather than presented as empirical
causal results or exact stochastic-policy optimality.

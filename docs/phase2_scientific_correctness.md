# Phase 2: actionable monitoring extraction

Implementation and verification record, 2026-11-09. Scope: R01 and R04 only.
Starting branch `fix/phase-2-llm-correctness`; clean starting commit
`bd3f23cd2181bc310aa19592f47ac6c1d67fcaba`. No project AGENTS.md files were found.

## Inspected dependency map

`CMDPEnvironment.generate_observable_records` supplies authorized `ObservableEvent`
and `EnrollmentRecord` objects from `SyntheticObservationModel`. `render_note`
applies the dated note-quality channel. `ClosedLoopCMDPController` selects and
routes notes to `ObservationExtractor`; `validate_extraction` checks schema,
identity, source time, verbatim spans and controlled-language entailment.
`StudentStateEstimator` replays validated evidence with committed action history
and registry records. Its Phase 1 assimilation rules determine freshness.
`SimulatedWithdrawalRiskEstimator` computes WAIT endpoint risk from that estimate.
`operational_snapshot` constructs a frozen `DecisionState`; `retention_value`
computes policy-model benefits; planners propose allocations; `validate_allocation`
and the environment independently enforce resources and single admission before
the environment transitions. Scorecards join evaluator truth only afterward.

R01: the controller unconditionally routed monitoring notes to the grammar
extractor. Injected extraction only saw programme notes after admission; those
students were permanently ineligible. R04: `live_snapshot_comparisons` initialized
fresh controllers at cutoff 1, where that route made zero injected calls, and
reported equality as if extraction had been exercised.

## Tests before production changes

On CPython 3.12.12, `python -m unittest tests.test_phase2_correctness -v` initially
failed all three tests: changed extraction left both month-2 actions at SYN00003;
initial monitoring produced 0 calls rather than 3; the always-failing snapshot
extractor received 0 calls. No production changes preceded this run.

The final counterexample strengthens the initial fixture by adding a moderate
assignment-difficulty report for SYN00002, so both month-2 choices have strictly
greater benefit than the alternative. The initial reproductions had already
failed before production changes; no pre-change pass is being inferred from the
later strengthened fixture.

## Selected correction and configuration

The default `actionable_monitoring` extraction contract adds a route for authorized
school monitoring before admission. It reuses the existing note, batch, estimator,
risk, snapshot and allocation interfaces. No environment transition, resource,
eligibility, fairness definition or risk equation changes were needed. In particular,
`StudentObservation.eligible` still requires enrollment and no previous programme.

| Setting / mode | Implemented behavior |
|---|---|
| `max_notes_per_month` | Unchanged programme-note cap per source month; default `None`. Delays can bring several source months to one extraction cutoff. |
| `max_monitoring_notes_per_month` | Separate per-decision-cutoff bound; default 1, 0 disables, Python `None` explicitly selects all actionable available notes. CLI accepts nonnegative integers. |
| Structured / oracle | Full authorized structured observations, ignoring both note caps. Oracle remains explicitly labeled and uses only current truth. |
| B-matched | Exact grammar extraction of only the selected available notes, including omissions, contradictions, delays and source dates. |
| C / `llm_notes` | Injected extraction for the same selected monitoring notes and retained programme notes. |
| D / `noisy_notes` | Configured noisy note channel precedes selection and injected extraction. Research D-matched uses B-matched with the exact D channel. |
| `legacy_programme_only` | Explicit historical routing: monitoring uses the grammar and only programme notes use the injected extractor. Old replay manifests without a contract select this legacy route. |

Selection is made at the receipt cutoff using current authorized administrative
enrollment and committed admission history. Eligible available notes are sorted by
SHA256 of `[seed, cutoff, note_id]`, with note ID as the secondary key. No condition,
demographic group, need score, private transition parameter or future draw enters
selection. This avoids a source-prefix priority. It is a reproducible per-note
lottery, not a calibrated fair sampling procedure: differential note availability,
multiple delayed reports and prior admissions can affect a group's realized
coverage. It does not guarantee equal group coverage. Selection and exclusion logs
make that limitation auditable; no new fairness constraint is introduced.

Cap-excluded notes are permanently unprocessed, with no backlog or gold fallback.
Unavailable notes remain pending and may compete at a later cutoff. Monitoring for
previously admitted/non-enrolled students is excluded, and no monitoring extraction
is performed after the final decision. Programme feedback can still be processed
at the terminal cutoff. Selection reasons include `monitoring_cutoff_cap`,
`programme_source_month_cap`, `not_yet_available`, `not_actionable`, and
`no_remaining_decision`. Stable note/source/evidence identities are unchanged.

All injected batches are revalidated at the controller boundary. A batch dataclass
does not itself establish validity. Schema, cutoff, student/note identity, source
time, verbatim evidence, controlled-language entailment and evidence hashes are
checked. Empty, unknown, conflicting and supported accepted results are distinguished.
Invalid/unsupported outputs and adapter exceptions are quarantined with note ID,
cutoff, exception type and reason. No failed call becomes structured evidence.
The unchanged Phase 1 estimator preserves valid history, advances using known
actions, deduplicates facts, and derives freshness only from successful condition
assimilation. Confidence is never used as an observation likelihood.

Every attempt records route, attempt ID, note/source IDs, event/availability/receipt
times, accepted evidence IDs, status, result kind, cache hit and model invocation
count. Built-in model adapters expose actual invocations via their `calls` counter;
fixture attempts have zero model calls. Per-decision diagnostics additionally record
usable evidence among eligible students. Episode diagnostics count attempts over
the whole run; their eligible-evidence counts describe the final estimate state.

## R04 common-history comparison

`live_snapshot_comparisons` now executes one shared gold-matched decision and
transition, then forks the controller before cutoff 2 extraction. Both branches
inherit the same notes, administrative history, prior beliefs, past action,
remaining budget, mentor resources, planner state and frozen fairness cohorts.
The branches differ only in gold versus injected extraction. Each allocation goes
through the independent validator. The comparison asserts identical selected notes,
eligibility, programme histories, budgets and mentor resources.

No post-fork outcomes are reused. Ordinary closed-loop runs continue to generate
each branch's observations from its own subsequent transitions. This conditional
snapshot diagnostic does not estimate full-trajectory extraction effects.

The output identifies `EXERCISED`, `UNAVAILABLE / NOT EXERCISED` (zero injected
attempts), or `UNAVAILABLE / UNUSABLE` (no newly usable monitoring evidence among
eligible students). Zero-attempt belief/risk/benefit/disagreement metrics are null.
Failed attempts can still have measured downstream differences, explicitly labeled
unusable; they are never extraction agreement. Rank correlation is null for
unexercised/unusable comparisons or constant benefit vectors. Diagnostics include
attempts, model invocations, cache hits, accepted/quarantined results, selected
notes, usable-evidence counts and compared cutoffs. Common history, both snapshots,
attempts, selection and both allocations are saved with each comparison.
The live runner writes its total invocation count after the snapshot comparisons,
and splits closed-loop and snapshot invocations; the newly exercised snapshot calls
are therefore included in the total. An offline counter fixture independently
checks 8 closed-loop plus 3 snapshot invocations equals 11, without calling a model.

## Actual strict-ranking counterexample

The final [verification artifact](../results/phase2_20261109_verification_v3/verification.json)
uses 3 students, 1 mentor, 3 months, seed 42, a budget of 10, 1 admission and
5 appointments per month, and a monitoring bound of 3. No binding fairness target
forces the result. Both runs admit SYN00001 in month 1; the first post-transition
conditions are stable/vulnerable/vulnerable for SYN00001/2/3. Both receive the exact
same notes through cutoff 2. SYN00002 reports assignment difficulty; SYN00003 reports
low participation. Only the extraction of SYN00003's month-1 note changes.

| Quantity at cutoff 2 | Perfect extraction | Valid empty extraction for SYN00003 |
|---|---:|---:|
| SYN00003 stable probability | 0.3602450203 | 0.6294418125 |
| SYN00003 vulnerable probability | 0.3389485879 | 0.2546595030 |
| SYN00003 disengaged probability | 0.3008063917 | 0.1158986846 |
| SYN00003 withdrawn probability | 0 | 0 |
| SYN00003 WAIT endpoint risk, 2 remaining months | 0.1069817606 | 0.0578051724 |
| SYN00003 incremental retention benefit | 0.0371695820 | 0.0197629590 |
| SYN00002 incremental retention benefit | 0.0204329497 | 0.0204329497 |
| Selected student | SYN00003 | SYN00002 |
| Remaining budget after months 1, 2, 3 | 5, 0, 0 | 5, 0, 0 |

Both choices have strictly greater benefit than the alternative; the small omitted
case gap is still well above the planner's numerical objective tolerance. Both
allocations are feasible. This is evidence of downstream sensitivity, not evidence
of improved retention or fairness. A changed risk can increase or decrease with
evidence, elapsed time and remaining horizon; no monotonic improvement is required.

The exact accepted trace is:

1. Note `SYN00003:1:note`, source event `SYN00003:1`, event month 1,
   available/received at cutoff 2, text “The school reports low participation in recent activities.”
2. Injected attempt `SYN00003:1:note:extract:2`, accepted supported result.
3. Evidence `f21dd964bf639d9b29010eda78d5bd3da06460466254c0d8d831a5c0d029ae0f`.
4. Estimate `e5f66de160d461f74318232b0d21fd4b0f7d1619cc35e88534e30fe1473e6ca4`.
5. Risk `input_estimate_id` is exactly that estimate ID; probability 0.10698176059375486.
6. Cutoff-2 immutable snapshot selects SYN00003, spending the remaining 5 units.

The empty extraction retains the prior evidence and produces estimate
`23f63c16e9aca143a4f0ac82880f5badf68304217117b98cd6ff34efbf8509c2`; its risk references
that exact ID. Each complete controlled episode makes **6 injected fixture attempts**,
all accepted, zero cache hits, zero model invocations and zero quarantines.

The final bounded snapshot harness separately compares B/C and noisy D-matched/D:

| Extractor | Injected attempts across both contrasts | Max belief L1 difference | Assignment disagreement rows | Status |
|---|---:|---:|---:|---|
| Perfect fixture | 4 | 0 | 0 | EXERCISED |
| Controlled omission | 4 | 0.5383935843 | 2 | EXERCISED |
| Always failing fixture | 4 | 0.6411757565 | 4 | UNAVAILABLE / UNUSABLE |

Disagreement rows are student-level changes: replacing one selected student creates
two rows. They are not independent replications. Each contrast uses two selected
cutoff-2 monitoring notes. D deliberately uses a declared misleading-note probability
of 1 in this small harness to ensure available corrupted evidence; the complete
configuration is saved. Live-model calls are zero. A separate zero-bound regression
checks NOT EXERCISED with null comparison metrics.

The initial harness using the broader research configuration produced unavailable
tiny comparisons because of its omission/delay channel. It was not counted as
agreement or deleted. Final artifacts use a new `verification_v3` directory; the
earlier diagnostic versions remain separate. Version 2 demonstrated sensitivity
but included a tie in the omitted arm; version 3 supplies the strict-ranking result.

## Verification and resources

The [new regression module](../tests/test_phase2_correctness.py) covers actionable
strict-order changes, pre-admission injected calls, bounded calls with zero
programmes, full structured access, clean/noisy matched equality, schema/JSON/
unsupported/forged/exception quarantine, empty/unknown/conflicting evidence,
source-time delays, future-cutoff rejection before mutation, hidden-state
invariance, duplicates, deterministic reruns, cache hits, offline replay and
all-mode feasibility. Existing legacy call-limit tests are retained with the
explicit historical contract; no budget or information assertions were removed.

Independent checks use the existing allocation validator and episode validator,
separately from planner objectives. They enforce enrolled/unadmitted eligibility,
one programme per student, mentor compatibility, capacity, appointment limits,
whole-programme prices and budget balance. Snapshot validation requires the current
estimate and exact risk input identity. The environment remains the sole transition
authority. Phase 1 regressions are unchanged and pass.

The [bounded end-to-end comparison](../results/phase2_20261109_comparison/report.md)
completed **17 runs**, 6 students over 3 months at seed 42, with a programme bound
of 1 and monitoring bound of 2. Injected attempt counts were 8 for resource/C,
7 for resource/D, 8 for fairness/C and 8 for fairness/D: **31 total**, including
**24 monitoring attempts**. All were accepted, with zero quarantines and zero
live-model calls. Each spending policy used two programmes and 10 units; WAIT used
zero. These tiny synthetic outcomes are not comparative effectiveness evidence.

Commands (repository root; output paths must be new):

```sh
/tmp/phase1-python312/bin/python -m unittest tests.test_phase2_correctness tests.test_phase1_correctness tests.test_feedback_closed_loop tests.test_feedback_extraction tests.test_feedback_estimation tests.test_research_information tests.test_extraction_evaluation -v
/tmp/phase1-python312/bin/python -m unittest discover -s tests
/tmp/phase1-python312/bin/python scripts/verify_phase2.py --output results/phase2_new_verification
/tmp/phase1-python312/bin/python -m src.main --extractor fixture --students 6 --mentors 1 --months 3 --budget 10 --seed 42 --max-notes-per-month 1 --max-monitoring-notes-per-month 2 --output results/phase2_new_comparison
git diff --check
```

Supported interpreter: CPython **3.12.12** in the pre-existing verification venv;
the original workspace venv was 3.14.8, outside the declared supported range.
Focused verification passed **64 tests**, including **15 Phase 2 tests**.
The first full run passed **252 tests** in 46.136 seconds; an intermediate run
passed **254 tests** in 43.909 seconds after adding temporal/resource checks.
Final full-suite evidence, including aggregate invocation accounting, is recorded below.

Editor diagnostics were clean for the controller, runners, replay, comparison,
new tests and verification script. The editor reported an existing relative-import
package-root diagnostic in the extractor's unchanged import line; Python 3.12
imports and the runtime suite pass. No import-layout change was made for that
editor-only diagnostic.

## Changed and created files

| File | Change |
|---|---|
| [closed_loop_controller.py](../src/school/closed_loop_controller.py) | Bounded selection, injected monitoring, validation/audit records, cutoff guard and one-month commit method for forks. |
| [observation_extractor.py](../src/intervention/observation_extractor.py) | Revalidate injected batches and evidence identities. |
| [research_experiments.py](../src/evaluation/research_experiments.py) | Shared-history comparisons, non-vacuous diagnostics and saved traces. |
| [research_evaluation.toml](../configs/research_evaluation.toml) | Explicit extraction contract and separate monitoring bound. |
| [feedback_experiments.py](../src/school/feedback_experiments.py) | Configuration, CLI and audit persistence. |
| [feedback_replay.py](../src/school/feedback_replay.py) | Restore selection contract, bound and per-student quality; legacy manifest default. |
| [simulation_comparison.py](../src/school/simulation_comparison.py) | Expose bounds and attempt/model/cache diagnostics. |
| [main.py](../src/main.py) | New CLI options without changing programme-cap semantics. |
| [school.py](../src/school/school.py) | Correct the feedback API docstring. |
| [test_feedback_closed_loop.py](../tests/test_feedback_closed_loop.py) | Label legacy routing and count injected attempts separately from gold attempts. |
| [test_phase2_correctness.py](../tests/test_phase2_correctness.py), new | Reproductions and Phase 2 acceptance regressions. |
| [verify_phase2.py](../scripts/verify_phase2.py), new | Reproducible offline evidence harness using explicit test fixtures. |
| [README.md](../README.md) | Current defaults, limits, legacy behavior and report navigation. |
| This document, new | Implementation rationale, evidence, development amendment and scope limits. |

## Remaining research scope

This dated development amendment describes implemented Phase 2 behavior; it does
not rewrite the [historical research protocol](research_evaluation_protocol.md),
validate historical results or authorize interpreting the old primary experiment
under new sampling defaults. Future substantive research runs require their own
frozen inputs and explicit protocol amendment. Historical result files and the
Phase 1 implementation/report are unchanged.

Programme feedback remains non-actionable for its recipient after atomic admission.
Repeat/continuing support, switching, scheduling, multi-week commitments and later
Phase 3/4/5 work are deferred. This phase establishes actionable monitoring-language
extraction only; it does not solve the full intervention-feedback research question.
The grammar, emission likelihoods, transition effects, group-quality channels and
uncertainty rules remain synthetic. No trained risk model, calibrated LLM confidence,
new fairness definition, population-generalization claim or live Ollama evaluation
is introduced. All work remains reviewable on the working branch; no commit, push,
PR or merge was performed.

## Final acceptance

The final offline suite passed **255 tests in 43.793 seconds** on CPython 3.12.12:
[complete test log](../results/phase2_20261109_verification_v3/offline_tests_final.log).
The final focused suite passed **64 tests in 0.948 seconds**:
[focused test log](../results/phase2_20261109_verification_v3/focused_tests_final.log).
`git diff --check` passes. No unresolved runtime test failures remain.

| Mandatory criterion | Result and evidence |
|---|---|
| R01 actionable monitoring | PASS: strict benefit ordering reverses and changes month-2 admission; month-1 action and transition remain identical. |
| Injected extractor actually called | PASS: 6 monitoring fixture attempts in each controlled episode; 24 monitoring attempts in the broader offline comparison. |
| B/C and D-matched/D isolate extraction | PASS: shared pre-decision history, identical notes/selection/resources; perfect extraction yields identical beliefs, risks and assignments. |
| R04 zero-attempt honesty | PASS: NOT EXERCISED and null metrics; always-failing attempts are counted and labeled UNUSABLE. |
| Missing, malformed and conflicting evidence | PASS: empty/unknown/conflict distinctions, schema/identity/span/entailment checks and auditable quarantine; no gold fallback. |
| Exact risk/estimate identity | PASS: current snapshot validation plus saved evidence-to-estimate-to-risk trace. |
| Temporal and hidden-information safety | PASS: delayed source-time replay, future-cutoff precheck, immutable historical snapshots, fixed-record hidden-state invariance. |
| Resources and atomic eligibility | PASS: independent validators, all information modes, no repeat admissions, balanced nonnegative budgets. |
| Phase 1 preserved | PASS: unchanged Phase 1 regressions and all existing tests pass. |
| Supported full-suite execution | PASS: 255 tests on Python 3.12.12. |
| Bounded offline experiment | PASS: strict-ranking verification plus 17-run end-to-end comparison, zero live model calls. |
| Reproducibility and fresh artifacts | PASS: deterministic reruns, cached extraction, duplicate handling, saved offline replay; new versioned result directories. |
| Scope and limitations documented | PASS: monitoring sensitivity only; programme continuation and Phases 3–5 remain deferred. |

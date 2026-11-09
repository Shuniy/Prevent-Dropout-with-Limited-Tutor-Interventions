# Phase 2 scientific correctness: finalization record

Verified locally on 2026-11-09 on branch `fix/phase-2-llm-correctness`.
The clean starting revision was `a7e835c96120cc25401175ee704da9e988d8072c`,
which already contains the earlier Phase 2 implementation. The historical claim
of 255 passing tests described that earlier implementation, not the changes here.
The corrections described below are working-tree edits on that revision.
No commit, push or merge was performed during this finalization.

The verified runnable source/configuration fingerprint is
`8eaea7851c91652def46f3f8f3e9951b0c6d1ca26a8ca104ce4ac42ac855a32f`.
The generated record includes SHA256 for every source, test, script, configuration
and workflow file, including uncommitted files. Documentation is excluded to avoid
a circular fingerprint when quoting verification results. A commit SHA alone
does not identify these uncommitted corrections.

## Changes and root causes

| Issue | Previous behavior | Corrected behavior |
|---|---|---|
| Historical actionable evidence | Episode diagnostics consulted final eligibility and final estimates, losing evidence coverage when the recipient was admitted. Parsed facts were used as a proxy for assimilation. | Store eligibility and usable evidence at each pre-allocation cutoff. Intersect newly accepted evidence IDs with IDs the estimator actually assimilated. Preserve historical counts after admission. |
| Failure replay | Only successful batches were reconstructed. Exceptions became missing-fixture errors, invocation/cache provenance was lost, and custom authorized inputs were regenerated differently. | Replay recorded outcomes, authorized observations and exact notes. Revalidate accepted batches; replay quarantines with original reason/type and preserve invocation/cache audits. Restore recorded planner failure mode instead of the scenario default. |
| Verification record | Documentation linked local ignored artifacts as if available from the branch and ambiguously described the commit history. | Record actual HEAD, branch, working-tree source fingerprints, Python/dependencies, commands, results and traces. Clearly distinguish local artifacts from repository content. |

Production changes are limited to
[closed_loop_controller.py](../src/school/closed_loop_controller.py),
[state_estimator.py](../src/school/state_estimator.py),
[observation_extractor.py](../src/intervention/observation_extractor.py),
[feedback_replay.py](../src/school/feedback_replay.py),
[feedback_experiments.py](../src/school/feedback_experiments.py) and
[simulation_comparison.py](../src/school/simulation_comparison.py).
The comparison CSV now accommodates the additional diagnostic fields; baseline
coverage fields that do not apply are null.

Five new regression tests in
[test_phase2_correctness.py](../tests/test_phase2_correctness.py) cover historical
coverage after admission, rejected/uninformative/zero-likelihood evidence,
duplicate evidence at the same and later cutoffs, eight replay outcome cases,
and incomplete recordings. Existing Phase 1 and Phase 2 tests remain.
The new reproductions failed before production changes; subsequent targeted
integration tests passed. The full final suite below includes all existing tests.

## Diagnostic definitions

`extraction_diagnostics(month)` describes that stored decision cutoff, even
when queried after the episode has ended. Its counts include eligible students,
those with previously usable evidence, those with usable evidence after this
cutoff's assimilation, and those with newly usable injected evidence.
`new_usable_student_ids` permits auditing membership, including recipients
admitted immediately afterward.

`extraction_diagnostics()` reports historical episode coverage:

- `historical_students_with_usable_injected_evidence`: distinct students
  receiving newly assimilated injected condition evidence while eligible.
- `historical_student_cutoff_pairs_with_new_usable_evidence`: distinct
  eligible student–decision-cutoff pairs with such evidence.
- `actionable_extraction_opportunities`: selected injected attempts for
  eligible students at actual decision cutoffs, including failed attempts.
  This is after the selection cap, not all available candidate notes.
- `eligible_students_with_usable_evidence` and
  `eligible_students_with_new_usable_evidence` retain their existing names:
  at episode scope they are historical distinct-student unions, not final
  eligibility counts. The latter aliases historical injected coverage.
- `final_students_eligible`, `final_students_previously_admitted` and
  `final_students_enrolled` are separate fields emitted only after completion.

Attempt, accepted, quarantine, empty, unknown and conflicting counts describe
injected extraction. Empty/unknown/conflicting are subsets of accepted results;
schema acceptance does not imply a usable Bayesian condition update.
Selected-note counts include all extraction routes. Gold and injected routes
remain explicit in individual attempt records.

The estimator's new audit field `assimilated_condition_evidence_ids` identifies
condition emissions that actually passed Bayesian assimilation. Workflow-only,
unknown, conflicting, duplicate and zero-likelihood reports cannot create new
usable coverage. Existing source-time filtering, freshness, posterior computation
and estimate identities are unchanged. Terminal cutoff T+1 contributes extraction
totals but cannot create an actionable student–decision-cutoff pair.

## Replay contract

The recorded-outcome adapter never invokes a language model. It preserves note
and student identities, source events and times, cutoff, gold/injected route,
result category, evidence IDs, original failure type/reason and cache/invocation
audit. Failure records are now saved after invocation/cache metadata is attached.
A recorded `RuntimeError("model unavailable")` remains that historical failure;
it is not re-raised by contacting the original model or replaced by gold evidence.

Replay checks selected notes, batches, accepted/quarantined attempts, failure
records, estimate updates, risk identities, decision snapshots, cutoff diagnostics,
authorized records, allocations including mentor assignments, budget trajectories
and evaluator-only conditions. Complete allocation records are compared except
solver wall-clock runtime. Missing or inconsistent outcomes fail replay.

Per-attempt invocation/cache values remain the original execution's provenance.
The replay manifest and summary separately report `original_model_invocations`,
`original_cache_hits` and `replay_model_invocations` (zero). They must not be
added together as newly performed inference.

## Actual verification

Interpreter: CPython **3.12.12**, `/tmp/phase1-python312/bin/python`.
Key installed dependencies: NumPy **2.3.5**, SciPy **1.18.1**, pandas **2.2.3**,
jsonschema **4.26.0**, matplotlib **3.11.2**. The generated record contains the
complete installed distribution/version inventory. The selected workspace's
earlier Python 3.14 environment was not used for verification.

| Check | Result |
|---|---|
| Required focused suite, including Phase 1 | 69 tests passed in 1.164 seconds |
| Complete offline suite | 260 tests passed in 44.960 seconds |
| Phase 2 module alone | 20 tests passed, including five new regression methods |
| Deterministic extraction sensitivity | Passed; shared month-1 history, different feasible month-2 admission |
| Successful, empty, mixed and failed replay | All histories, decisions, assignments, budgets and truth matched |
| Actual model calls in harness / new calls in replay | 0 / 0 |
| `git diff --check` | Passed |

Exact commands executed from the repository root:

```sh
/tmp/phase1-python312/bin/python -m unittest tests.test_phase2_correctness tests.test_phase1_correctness tests.test_feedback_closed_loop tests.test_feedback_extraction tests.test_feedback_estimation tests.test_research_information tests.test_extraction_evaluation -v
/tmp/phase1-python312/bin/python -m unittest discover -s tests
/tmp/phase1-python312/bin/python scripts/verify_phase2.py --output results/phase2_finalization_20261109
git diff --check
```

[verify_phase2.py](../scripts/verify_phase2.py) now runs and records the two test
commands and diff check itself, then executes the deterministic experiments and
replays. It rejects unsupported Python versions, existing output directories,
changing source files during verification and failed test/check results.

The local artifact directory is `results/phase2_finalization_20261109/`.
It contains `verification.json`, `focused.log`, `offline.log`,
`diff_check.log`, both sensitivity episodes, matched comparisons and four
original/replayed episode pairs. These artifacts are intentionally ignored by
Git and are **not claimed to be committed or available on GitHub**.
To recreate them, use a supported environment with the recorded dependencies
and run the harness with a fresh directory, for example:

```sh
python scripts/verify_phase2.py --output results/phase2_reproduced_01
```

A minimal [offline CI workflow](../.github/workflows/offline-tests.yml) runs the
suite on Python 3.12 and 3.13. It has been added locally; no GitHub Actions run
has been claimed. The actual results above are local Python 3.12 results.
Editor checks still report package-root relative-import diagnostics and lint
warnings; they are not a clean-editor claim. Supported-runtime imports and all
offline tests pass.

## Controlled evidence-to-allocation trace

The fixture uses 3 students, 1 mentor, 3 months, seed 42, budget 10,
one admission and five appointments per month, and a monitoring bound of 3.
Both arms admit SYN00001 in month 1 and have identical first transitions.
They receive identical notes through cutoff 2; only SYN00003's month-1
extraction is changed to an accepted empty batch in the omission arm.

| Cutoff-2 quantity for SYN00003 | Supported extraction | Empty extraction |
|---|---:|---:|
| Stable probability | 0.3602450203 | 0.6294418125 |
| Vulnerable probability | 0.3389485879 | 0.2546595030 |
| Disengaged probability | 0.3008063917 | 0.1158986846 |
| Two-month WAIT withdrawal risk | 0.1069817606 | 0.0578051724 |
| Incremental retention benefit | 0.0371695820 | 0.0197629590 |
| SYN00002 benefit | 0.0204329497 | 0.0204329497 |
| Selected student | SYN00003 | SYN00002 |
| Remaining budget after months 1, 2, 3 | 5, 0, 0 | 5, 0, 0 |

The supported note `SYN00003:1:note` cites source event `SYN00003:1`,
event month 1, available at cutoff 2:
“The school reports low participation in recent activities.”

- Accepted evidence: `f21dd964bf639d9b29010eda78d5bd3da06460466254c0d8d831a5c0d029ae0f`.
- Resulting estimate: `e5f66de160d461f74318232b0d21fd4b0f7d1619cc35e88534e30fe1473e6ca4`.
- The cutoff-2 risk's `input_estimate_id` exactly equals that estimate ID.
- The feasible cutoff-2 allocation admits SYN00003 and spends the remaining 5 units.

At cutoff 2 there are two eligible students and two with newly usable evidence
in the supported arm. SYN00003 remains in historical coverage after admission.
Episode totals are **3 distinct students**, **6 student–cutoff pairs**, and
**6 actionable extraction opportunities**; final state is **1 eligible**,
**2 previously admitted**, **3 enrolled**. The omission arm has five newly
usable student–cutoff pairs. Each arm has six accepted fixture attempts and
zero model invocations.

The shared-history gold/extracted comparison also remains exercised:

| Extractor | Attempts across both contrasts | Max belief L1 | Student assignment disagreement rows | Status |
|---|---:|---:|---:|---|
| Perfect | 4 | 0 | 0 | EXERCISED |
| Omission | 4 | 0.5383935843 | 2 | EXERCISED |
| Always failing | 4 | 0.6411757565 | 4 | UNAVAILABLE / UNUSABLE |

The separate zero-attempt regression still requires NOT EXERCISED and null
agreement metrics. Disagreement rows are not independent replications.

## Extraction replay evidence

| Offline case | Attempts | Accepted | Quarantined | Decisions reproduced | New replay model calls |
|---|---:|---:|---:|---:|---:|
| Supported | 6 | 6 | 0 | 3 | 0 |
| Empty | 6 | 6 (all empty) | 0 | 3 | 0 |
| Mixed supported/failure | 5 | 4 | 1 | 3 | 0 |
| Model unavailable | 6 | 0 | 6 | 3 | 0 |

Original and replayed extraction outcome records are included side by side in
the generated verification record. All six unavailable outcomes retain
`error_type="RuntimeError"` and `reason="model unavailable"`.
All original harness cases also make zero real model calls.
Additional tests cover accepted unknown/conflicting facts, invalid-evidence
quarantine and cached outcomes. Invocation counters in those mocked provenance
tests are synthetic; they are not evidence of live-model execution.

## Preserved behavior and remaining limits

The actionable monitoring route and separate bounded monitoring-note cap remain.
The programme-note cap retains its original meaning. Structured/oracle modes,
matched-note controls, legacy programme-only routing, source-time availability,
non-vacuous shared-history comparisons, exact risk/estimate linkage and independent
feasibility checks remain tested.

No transition probability, optimizer objective, fairness constraint, resource
meaning or one-programme eligibility rule changed. The environment remains the
sole authority for hidden conditions and actual intervention outcomes. Hidden
conditions are not supplied to an extractor or ordinary planner.

Replay requires complete current-format records. Older batch-only archives or
older audit schemas may be rejected; no exact reconstruction is claimed for
missing failure metadata. Arbitrary robust/custom policy configurations and
custom environment dynamics are not reconstructed by this small replay adapter.
Recorded authorized inputs are replayed; this does not independently validate
their original generation. Time-limited solver behavior and different numerical
library versions may prevent exact allocation reproduction.

These are synthetic development checks, not effectiveness, calibration or
fairness evidence for a real student population. No live Ollama evaluation,
programme continuation, switching, session scheduling, trained risk models or
new intervention types were added. Historical research results are not
reinterpreted under the new monitoring defaults.

**Recommendation:** the targeted Phase 2 finalization is ready for merge review
within these limits. Committing, pushing and merging remain separate user actions.

# Phase 3: experimental correctness and reproducibility

This is an implementation and offline verification record, not a new research
protocol or evidence that mentoring prevents real school dropout. The starting
checkout was clean at `9014ae3a9209032c4c752a8ec9054cab4101742c`. The corrections
below are uncommitted working-tree changes. No historical experiment was rerun,
overwritten, or relabelled. The restored historical evaluation protocol remains
unchanged.

## A — Common information-controlled policy execution

The controller accessed planner-only matrix attributes both when initializing
the estimator and when calculating diagnostic benefits. All five baselines
therefore raised `AttributeError`. The console comparison separately used an
oracle baseline simulator, confounding policy choice with information access.

[ClosedLoopCMDPController](../src/school/closed_loop_controller.py) now accepts
independent `wait_matrix` and `treatment_matrix` assumptions. Defaults are the
usual-support matrix and scenario programme matrix; an explicitly supplied
estimator supplies default diagnostic matrices. Explicit diagnostic overrides
remain independent of estimator and allocation-model assumptions. The policy
contract remains `plan(decision_state) -> AllocationResult`.

The [comparison runner](../src/school/simulation_comparison.py) sends every
selected policy through the same controller for each information mode. Only
`oracle` uses privileged conditions. `terminal_value` is canonicalized to
`resource` to avoid duplicate aliases. The five baselines and resource/fair
planners yield 35 default policy/mode cells; optional `--feedback-policies
resource fairness robust` includes the robust planner. Fixture modes make no
model calls. Live note modes now also process baseline notes, so their workload
is larger than the former oracle-only baseline comparison.

Severity uses the authorized MAP condition. An unavailable estimate ranks below
every known condition; missing estimates tie by student ID. Random uses the
recorded policy seed and decision month, independent of environment streams.
Baseline allocation records retain `status=baseline` and empty solver settings.
No fake solver execution is introduced. The old sweep remains a separately
labelled `privileged_oracle_diagnostic`; it is not an ordinary-information control.

The independent allocation validator still runs before the environment's own
validation and accounting. Identical initial authorized observations produce
identical initial snapshots across policy families. Actions may change subsequent
causal histories, observations, and trajectories. Observation-driven severity
ranking changes are legitimate; replacing hidden conditions while retaining the
authorized inputs cannot change a decision snapshot.

## C — Fairness configuration

The research policy factory and feedback experiment factory omitted the enabled
flag. Named `FairPoint` and `FairRobust` research policies now reject
`fairness_enabled=False` before execution; `ResourceOnlyPoint` is the labelled
resource-only ablation. Generic construction honors disabled fairness for both
point and robust planners. The point planner then uses the resource-only
objective; the robust planner retains its robust benefit objective without
access constraints. Zero target remains a documented trivial access constraint.

Effective settings now include enablement, target, window, grouping and shortfall
mode. Scenario fairness settings separately govern the evaluator's audit, which
remains available for WAIT, baselines, resource-only and disabled-fairness policies.
An explicitly supplied planner may have a different target from the evaluator;
both are serialized separately. No fairness target formula, normalized shortfall
objective, or tie-breaking objective was changed.

A two-student, one-programme, zero-benefit example makes the distinction visible:
enabled access fairness allocates one place; disabling it allocates none after
cost minimization. Both point and robust implementations satisfy this example.

## D — Monetary zero versus no service

The experiment runner treated `budget == 0` as a reason to require identical
hidden trajectories. That is false when a feasible programme costs zero.

The runner now distinguishes identical transition dynamics (`effect_strength=0`
in this benchmark) from no feasible service. The homogeneous benchmark has no
service when it has no mentors, no admission capacity, fewer than five appointment
slots per mentor, or insufficient budget for a programme. Affordability uses the
same exact decimal arithmetic as the resource validator. A zero monetary budget
alone imposes no extra restriction on a free programme.

The constructed counterexample uses the existing transition matrices and a fixed
shared draw of `.975`: a vulnerable student's usual-support withdrawal threshold
is `.97`, while the programme threshold is `.98`. Free positive-effect support
can therefore change hidden transitions without spending money. This previously
raised the runner's trajectory-invariant error. Separate tests retain zero-effect
equality, paid-service zero-budget equality, free-service capacity limits, and
budget conservation. Neither transition matrices nor treatment-effect assumptions
were modified to obtain these results.

## B — Versioned exact replay

The old factory recognized only resource and point-fair class names and rebuilt
some settings from scenario defaults. Robust settings, explicit planner dynamics,
effective fairness parameters, and full resource/fairness records were incomplete.

[policy_configuration.py](../src/school/policy_configuration.py) provides an
explicit type registry and reconstruction version. Baselines store their name
and policy seed. Planners store both matrices, solver settings, fairness parameters,
and, for robust planning, the complete uncertainty configuration. Unknown policy
implementations are rejected rather than guessed from class names.

Episode replay contract version 3 stores:

- Exact synthetic student inputs and mentor calendars/prices under evaluator-only
  reconstruction storage, plus actual environment matrices and scenario seeds.
- Independent controller diagnostic matrices, estimator prior/likelihoods/matrices,
  policy configuration, risk identities and effective fairness configuration.
- Observation configuration, note corruption and per-student overrides, monitoring
  and programme limits, extraction route contract, exact notes, validated outcomes,
  failures, cache audits and invocation provenance.
- Source/configuration hashes, dataset hash, Git/dirty identity, interpreter and
  resolved dependency versions, extractor adapter/model identity, prompt/schema
  hashes, experiment identity, and a content-derived episode identity.
- Authorized events and administrative records, assimilation updates, final beliefs,
  risk estimates, decision snapshots, assignments, complete environment ledgers,
  fairness windows, and evaluator-only hidden trajectories.

Replay uses recorded observations and outcome adapters; it never constructs a
live extractor. Accepted batches are revalidated, failures remain quarantined,
and original cache/invocation audits are preserved as historical provenance.
Configuration identity and file inventory hashes are checked before execution.
All applicable deterministic records and restored settings are compared before
writing a successful replay result. Only allocation wall-clock runtime is removed
from equality checks. The result includes a deterministic trace digest.

The current source/configuration and Python/dependency versions must match the
recording. Old incomplete records explicitly fail instead of taking new defaults.
Restoring a recorded checkout/environment is necessary for replay across later
implementation changes. Arbitrary policy subclasses, externally mutated private
environment state, and unrecorded custom scheduling/model behavior are outside the
reconstruction contract. Solver time limits remain wall-clock sensitive: if they
change an actual solve outcome, exact replay fails rather than accepting a
different allocation. Recorded LLM outcomes can be replayed without claiming that
a fresh model invocation is deterministic. A basic live extractor may record a
model tag without a weight digest; the research cached extractor records the digest.

## E — Immutable provenance and amendments

The old freeze implementation overwrote the single manifest and frozen protocol.
Aggregation silently skipped summaries from other input digests, and cache keys
omitted some execution inputs.

[provenance.py](../src/evaluation/provenance.py) supplies shared provenance and
integrity checks. New research runs retain:

```text
configuration_manifest.json                 # original, never replaced
protocol.json                               # original, never replaced
research_evaluation_protocol_frozen.md       # original, never replaced
current_version.json                        # mutable active pointer only
versions/<full-content-identity>/
  configuration_manifest.json               # includes predecessor and reason
  protocol.json
  research_evaluation_protocol_frozen.md
  episodes/<phase-policy-mode-seed-token>/
    execution.json
    trace.json.gz
    replay/                                 # complete version-3 replay record
    ... scorecards ...
    summary.json
    artifact_integrity.json
  aggregation_status.json
  ... tables and reports for this version ...
```

Unchanged freezes are idempotent. Changed inputs require a nonempty amendment
reason and create a new identity linked to its predecessor. Root compatibility
copies remain the original bytes. New runs, gates, tables and reports use the
active version directory. Historical unversioned manifests are rejected for new
execution or in-place amendment; preserve them and choose a new run directory.

Identity includes source and configuration fingerprints, dataset hash, full
protocol text, Git revision and dirty execution-input identity, Python/platform
and installed dependencies, effective planner and estimator settings, uncertainty,
seeds, solver configuration, extraction contract and experiment configuration.
Only explicit runtime fields are collected; environment variables and credentials
are not serialized. Exact episode outcomes and initial world are also hashed.

Cache reuse requires compatible complete execution identity including phase,
setting, mode, seed, model/extractor identity, and all supported overrides. A cache
hit must pass artifact-integrity checks. Aggregation rejects other experiment
identities, incompatible model versions within an information mode, differing
execution settings within one reported cell, and missing/corrupt scorecards.
It reports missing primary cells and failed/incomplete directories. Failed
execution retains failure metadata without a successful summary marker. Extraction
quarantines and explicitly configured solver-WAIT fallbacks remain recorded
episode behavior, not evidence of successful extraction or optimization.

`python scripts/verify_experiment_records.py <run-directory>` independently checks
retained manifests, protocol bytes, predecessor chains, original copies and
completed episode file inventories without requiring today's checkout to match.
This is filesystem integrity verification, not protection against an adversary
rewriting both artifacts and hashes. Interrupted/failed cells are retained; there
is no automatic retry that overwrites them. Use a fresh run identity/directory.

## Reproductions and regression evidence

New tests in [test_phase3_correctness.py](../tests/test_phase3_correctness.py) were
run before their corresponding production fixes:

| Task | Reproduced defect | Corrected evidence |
|---|---|---|
| A | 21 baseline constructor errors across modes and repeat test | Every baseline runs three months in four ordinary modes; common inputs, feasible resources, missing severity and seeded repeat checks |
| C | Both named fair policies failed to reject disabled constraints | Early rejection and hand-checkable enabled/disabled point/robust allocations |
| D | Fixed-draw free-service runner raised the old invariant | Free intervention diverges legitimately; no-service and zero-effect controls remain equal |
| B | Eight unsupported/incomplete reconstruction cases | All baseline types, resource, fair enabled/disabled, nondefault robust and estimator/model settings replay; repeated digests match |
| E | Original manifest bytes changed; incompatible aggregation did not raise | Linked amendments preserve prior manifest and held-out episode bytes; complete caches, failures and corruption are checked |

The initial full suite passed **260 tests in 45.171 seconds** on CPython 3.12.12.
During implementation, a full run found one obsolete missing-severity assertion
and 20 replay subtest errors caused by mutating the parsed emission configuration
from JSON lists to tuples. The replay code now copies that dictionary before
conversion. The prior severity test now verifies the explicitly requested missing
estimate behavior while retaining its immutability and hidden-state assertions.
The subsequent focused regression run passed **54 tests in 14.769 seconds**.

The prior comparison test now expects the common 35-cell pipeline; the old
manifest-amendment test now requires preserved original bytes, and its old
silent-exclusion assertion now requires an incompatibility error. These are
intentional contract corrections, not removal of resource or information checks.
Phase 1/2 production observation assimilation, source-need rules, actionable note
selection, failure quarantine, and extraction provenance rules were preserved.

## Final verification record

Final execution on 2026-11-09 passed **275 tests, zero failures and zero errors**
in **60.024 seconds**. The focused Phase 1/2/3, research-information and comparison
suite passed **49 tests in 15.770 seconds**. The original 260-test suite is included;
15 new Phase 3 test methods exercise multiple policy/mode subcases.

Executed command:

```sh
/tmp/phase1-python312/bin/python scripts/verify_phase3.py --output results/phase3_verification_20261109_final
```

The harness executed and retained output for:

```text
/tmp/phase1-python312/bin/python -m unittest tests.test_phase3_correctness tests.test_phase1_correctness tests.test_phase2_correctness tests.test_research_information tests.test_simulation_comparison
Ran 49 tests in 15.770s
OK

/tmp/phase1-python312/bin/python -m unittest discover -s tests
Ran 275 tests in 60.024s
OK

git diff --check        # exit 0; no output
git status --short      # exit 0; 15 modified and 6 new source/test/documentation files
git diff --stat         # exit 0; tracked changes listed, new files also recorded by status/fingerprints

/tmp/phase1-python312/bin/python scripts/verify_experiment_records.py /Users/shuniy/Documents/projects/school-dropout/results/phase3_verification_20261109_final/immutable_records
verified_versions: 2
```

The bounded scenario uses **6 students, 2 mentors, 3 periods, budget 10, one
admission and five appointment slots per mentor/month, seed 73**. Forty
policy/mode episodes cover eight policies across all five modes. Every allocation
passed independent feasibility checks; initial snapshots matched across all
policy families within each mode. Eight saved noisy-note policy episodes were
each replayed twice, with identical deterministic digests and zero real model
calls. Four additional small research episodes exercised actual versioned
storage and aggregation. The amendment preserved all prior manifest and episode
bytes. Missing held-out cells remain reported as incomplete; this harness does
not claim completion of a research evaluation grid.

The separate fixed-draw controls produced these actual outcomes (WAIT first,
need-priority second):

| Control | Programmes | Remaining budget | Hidden trajectories equal? |
|---|---|---|---|
| Zero effect | 0 / 2 | 10 / 0 | Yes |
| Zero budget, paid service | 0 / 0 | 0 / 0 | Yes |
| Zero budget, free positive-effect service | 0 / 4 | 0 / 0 | No, legitimately |
| Zero budget, free service, insufficient appointment capacity | 0 / 0 | 0 / 0 | Yes |

Exact execution identity:

```text
Branch: fix/phase-3-repair-experimental-comparisons
HEAD: 9014ae3a9209032c4c752a8ec9054cab4101742c
Working-tree runnable source/test/script/configuration SHA256:
a2f5962c0cb9001fb8c5647ceae0c3160f800202d32ac904e7ccead4b17d6252
Tracked execution-input diff SHA256:
f892cd37d7bf7077abde71eba0963c67d030bc6325de85ca9a3cf8e204033dec
Initial immutable bounded research identity:
aed17df6f9ac3c446daa672e0f2de9e9963dffb9dae505194d9fe24fd5bab659
Amended immutable bounded research identity (radius .44):
48b90f3cfc821e955cd182f47e50c242ffc16b9945b9798507cc6910843cf69b
```

The source fingerprint includes uncommitted and untracked runnable files and
configuration; a commit SHA alone does not identify these corrections. Reporting
documentation is excluded to avoid a circular fingerprint. The restored protocol
is separately included in each immutable research identity. The working-tree
status and individual file hashes are retained with the verification record.
No commit or push was performed.

Runtime: **CPython 3.12.12**, `/tmp/phase1-python312/bin/python`,
`macOS-27.2-arm64-arm-64bit`. Resolved packages recorded in the environment:

```text
attrs 26.1.0; contourpy 1.4.0; cycler 0.12.1; fonttools 4.68.0;
jsonschema 4.26.0; jsonschema-specifications 2025.9.1; kiwisolver 1.5.1;
matplotlib 3.11.2; numpy 2.3.5; packaging 26.3; pandas 2.2.3;
pillow 13.0.0; pip 25.0.1; pyparsing 3.3.3; python-dateutil 4.0.0;
pytz 2026.6; referencing 0.37.0; rpds-py 2026.9.1; scipy 1.18.1;
tabulate 0.10.0; typing_extensions 4.16.0; tzdata 2026.6.
```

The [local verification record](../results/phase3_verification_20261109_final/verification.json)
contains all command exits, full file hashes, environment metadata, episode
results, replay digests and control outcomes. Complete command outputs are in
the adjacent `focused.log`, `offline.log`, `diff_check.log`, `status.log`,
`diff_stat.log` and `immutable_verification.log`. These generated artifacts live
in an ignored local results directory and are not distributed with the source.
The runnable harness and regression tests recreate them in a fresh directory.

Final diff inspection confirms no changes to transition matrices, optimization
objectives, source datasets, configuration files, the restored historical
protocol, or historical outputs/results. All Phase 1/2 regression tests pass.
Editor diagnostics were also inspected: namespace-package relative-import and
related type-resolution warnings remain in the workspace. Runtime imports and
tests pass; this report does not claim an entirely lint-clean editor workspace.

## Modified implementation and tests

- [closed_loop_controller.py](../src/school/closed_loop_controller.py),
  [baseline_policy.py](../src/school/baseline_policy.py),
  [allocation_policies.py](../src/school/allocation_policies.py),
  [simulation_comparison.py](../src/school/simulation_comparison.py), and
  [main.py](../src/main.py): common policy execution and optional robust comparison.
- [cmdp_environment.py](../src/school/cmdp_environment.py): evaluator-only initial
  reconstruction inputs; no change to transition or accounting algorithms.
- [cmdp_experiments.py](../src/school/cmdp_experiments.py): separate controls and
  explicit legacy oracle label.
- [fairness_planner.py](../src/school/fairness_planner.py): complete settings metadata.
- [policy_configuration.py](../src/school/policy_configuration.py),
  [feedback_experiments.py](../src/school/feedback_experiments.py), and
  [feedback_replay.py](../src/school/feedback_replay.py): versioned reconstruction.
- [research_experiments.py](../src/evaluation/research_experiments.py) and
  [provenance.py](../src/evaluation/provenance.py): immutable records and checks.
- [verify_phase3.py](../scripts/verify_phase3.py) and
  [verify_experiment_records.py](../scripts/verify_experiment_records.py): bounded
  offline verification and retained-record inspection.
- [test_phase3_correctness.py](../tests/test_phase3_correctness.py),
  [test_cmdp_reproducibility.py](../tests/test_cmdp_reproducibility.py),
  [test_research_information.py](../tests/test_research_information.py), and
  [test_simulation_comparison.py](../tests/test_simulation_comparison.py): regressions
  and corrected contract assertions; [README](../README.md): current usage.

## Scientific scope and deferred work

These are deterministic software and mathematical-contract tests in a
semi-synthetic benchmark. They do not establish causal effects, real dropout
prediction quality, calibrated uncertainty, fairness guarantees in real schools,
or natural-language extraction accuracy. The synchronized two-grade availability
assumption, atomic five-appointment intervention, fixed source population and
declared transition/observation models remain assumptions. No live LLM evaluation,
expensive full grid, trained risk model, multi-session scheduling, new population
generator, RAG, QLoRA, or agent orchestration was added. No historical numerical
results are validated by this phase.

## Final Phase 3 Review Repairs and Verification

This additional record starts from a clean
`fix/phase-3-repair-experimental-comparisons` checkout at
`68a97f61cf4e530177d1a8a407aaabfad40cd5a7`. It preserves the preceding
verification records. These corrections are working-tree changes on that commit;
the final executable source fingerprint and local results are recorded below.

### Reproductions and already satisfied contracts

The supported baseline was CPython 3.12.12 in
`/tmp/phase1-python312/bin/python`: **275 tests passed in 60.315 seconds**,
with no failures or skips. The selected workspace environment had been Python
3.14.8; it was not used for scientific verification. Resolved dependencies and
the clean source identity are retained in the new local `baseline.json`.

Seven regression methods were run against the original implementation before
production edits. All seven failed: aggregate CSV modification was undetected;
the wrong information mode could complete the primary matrix; a one-seed subset
was called the prespecified primary estimate; scoring failures lacked failure
records; sealing failures left successful summaries; late replay mismatches left
published destinations; and distinct endpoints had identical extractor identities.
The new `before_repairs.log` retains the actual failures.

Review then reproduced two additional invariant gaps: replacing a convenience
table link with an ordinary file hid the change, and actual controller settings
could differ from declared settings. Both failed in `reviewer_reproductions.log`
before correction. Expanded tests also found a report-rendering crash when only
FairPoint was available. The final implementation handles that partial state.

Existing protections were retained: source/protocol identity hashing, predecessor
chains, sealed completed episodes, exact-cell cache verification, independent
allocation validation, all baseline/controller information boundaries, explicit
oracle privilege, fairness enablement, and free positive-effect zero-budget
controls. The earlier regression tests were not weakened or removed.

### A: finalized derived-artifact contract

New experiment manifests use **manifest version 4**, report contract **1**, and
extractor identity **2**. The frozen experiment includes its primary design,
fully expanded execution defaults, planner/estimator configurations and declared
transition interpolation assumptions. Retained-record verification compares
against those frozen values rather than constructing today's policies or models.
It does not need the original checkout or invoke inference.

The three identities have distinct purposes:

1. The immutable experiment identifies source/configuration/protocol/runtime.
2. A completed episode records its execution identity, validated reconstruction,
   summary and sealed artifact inventory.
3. Each finalized aggregate/report generation records the experiment identity,
   contributing episode paths, summary identities, reconstruction identities and
   episode-seal digests, plus a SHA-256 digest for every generated artifact.

```text
versions/<experiment-identity>/
  configuration_manifest.json
  episodes/<cell-identity>/
    execution.json
    summary.json
    artifact_integrity.json
    ... unchanged scientific/reconstruction records ...
  reports/<unique-generation>/
    aggregation_status.json
    episode_results.csv
    primary_policy_comparison.csv
    exploratory_primary_comparison.csv
    ... aggregate tables ...
    research_results.md                      # report generations only
    figures/                                # report generations only
    report_manifest.json
    artifact_integrity.json
  report_generations.json                    # hash-linked retained inventory
  current_report.json                       # mutable convenience pointer
  .current_report -> reports/<generation>
  episode_results.csv -> .current_report/episode_results.csv
```

All regular files recursively inside a sealed generation are inventoried, except
its single root integrity file, which records the other digests. Nested files
with the same seal filename are still inventoried. Symlinks inside sealed
directories are rejected. Added, deleted, modified or substituted artifacts fail
verification, as do a deleted whole generation, broken registry, wrong source
episode identity or replaced finalized convenience link. New generations never
write through links into prior finalized bytes. The registry and current pointers
are updated under a filesystem writer lock.

Optional diagnostic inputs used by the renderer are copied into the generation
and covered by its seal. Their original working files and extraction caches are
inputs, not finalized reporting artifacts. The verifier's declared completed
scope covers immutable experiment records, every completed episode, every
registered finalized generation and its finalized convenience links. Private
staging/failure directories are excluded and reported separately.

Version-3 experiments receive `historical_partial`, with
`fully_verified: false` and an explicit list of versions whose derived artifacts
cannot be verified. The verification CLI exits **2** by default for that case;
`--allow-historical` allows exit **0** without changing the partial status.
Integrity errors exit **1**. Older unsupported/unversioned manifests fail with an
explicit historical-provenance error. Existing evidence is never retrofitted,
rehashed or rewritten. A new contract requires a declared amendment/new version
or a new run directory.

### B: completion and publication semantics

The frozen primary design requires exactly FairPoint and FairRobust, every frozen
held-out seed, phase `evaluation`, setting `primary` and mode `d_matched`.
Development/secondary/wrong-mode/wrong-setting runs do not count. Duplicate or
malformed cells fail. Every counted cell must have a valid seal, experiment
identity, execution key, independent validation record and compatible saved
scenario, policy, estimator, matrices, observation/note settings, extraction
route and monitoring limits. Sensitive/unknown execution options cannot enter
attempt provenance.

`aggregation_status.json` records actual/expected episode and paired-seed counts,
completed/missing/failed/invalid primary cells, excluded cells and contributing
episodes. `COMPLETE` means the full validated matrix. Missing cells produce
`INCOMPLETE / EXPLORATORY`; failed or incompatible primary cells produce
`FAILED / INCOMPLETE`. An unrelated secondary failure cannot falsely complete or
block an otherwise valid primary matrix.

Available paired subsets remain useful exploratory summaries. They are explicitly
conditional on completed pairs and exported separately as
`exploratory_primary_comparison.csv`. The completed primary table and successful
`primary_complete.json` declaration exist only for the full valid matrix. Unequal
policy seed sets yield only their explicitly labelled completed pairs, without
fabricating missing observations. The renderer rebuilds its aggregate from
validated episode records, reads its completion state, displays actual/expected
counts and missing/failed/invalid cells, and marks incomplete prose and figures
`INCOMPLETE / EXPLORATORY`. It cannot call a partial CI the prespecified completed
primary result.

A finalized report is an immutable **snapshot**, which may honestly document an
incomplete experiment. Finalizing that snapshot does not declare primary
scientific completion. Additional episodes produce another auditable generation.

### C: execution, failure and retry lifecycle

Research execution, standalone episode persistence and replay now use uniquely
named private staging directories, exclusive writer locks and one-filesystem
rename publication. The entire construction/simulation/optimization/validation/
scoring/serialization/trace/sealing/publication path is inside the failure scope.
A successful destination appears only after all required writes and validation
succeed and the seal verifies. Replay writes its success record only after every
late deterministic comparison, then seals that record too before publication.

Failures retain identity, destination, error type/message and attempt metadata
with partial diagnostic artifacts under `.failed/`. Research failures also retain
an explicit failed-cell marker without a successful summary. Unpublished summary,
replay-result and seal files are labelled `.unpublished`. Existing destinations
are never replaced. Failed identities are not silently retried; inspect the
failure and use a new experiment identity/directory. Replay diagnostics live
outside its requested destination, so a failed replay leaves that destination
absent. An abrupt process termination leaves explicit staging/lock state and
cannot create a completed inventory; locks are not automatically cleared and
overwritten. Temporary records do not enter aggregation.

Review also reproduced a retry through explicit-default option spelling, retained
in `retry_reproduction.log`. Execution identities now canonicalize effective
defaults, so that spelling resolves to the same completed cache or failed-cell
reservation rather than creating an unmarked retry.

### D: safe extractor execution identity

The allowlisted identity records extractor/client implementation and code hashes,
backend, canonical endpoint SHA-256, model tag and available weight digest,
context length, actual temperature, timeout, fixed think/stream settings,
system-prompt/schema hashes, and validation-code/evidence-contract versions.
Fixture payloads and recorded outcomes receive fingerprints and remain distinct
from real inference. Unknown adapters and historical/partial identities are
explicitly labelled and cannot enter current research aggregation.

Endpoint normalization folds hostname/scheme case and default ports and removes
authentication, query and fragment components before hashing routing. Raw private
endpoints, arbitrary metadata/configuration, environment values, API keys and
tokens are not serialized into extractor identities or cache contexts. Frozen
configuration rejects credential fields and authentication URL components.
The existing Ollama client reports safe endpoint hashes/status codes in failures
without serializing authentication URLs or raw HTTP error bodies.

Unavailable model weights remain `null`, with
`mutable_tag_without_weight_digest`; no digest is invented and no inference call
is made merely to collect identity. An available digest is recorded without
claiming independent attestation. Both in-memory and persistent cache keys use
the same current execution identity, including after client settings change.
Aggregation rejects incompatible extractor versions within an information mode.

A final adversarial probe also reproduced leakage of an arbitrary field added
to the cache adapter's configuration dictionary. The cache writer now reconstructs
its entire persisted configuration from the allowlist on each extraction, rather
than merging arbitrary existing fields. `cache_privacy_reproduction.log` retains
the failing regression before this correction.

The feedback runner's redundant descriptive `llm_options` now comes from the
same identity too. A nondefault-temperature regression reproduced a stale
hardcoded zero in that description; the retained metadata reproduction shows
declared zero versus actual `.4` before correction. No new model call is needed.

### Regression and verification commands

The added [regression module](../tests/test_phase3_final_repairs.py) exercises
artifact tampering/deletion/substitution/inventory changes; report generations,
amendments and legacy policy; empty, partial, failed, complete and incompatible
primary matrices; errors at construction, simulation, scoring, JSON, gzip,
sealing, late replay and final publication; cache reuse, duplicate destinations,
unpublished staging; endpoint/digest/options/prompt/schema identity and privacy.
It also checks retained-record verification without today's factories and valid
nondefault effect, radius and missingness settings.

Run on supported Python 3.12 or 3.13 from the repository root:

```sh
python -m unittest tests.test_phase3_final_repairs -v
python -m unittest discover -s tests
python scripts/verify_phase3.py --output results/phase3_fresh_verification
python scripts/verify_experiment_records.py <run-directory>
git diff --check
git status --short
git diff --stat
```

The expanded verification harness uses six students, two mentors and three
months, all baselines and resource/fair/robust policies, fixture extraction,
partial primary summaries and a tiny explicitly frozen two-seed primary design.
It checks successive sealed reports, deliberate CSV corruption, late failed
replay, immutable amendment and both retained versions. It fingerprints the
source/runtime and compares earlier Phase 2/3 verification and historical
research artifacts before and after execution. Generated evidence stays in a
new ignored local directory and is not claimed to be committed or available on
GitHub. Final measured outcomes are appended below.

### Remaining limits

SHA-256 detects changed evidence relative to retained hashes; it is not a signed
external ledger and cannot defeat rewriting both evidence and every hash/registry.
Filesystem publication assumes a local filesystem with atomic same-volume
rename and cooperating writer locks. Power-loss durability and automatic stale
lock recovery are not claimed. A crash between report publication and registry/
pointer updates fails closed and needs explicit inspection; it does not silently
accept an unregistered generation. A completely unwritable filesystem can also
prevent writing diagnostics; the original exception is retained.

Exact replay still requires its recorded source/dependency environment, preserves
recorded extraction outcomes offline and makes zero new model calls. Mutable
model tags cannot establish immutable weights. Arbitrary undocumented adapters
are not certified. The tiny completion test validates the execution/reporting
contract, not research effectiveness, calibrated uncertainty, real LLM accuracy
or real-world fairness. No full held-out research grid, new scientific phase,
commit, push or merge is part of these repairs.

### Final repair file inventory

The final diff changes twelve existing files and adds three files:

- [provenance.py](../src/evaluation/provenance.py): version compatibility,
  allowlisted identities, strict inventories and staged artifact lifecycle.
- [report_artifacts.py](../src/evaluation/report_artifacts.py) (new): sealed
  generations, linked registry, contributing episodes and convenience-link checks.
- [research_records.py](../src/evaluation/research_records.py) (new): completed
  execution validation against frozen defaults and primary-matrix completion.
- [research_experiments.py](../src/evaluation/research_experiments.py): version-4
  freeze, canonical execution/cache identity, atomic publication and aggregation.
- [research_report.py](../src/evaluation/research_report.py): sealed rendering,
  completion-aware prose/figures and valid one-policy exploratory reports.
- [cached_observation_extractor.py](../src/evaluation/cached_observation_extractor.py),
  [observation_extractor.py](../src/intervention/observation_extractor.py) and
  [ollama_client.py](../src/intervention/ollama_client.py): safe complete execution
  configuration, compatible cache keys and credential-safe failure messages.
- [feedback_experiments.py](../src/school/feedback_experiments.py) and
  [feedback_replay.py](../src/school/feedback_replay.py): atomic persistence,
  deterministic comparisons before publication and consistent model metadata.
- [verify_experiment_records.py](../scripts/verify_experiment_records.py) and
  [verify_phase3.py](../scripts/verify_phase3.py): explicit verification exits,
  bounded lifecycle/corruption checks and historical-byte comparison.
- [test_phase3_final_repairs.py](../tests/test_phase3_final_repairs.py) (new):
  adversarial regressions. Existing test files remain unchanged.
- [README](../README.md) and this append-only correction record: current
  execution, reporting, failure and historical-compatibility semantics.

### Final local acceptance record — 9 November 2026

The final acceptance run passed on CPython **3.12.12**, macOS arm64, using
`/tmp/phase1-python312/bin/python`. The branch remains
`fix/phase-3-repair-experimental-comparisons`, based on commit
`68a97f61cf4e530177d1a8a407aaabfad40cd5a7`. The tested working-tree executable
source/configuration SHA-256 is
`8a44ee0bbcd89a895825822c3b460c388878a9a6dfe6588ef744eaa07980bcef`.
This fingerprint identifies the uncommitted implementation, not a new commit.
The harness confirmed the source did not change during verification. This final
documentation append does not change that executable-source fingerprint.

The exact acceptance command was:

```sh
/tmp/phase1-python312/bin/python scripts/verify_phase3.py --output results/phase3_final_repairs_20261109/acceptance
```

The retained [verification record](../results/phase3_final_repairs_20261109/acceptance/verification.json)
contains resolved dependency versions, per-file source hashes, immutable
experiment identities, historical artifact hashes, bounded results and the
commands' exit statuses. The final measured checks were:

| Check | Result |
| --- | --- |
| Focused Phase 1–3/information/comparison regressions | 106 passed in 51.550 seconds; 0 failed, 0 errors, 0 skipped |
| Full offline test discovery | 332 passed in 97.144 seconds; 0 failed, 0 errors, 0 skipped |
| New repair regressions | 57 methods; all original 275 tests retained |
| Bounded policy/information grid | 40 validated episodes: 8 policies across 5 information modes |
| Offline exact replay | All 8 policies replayed twice with equal deterministic digests |
| Primary completion progression | 0/4, then 2/4 exploratory, then 4/4 COMPLETE for frozen seeds 10073 and 10074 |
| Finalized derived artifacts | 6 sealed report/aggregate generations verified across 2 immutable experiment versions |
| Deliberately corrupted report | Rejected: `corrupted artifact: primary_policy_comparison.csv` |
| Deliberately late replay mismatch | Rejected: `replay final_beliefs mismatch`; requested replay destination absent |
| Historical preservation | All 4,774 inventoried historical files had identical before/after SHA-256 hashes |
| Prior immutable records and reports | Original manifest/episode bytes and previous finalized report bytes preserved |
| Real LLM calls | 0 |
| Whitespace and editor diagnostics | `git diff --check` passed; no editor errors in changed modules |

The zero-effect and paid zero-budget controls produced no outcome improvement.
The free positive-effect zero-budget control admitted four programmes and
changed the synthetic trajectory; removing service capacity prevented programmes
and restored equal trajectories. No transition matrices or treatment effects
were edited for these checks. Development episodes were explicitly excluded
from primary completion. The immutable amendment used a different uncertainty
radius and preserved verification of the preceding version.

The [pre-fix reproduction log](../results/phase3_final_repairs_20261109/before_repairs.log)
records seven failing methods covering A–D. Additional failing adversarial
reproductions are retained beside it for alias substitution, execution-setting
drift, explicit-default retry, cache-configuration privacy and descriptive model
metadata. All corresponding regressions pass in the final
[focused log](../results/phase3_final_repairs_20261109/acceptance/focused.log) and
[full-suite log](../results/phase3_final_repairs_20261109/acceptance/offline.log).
Earlier intermediate verification directories remain intact and are not
presented as the final tested source identity.

The final skeptical review covered incomplete prose/figures and primary counts,
sealed tables and aliases, cache configuration and credentials, frozen execution
compatibility, offline replay publication, strict artifact inventories,
interruption/failure paths, historical version policy, information boundaries
and preservation of old tests/protocols. The additional defects found during
that review were repaired and reproduced with regression tests before this
acceptance run. No residual merge-blocking correctness defect was identified.
The filesystem, hash-attestation, mutable-model-tag and scientific limits above
remain explicit limitations rather than claims validated by this tiny scenario.

**Verdict: READY TO MERGE on the basis of local acceptance.** The existing CI
workflow still targets Python 3.12 and 3.13 and was not changed. No CI run for
these final uncommitted changes has completed; Python 3.13 execution remains
unverified here. No commit, push, merge, historical evidence rewrite, full
research grid or Phase 4 work was performed.

## Final Report Alias Lifecycle Correction

### Root cause and reproduction

At baseline commit `f68f3c16691aa6b0ca818bf0d85b8dce47dbf229`,
[report_generation](../src/evaluation/report_artifacts.py) created convenience
links for the newly published directory, without retiring names absent from that
directory (baseline line 151). The verifier inspected only the latest directory's
names (baseline line 86). Consequently, full report → aggregate left a dangling
root `research_results.md` link while verification still succeeded. The original
sealed report's continued existence did not make that root link valid.

The two deterministic offline reproductions failed before the implementation
change: the obsolete link was still a symlink, and the verifier raised no error
for the dangling managed alias. The exact
[pre-fix log](../results/phase3_alias_lifecycle_20261109/before_fix.log) records
**2 tests, 2 failures**. No live model or research grid was used.

### Alias ownership and verification

Ownership is reconstructed from the top-level artifact names in **all retained,
verified report manifests**. These names remain reserved for that experiment
version, including after the corresponding artifact leaves the current
generation. The latest manifest supplies the expected set. This uses the existing
immutable records; it introduces no mutable alias registry or resealing.

Generation files remain immutable. The JSON current pointer and `.current_report`
directory link remain mutable publication metadata. Managed convenience links
must point exactly to `.current_report/<same-name>`. Optional diagnostic inputs
(`snapshot_assignment_comparison.csv`, `extraction_snapshot_comparison.csv`,
`live_runtime.json`, `development_gate.json`, and `extraction`) and generation
metadata/seals are excluded from convenience aliases. Diagnostic snapshots remain
inside their sealed generations; their root originals are untouched.

Publication removes obsolete managed links and creates missing expected ones.
An unrelated symlink is not automatically owned. A user file, directory or
different symlink at a reserved name is rejected and preserved. Even an
alias-shaped link at a newly required, previously unowned name blocks publication.
The complete managed-name inventory is checked for missing expected links,
ordinary-file substitutions, dangling links, outside/historical targets and
obsolete aliases or user conflicts. Checking `is_symlink()` also detects dangling
links for which `exists()` is false. Existing seal, manifest, registry and
contributing-episode checks remain in force; publication finishes by verifying
the resulting report state.

### Failure boundaries and preservation

The cooperating-writer lock and private staging/sealing remain. Update order is:
publish the sealed generation directory; atomically replace the generation
registry; replace the JSON current pointer; replace `.current_report`; remove
obsolete aliases and create expected aliases; verify the complete state. Prior
generation bytes are never rewritten.

These filesystem operations are not one transaction. Readers can observe an
intermediate state, and interruption can leave an unregistered generation,
mismatched pointers, missing links or obsolete dangling links. Such inconsistent
states fail verification and require inspection/recovery; there is no automatic
rollback or power-loss durability/fsync guarantee. A correctly completed alias
state may verify even if the writer stops immediately afterward. The hashes
remain integrity evidence rather than protection against rewriting both bytes
and attestations, and the lock does not serialize unrelated external writers.
Pre-existing invalid aliases are rejected before another generation is published.

The 18 added methods in
[test_phase3_final_repairs.py](../tests/test_phase3_final_repairs.py) cover all four
aggregate/report sequences, deletion and substitution, obsolete links after
multiple aggregate generations, old/outside targets, user file/directory/symlink
conflicts, optional diagnostics, interrupted alias creation/removal, interrupted
registry/pointer replacements, historical byte preservation and amendment into
a new version. All original tests remain intact.

The separate [skeptical review](../results/phase3_alias_lifecycle_20261109/skeptical_review.json)
created a tiny retained experiment, published a full report followed by an
aggregate, and verified that the obsolete alias was absent while the original
immutable report remained accessible with identical hashes. Reintroducing the
exact dangling link made the CLI exit **1** with
`obsolete managed artifact alias or unmanaged conflict: research_results.md`.
After removing that injected link, the CLI verified both retained generations;
the user file and unmanaged dangling symlink remained unchanged.

### Executed verification and source identity

The branch remains `fix/phase-3-repair-experimental-comparisons`, at commit
`f68f3c16691aa6b0ca818bf0d85b8dce47dbf229` plus the uncommitted correction.
The final executable-source/test/configuration SHA-256 is
`39b3e4b88abd5d61034ed4e7e751f991a5af4c1fded043e95a4db9bafadbd255`.
Documentation is excluded from this fingerprint to avoid a circular identity.
Local execution uses CPython **3.12.12** on macOS arm64 via
`/tmp/phase1-python312/bin/python`.

| Direct command (using the interpreter above) | Result |
| --- | --- |
| `-m unittest tests.test_phase3_final_repairs.ReportAliasLifecycleTests -v` | 18 passed in 13.149 seconds |
| `-m unittest tests.test_phase3_final_repairs -v` | 75 passed in 47.025 seconds |
| `-m unittest discover -s tests` | 350 passed in 109.964 seconds; original 332 retained |
| `scripts/verify_experiment_records.py results/phase3_alias_lifecycle_20261109/skeptical_records` | Exit 0; 1 version, 2 sealed generations fully verified |
| `git diff --check`, `git status --short`, `git diff --stat` | Exit 0; targeted implementation, tests and this appended record |

The [new verification directory](../results/phase3_alias_lifecycle_20261109/)
retains the reproduction, direct test logs and skeptical CLI evidence. Prior
verification directories and historical documentation results are preserved.

The bounded harness ran against the final source fingerprint above using the
fresh destination below:

```sh
/tmp/phase1-python312/bin/python scripts/verify_phase3.py --output results/phase3_alias_lifecycle_20261109/acceptance
```

The [final verification record](../results/phase3_alias_lifecycle_20261109/acceptance/verification.json)
reports:

| Final acceptance check | Result |
| --- | --- |
| Combined Phase 1–3/information/comparison regressions | 124 passed in 65.067 seconds |
| Full offline discovery on the final source | 350 passed in 110.602 seconds; 0 failures, errors or skips |
| Git whitespace/status/stat commands | All exited 0 |
| Bounded policy/information scenario | 40 validated episodes; 8 policies, 5 modes |
| Exact offline replay | 8 policies replayed twice with matching deterministic digests |
| Retained experiment CLI verification | Exit 0; 2 versions, 6 sealed generations fully verified |
| Historical preservation | All 4,774 inventoried files unchanged; prior manifests, episodes and sealed reports preserved |
| Source stability | Fingerprint unchanged from harness start through completion |
| Real model calls | 0 |

The final skeptical review confirms the originally reported condition is
prevented by normal publication and rejected if deliberately reintroduced. No
transition, fairness, information-boundary, seed, policy, completion, extractor,
episode or replay semantics were changed. User-facing report paths and commands
are unchanged, so the README was not modified.

**Verdict: READY TO MERGE on local Python 3.12 acceptance.** Python 3.13 and CI
were not rerun for these uncommitted changes. No commit, push, merge, full research
grid or Phase 4 work was performed. The explicit filesystem/crash and scientific
limitations above remain.

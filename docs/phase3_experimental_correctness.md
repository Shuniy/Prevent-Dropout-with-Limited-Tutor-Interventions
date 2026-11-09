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

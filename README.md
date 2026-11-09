# Student support simulation

The default workflow compares all baseline policies and the resource/fairness planners
in oracle, structured, matched-note, LLM-note and noisy-note modes through `main → school`.
Every run uses the same scenario, seed, transition model and resource limits. Information
access differs intentionally by mode; matched-note and LLM-note use the same feature schema.
Each result and wall-clock duration is printed, followed by the full comparison, before
Markdown, CSV, JSON, configuration and episode traces are saved in a new directory.
Timing includes simulation and extraction but excludes report writing. Extraction failures
are reported as quarantined observations; inspect these before interpreting LLM results.
The default extractor is Ollama (`qwen3.5:latest`); fixture extraction is an offline control.
LLM-note modes extract selected authorized school monitoring notes before admission,
with a separate default bound of one actionable monitoring note per decision cutoff.
Programme notes retain their own limit. Matched controls receive exactly the same
selected note content and timing. Unselected or failed notes supply no gold fallback.
Transition probabilities and intervention effects are synthetic assumptions.

Recorded-intervention extraction remains available through Python APIs and the
standalone simple/RAG analysis commands described below.

## Documentation navigation and authority

The current research objective is to evaluate limited educational-support allocation
under uncertain language-derived information in a synthetic benchmark. Simulated
withdrawal is not observed school dropout or evidence of real intervention effects.
The accepted Phase 1 requirements are: only successfully assimilated condition
evidence refreshes condition freshness (R02); hidden reset attendance/engagement
cannot enter ordinary policy inputs without authorized observations (R03); and
operational learning gaps use the mean of available first-period anchor and
mathematics grades under a declared synthetic decision-time assumption (revised
R14). Missing mathematics grades are excluded without imputation. Public needs
and private simulator initialization share the same grade-shortfall calculation.
The [Phase 1 correction record](docs/phase1_scientific_correctness.md) documents
these requirements, the superseded anchor-only rule, and scientific limits.
The [Phase 2 implementation and verification report](docs/phase2_scientific_correctness.md)
documents actionable monitoring extraction (R01), non-vacuous common-history snapshot
comparisons (R04), historical evidence coverage and deterministic extraction-outcome
replay. Its finalization record identifies the source revision plus working-tree
fingerprint and reports 69 focused / 260 offline tests on Python 3.12.12.
The [Phase 3 experimental correctness report](docs/phase3_experimental_correctness.md)
documents shared baseline information, exact versioned replay, fairness configuration,
free-service controls and immutable experiment amendments. Its bounded offline
verification is available through `python scripts/verify_phase3.py --output results/phase3_new_run`.
The [Phase 4 delivery and offer-fairness report](docs/phase4_delivery_and_fairness.md)
documents the separate weekly lifecycle, multi-week commitments, four-week unique
offers, delivery-driven effects and exact weekly replay. Its
[versioned weekly protocol](docs/phase4_delivery_protocol_v1.md) and
[configuration](configs/delivery_weekly_v1.toml) are synthetic assumptions.
Old configurations continue to select the atomic monthly benchmark.
The [Phase 4.1 amendment](docs/phase4_1_adaptive_delivery_correctness.md) adds
evidence-gated active-programme reassessment, documentation-sensitive uncertainty,
committed-support risk and joint fairness-feasibility diagnostics. Reproduce its
synthetic acceptance and exact offline replays with
`python -m src.school.delivery_acceptance --output results/phase4_1_new_run` after
installing `requirements-offline.txt` under Python 3.12 or 3.13. Use a fresh output
path for each execution; [retained measured evidence](docs/phase4_1_acceptance_results.json)
is included with the source, and CI uploads full synthetic episodes and logs.

Check current implemented behavior against `src/`, `configs/` and `tests/`.
Code and passing tests establish tested behavior, not scientific correctness.
This README provides navigation and commands, not a complete research design.
The [research evaluation protocol](docs/research_evaluation_protocol.md) is a
historical frozen specification, restored unchanged from pre-deletion main
(`3e9ccbe`), and a required input to experiment fingerprinting/freezing. It is not
an authoritative plan for future phases. Historical results have not been validated
under the Phase 1 corrections. A future experiment needs a separately versioned
protocol or explicit dated amendment; preserve historical methodology and run artifacts.

Use the [data role guide](data/README.md) and retained
[variable dictionary](data/external/variable_dictionary.csv) for input provenance.
Archived plans, specifications, audits and result summaries are historical evidence,
not instructions for future implementation; their availability assumptions may be
superseded. Do not reproduce known bugs to match them.

When sources conflict, identify the precise contradiction, distinguish intended
scientific requirements from current behavior, and consult verified research
requirements and evidence. Do not choose a source merely because it is newest.
Report unresolved scientific design decisions rather than guessing.

## Setup and commands

Use Python 3.12 or 3.13, as declared in `pyproject.toml`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

The requirements include dependencies for preserved research notebooks.

```bash
# Offline weekly delivery demonstration and exact replays, in a new output path:
python -m src.main --runner delivery --weeks 12 --output results/delivery/my_run
# Equivalent dedicated entrypoint:
python -m src.school.delivery_experiments --output results/delivery/another_run
# Replay a saved weekly policy episode without a live LLM:
python -m src.school.delivery_experiments --replay results/delivery/my_run/fair_point \
  --output results/delivery/fair_point_replay

# Full comparison with real LLM extraction (requires a running Ollama model):
python -m src.main --extractor ollama --output results/comparison/my_run

# Small offline comparison of all modes:
python src/main.py --extractor fixture --students 10 --months 3 \
  --output results/comparison/offline_run

# Privileged oracle diagnostic sweep (not an ordinary-information comparison):
python -m src.main --runner baselines --output results/cmdp_baselines/my_run

# Small CMDP run with explicit scenario overrides:
python src/main.py --runner baselines --students 10 --mentors 2 --months 12 \
  --development-seeds 1 --evaluation-seeds 1 --output results/cmdp/small_run

# Full effect and budget sweep:
python -m src.main --runner baselines --suite full --output results/cmdp_baselines/full_run

# Step 4: frozen-cohort fairness targets, budget and effect sensitivity (1,000 episodes):
python scripts/run_cmdp_fairness.py --output results/cmdp_fairness

# Development only, to inspect results before a full comparison:
python -m src.main --runner baselines --suite full --stage development \
  --output results/cmdp_baselines/development_run

# One-call private analysis of all sessions through the cutoff:
python -m src.intervention.simple_llm \
  01_transport_assessment/intervention_student_001 \
  --through-session 2 --output results/private_simple/conclusion.json

# Preserved RAG analysis of the same history:
python -m src.intervention.rag \
  01_transport_assessment/intervention_student_001 \
  --through-session 2 --output results/private_history/conclusion.json

# Offline feature tests, including teaching examples:
python -m unittest discover -s tests
```

Equivalent application entry points are `python src/main.py`, `python -m src.main`,
and, after installation, `school-dropout`. The combined comparison defaults come from
`configs/cmdp_llm_feedback.toml` (100 students, 2 mentors, 12 months, one monthly
admission and five monthly appointments per mentor). Use `--policies` to select baselines,
`--feedback-policies` to select planners, and `--modes` to select information modes.
`--max-notes-per-month` still caps intervention programme notes per source month.
`--max-monitoring-notes-per-month` separately caps actionable monitoring notes per
decision cutoff (default 1; 0 disables this channel). The Python API accepts `None`
to select all available actionable monitoring notes. Selection uses a reproducible
seeded hash of cutoff and note identity, independent of group, need and hidden truth.
Eligibility uses authorized enrollment and prior admissions. Cap-excluded notes
are logged and discarded; unavailable notes wait until their availability cutoff.
No monitoring model calls are made after the final decision. Structured and oracle
modes retain all authorized structured observations regardless of these note caps.
Delayed programme notes retain their source-month cap and are processed once when
available, so several source months can reach one cutoff. With two mentors, one
admission each per month, and a twelve-month horizon, the default allows at most
12 monitoring plus 24 programme calls per policy/LLM mode (504 across the default
seven policies and two LLM modes). Baselines now use the same extraction pipeline.
`--feedback-policies resource fairness robust` also includes the robust planner;
its default declared uncertainty radius is .25. `terminal_value` is canonicalized
to `resource` to avoid duplicate runs. Cache hits can reduce model invocations. Attempts, actual calls,
cache hits, accepted/quarantined results and note-selection reasons are saved separately.

`--extraction-contract legacy_programme_only` preserves the historical routing:
all routine monitoring uses exact grammar extraction and only programme notes use
the injected extractor. It retains its old note-cap meaning but does not establish
actionable LLM feedback. Programme-note feedback remains non-actionable for the
recipient under the single-programme benchmark; repeat or continuing support is deferred.
The legacy baseline runner defaults come from
`configs/cmdp_baselines.toml`: the same Step 1 scenario with 100 students,
2 mentors, 12 months, 5 appointments per
programme, 10 monthly admissions, budget 150 and seed 42. Explicit CLI options
override the configuration. The default comparison uses 10 development seeds and
30 independent evaluation seeds. The five baselines are the default; `--policies`
selects policies, `--seed` sets the first development seed (evaluation starts
10,000 later), and `--effect-strength` and `--budget` change a default-suite scenario.
`--output` must be new; omitting it creates a timestamped destination under
`results/cmdp_baselines`. Development validation precedes held-out execution.
The CLI prints scenario progress and exits nonzero on failure, preserving a
`failure.json` with the failed world. Existing optimizer/fairness policies remain
explicit opt-ins and are excluded from the Step 2 comparison.

Step 4 adds strict or shortfall-aware minimum programme-access coverage with
four-month frozen condition strata and one explicitly selected audit attribute.
The rolling MILP executes only current-month admissions; future schedules remain
tentative.

Step 5 connects dated monitoring/programme notes to validated LLM extraction,
categorical beliefs, synthetic withdrawal risk and both existing CMDP planners.
Run `python scripts/run_cmdp_feedback_pilot.py` for the offline fixture pilot, or
add `--extractor ollama --max-notes-per-month 1 --max-monitoring-notes-per-month 1`
for the existing local model. Run `python scripts/verify_phase2.py --output
results/phase2_new_run` on Python 3.12 or 3.13 for the offline verification harness.
It runs the focused and full test suites, checks the diff, and saves deterministic
evidence-to-allocation traces plus successful, empty, mixed and failed extraction
replays. It records Git revision, source fingerprints and dependency versions.
Use a fresh output directory; generated results and logs are ignored by Git and
are not distributed with the repository. Replay preserves original failure/cache
provenance and reports zero new model calls. Phase 3 replay contract version 3
supports all five baselines and the resource, fair and robust planners, including
nondefault dynamics, estimators, uncertainty and note settings. Incomplete historical
records and arbitrary custom policy implementations are explicitly rejected.

Standalone extraction commands require a local Ollama server and model:

```bash
ollama serve
# In another terminal:
ollama pull qwen3.5:latest
```

For those standalone commands, use `--root` for another corpus, `--model` for
another installed model and `OLLAMA_BASE_URL` for a different local endpoint.
SQLite FTS5 provides retrieval; no embedding model is needed. School and
intervention APIs use independent NumPy RNG streams from `create_rng(seed)`;
teaching examples create a fresh `create_rng(seed)` per school or main invocation
and pass that generator to their students. Defaults use the shared `SEED`; callers
can override the seed. CMDP policy shuffles and keyed environmental draws retain
separate seeded streams so policy calls cannot shift environmental outcomes.

## Recorded-intervention Python workflow

1. Read current performance, save a before snapshot and compute ranked support needs
   using the shared baseline/current rules. Need severity determines priority;
   seeded shuffling breaks ties.
2. Allocate suitable mentors using skills, caseload, monthly session limits and
   remaining budget. Reserve the entire planned dose for the month's admissions.
3. Send immutable minimal requests to intervention. It binds a coherent randomly
   chosen support-matched history to the run/programme/student/mentor identity.
4. Select at most the planned number of recorded sessions. With `method="simple"`, send all
   selected spoken conversations in one call, without an index, retrieval or
   previous LLM memory. The response contains a chronological findings timeline;
   its final entry supplies the intervention conclusion. With `method="rag"`,
   extract once per session with earlier passages, source-backed actions and validated
   findings. Both modes run an additional semantic review per timeline entry.
   Both exclude profiles, sessions beyond the selected cutoff
   and retrospective corpus labels. Seeded history selection is unchanged.
5. School validates matching result identity and counts, rejects duplicate application,
   charges recorded sessions and releases unused reservations. Recorded attendance
   remains available when model analysis fails. Missing history returns zero attendance.
6. Update school-owned participation and known reported outcomes, record after
   snapshots and save the monthly report before advancing the clock. Refunds can
   fund later months; the same month is never refilled.
7. Save student summaries and the final school report after the final month.

All students remain in monthly tracking, including unassigned students and those
whose programme has finished. A student never starts a second programme in a run.
Source grades, demographics and `initial_*` assumptions remain unchanged. Current
metrics, mentoring participation and reported outcomes are separate. A reported
attendance improvement does not become an invented attendance percentage or grade
increase. Unknown/conflicting/failed extraction leaves relevant measures unchanged and records
why. There is no calibrated intervention score or trained predictive model.

Python callers construct `Intervention(load_sessions(), client, seed=...)` explicitly and call
`school.run_simulation(intervention, output_dir=...)` once. `school.allocate_programmes()`
provides the old allocation-only operation and returns monthly maps. It reserves
planned costs without claiming completed attendance. `reset()` restores baseline
performance, initial mentor caseloads and run accounting under a fresh run ID.

### Support rules

Severity is a scenario priority in `[0, 1]`, not a predicted dropout probability.
At the initial simulated decision point, available first-period anchor and
mathematics grades are treated as known academic measurements. The learning gap
uses their mean. Missing mathematics grades are excluded from the mean without
imputation. Their synchronized real-world availability has not been independently
established; this is a synthetic benchmark assumption.

`learning_gap = clip((10 - mean(available G1 grades)) / 10, 0, 1)`.
A valid mathematics grade of `0` contributes to the mean; `None` does not.
For example, anchor/math grades `8`/`None`, `8`/`6`, `2`/`10` and `10`/`0`
give gaps `0.2`, `0.3`, `0.4` and `0.5`, respectively. Anchor `18` gives `0.0`
with either missing math or math `10`. Source grades and missing values are
preserved. Public learning needs and private initialization use this same formula;
the realized initial condition remains private.

The assumed enrollment, attendance and engagement rows below apply only to the
recorded-history performance evaluator's explicit legacy opt-in. Ordinary
policy-facing source needs exclude these hidden reset measurements.

| Condition | Support | Severity |
| --- | --- | --- |
| Initially not enrolled | Reentry support | 1 |
| Learning gap or past failures | Tutoring | Maximum of learning gap and failures / 4, capped at 1 |
| Assumed attendance below 0.85 | Attendance planning | 1 − attendance |
| No home internet | Device access | 0.5 |
| Travel category at least 3 | Transport assessment | (category − 2) / 2 |
| Study-time category 1 | Homework support | 0.25 |
| Family relationship rating at most 2 | Family liaison | (3 − rating) / 3 |
| Health rating at most 2 | Wellbeing check-in | (3 − rating) / 3 |
| Assumed engagement below 0.6 | Peer support | 1 − engagement |
| Financial need explicitly verified | Family finances | 0.75 |
| No condition met | Routine tutoring check-in | 0 |

## Saved results and confidentiality

School reports default to a fresh directory under `results/intervention_simulation/`:

```text
run_.../
  month_01.json
  ...
  month_12.json
  final_report.json
  student_00001/
    final_report.json
```

School retains only limited immutable intervention results: run/programme/pair IDs,
month, support, planned/recorded counts, programme/analysis status, and reported
attendance change, barrier resolution and helpfulness. Exports use an explicit field
allowlist. They contain no transcripts, history IDs/paths, retrieved passages,
private errors, detailed session memory or free-text conclusions.

| School report | Contents |
| --- | --- |
| Monthly | Identity, costs, that month's admissions/results and all student before/after evaluations |
| Student final | Student ID, limited `result` or null, unassigned reason and monthly evaluations |
| Run final | Run ID, months, status, output directory, costs, assignments and student summaries |

Programme `status` is `completed`, `incomplete` (short recorded history) or
`unavailable` (no compatible history). `analysis_status` is independently `completed`,
`failed` or `unavailable`. Failed/unavailable analysis returns unknown outcomes.
A fully attended programme can have failed analysis. Run status is `failed` if any
analysis failed, otherwise `finished`; short or unavailable histories alone do not
cause extraction failure. A student who was never admitted has `result: null` and
an explicit resource/budget reason. Missing history preserves its admission with
zero cost and attendance.

Optional private persistence uses another directory:

```text
example_private/
  programme_00001/
    session_01.json
    private_report.json
```

Private session files contain detailed validated findings and identity/history data.
The private final report can contain narrative conclusions and errors. The simple
method validates the entire timeline, including semantic reviews, before saving any
session files; a rejected generation or review leaves no partial session findings.
In RAG mode, earlier valid sessions survive a later failed generation or review.
School reports never link to this destination.
Python callers must choose separate public/private destinations, as the CLI does.
Both standalone extraction commands write the same private report structure:
`history_id`, `as_of_session`, `timeline`, `conclusion`. Existing school results and
private file layouts retain their outer fields. Findings use the current extraction schema;
old findings are incompatible and historical outputs are not migrated.

Each agreed action has a stable ID (`<history_id>:s<origin-session>:a<ordinal>`), verbatim
original wording, owner, original session/date, literal due date and source-cited status.
Statuses mean: `not_started` (explicitly no work begun), `attempted` (effort without a
completed required part), `partially_completed` (some required work done), `completed`
(all agreed work done), `not_completed` (explicit failure/abandonment or not done at a
checkpoint), and `unknown` (unspecified/ambiguous/conflicting progress). Agreement alone
leaves progress unknown. A completed review cannot complete the task being reviewed.

`intervention` separates `intended_intervention` (with intended `component_ids`),
`direct_activities` and `external_support`. Each activity/service has its own ID,
status and evidence. Preparing an application can be delivered direct assistance while
the requested service remains pending. The old `service_delivered` field is removed.
Known outcomes and session helpfulness also require source citations.

After JSON validation, deterministic checks verify verbatim quotes, source history,
session/turn numbers, as-of cutoff, immutable action fields, status transitions and
scoped delivery requirements. A separate model call checks evidence entailment and
narrative/indicator consistency; rejection or malformed review fails analysis without
repair or retry. This adds one review call per session to both methods. Model review
remains fallible and does not establish independently verified facts or causal effects.

RAG pins original action turns and dated status reports in `source_backed_actions`,
independently of ranked passage retrieval. Earlier findings remain provisional summary
memory. Original evidence and prior reported statuses survive later updates in the
accepted timeline; silence preserves the last report. Oversized evidence fails the
prompt budget check rather than dropping action records. Modules in one Python process
do not provide an OS access-control boundary.

### One-intervention comparison

Run [intervention_extraction_evaluation.ipynb](notebooks/intervention_extraction_evaluation.ipynb)
to compare both methods on the same three-session transport history with the same
`qwen3.5:latest` model and question:

```bash
python -m jupyter nbconvert --to notebook --execute --inplace \
  notebooks/intervention_extraction_evaluation.ipynb --ExecutePreprocessor.timeout=1800
```

The executed notebook and `outputs/intervention_extraction_evaluation/` retain both
reports, exact model requests (prompts, input context and schemas), call counts, elapsed
time, prompt characters, outcome agreement and three
transcript-based reference checks. Historical saved results use the earlier schema
and four-check rubric; rerunning uses the current schema and includes semantic review calls. This is one synthetic case, not an accuracy
benchmark. Timing is a single sequential run with uncontrolled startup/cache effects.
Each method receives the recorded intervention type, date and stage alongside spoken
turns. Simple inputs label each conversation position and its earlier sessions explicitly.
The simple timeline is reconstructed with all selected sessions visible; the prompt
requests findings as of each session, but only RAG enforces earlier-session isolation.

### Comparison across support types

```bash
python scripts/evaluate_intervention_types.py
```

This paired evaluation selects the first complete three-session history per support
type in sorted order (13 histories, 39 sessions). Both methods use the same model,
question and source history; method order alternates between cases. Outputs under
`outputs/intervention_type_evaluation/` include a manifest with exact prompts,
transcript hashes and spoken reference evidence, exact requests, raw responses,
validated reports and per-method measurements. Existing measurements are retained
when resuming, including failures; changed inputs or settings require a new output
directory. A complete run now makes 130 model calls: 52 extraction calls and
78 per-session semantic reviews, with one attempt per call. The manifest includes
the findings schema and review contract to prevent resuming older runs with new semantics.

Three narrow final-field checks cover barrier persistence, unknown attendance
improvement and positive session feedback. Delivery, intervention helpfulness and
action chronology also undergo the runtime semantic review; the narrow reference
checks remain separate from that model-based review. This template-generated sample
supports comparison across support types, not generalization to real student records.
See the [completed evaluation](outputs/intervention_type_evaluation/evaluation.md)
for aggregate and per-type results, with source-linked semantic review examples.

## Code organization

Production classes/dataclasses each have their own snake-case file, with explicit
package exports and plain functions for loading, need rules, validation and reporting.

- `src/school/`: source records, runtime performance, mentors, assignments, allocation,
  the School facade, monthly simulation and school reports.
- `src/intervention/`: immutable request/result boundary, private programme profiles,
  history assignment, one-call extraction, preserved chronological RAG, index,
  transcripts and model client.
- `src/utils/`: independent shared enums and constants.
- `src/main.py`: CMDP CLI and explicit experiment configuration.
- `src/basic_examples/`: independent agent, Markov, MDP and CMDP demonstrations.
- `tests/`: offline feature tests with a shared fake client.

School-specific loading/validation helpers moved from `src.utils.school` to
`src.school.loading`; imports use `src.school`, with no legacy `src.models` alias.
Cohort orchestration moved from intervention to school. There are no school objects
or mutation callbacks in intervention.

## Teaching examples and research material

Run examples independently:

```bash
python -m src.basic_examples.markov_chains
python -m src.basic_examples.simple_agent
python -m src.basic_examples.agent_based_modelling
python -m src.basic_examples.markov_decision_process
python -m src.basic_examples.budgeted_mdp
python -m src.basic_examples.cmdp
```

Imports do not run simulations. Examples keep their essential state counts,
rewards, and optimization algorithms and print a final result. The CMDP example
uses SciPy through the existing scientific environment. Recorded-intervention Python
runs use need priority. The default CMDP workflow compares the selected policies,
including the constrained terminal-value optimizer.

The supplied CSVs and transcripts are used directly; no preprocessing command is
required. `data/processed/`, `data/external/`, notebooks, corpus generators, and
`archive/` remain research/reference material. Historical notebooks may need import
or result-field updates before reuse; they are outside this refactor. Historical
research specifications describe possible future work, not the active interface.

Synthetic conversations and assumed attendance/engagement are not observations of
real children or measured treatment effects. Missing appointments have unknown
reasons and do not establish dropout. Historical course failure is not school
dropout. Causal calibration and trained withdrawal risk models remain future work;
the school CMDP feedback and evaluation workflows use explicit
synthetic dynamics and provides initial policy/fairness experiments.

## CMDP retention simulation

The finite-horizon simulator lives in `src/school` and runs through
`School.run_cmdp(policy)` or `main.py`. It reuses the existing
student/mentor models and matching rules, supports five allocation baselines,
monthly terminal-value MILP allocation, exact tiny-instance comparisons, frozen
group-access audits and optional window-aware fairness allocation. All transitions
and effects are synthetic assumptions; simulated withdrawal is not observed school
dropout. Note extraction is available through Python APIs and standalone analysis commands.

```sh
.venv/bin/python -m src.main --output results/cmdp_baselines/my_run
# Print month 0–12 and terminal summaries for a WAIT-only demonstration:
.venv/bin/python -m src.main --policies wait --development-seeds 1 \
  --evaluation-seeds 1 --print-monthly --output results/cmdp/my_wait_run
.venv/bin/python -m unittest discover -s tests -p 'test_cmdp*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_baseline*.py'
```

Every episode saves `monthly_summaries` in `episodes.jsonl`, including initial
retention/dropout rates, withdrawals, programmes, appointments, spending, remaining
budget, mentor utilization and waiting among enrolled, unsupported students.
Portable CSV exports include episode/monthly records, policy comparisons with
sample standard deviations and paired 95% Student-t intervals, budget/effect
sensitivities, and descriptive group access. Eight figures under `figures/` cover
retention, withdrawals, spending, programmes, utilization and sensitivities.
Waiting counts only months survived without a programme; a withdrawal month adds
no waiting time. `--print-monthly` prints the first development world for each
policy/scenario; large sweeps otherwise keep their usual progress output.

See the [baseline configuration](configs/cmdp_baselines.toml).
Use a new output directory for each run.

## Step 6 research contribution evaluation

The historical [frozen evaluation protocol](docs/research_evaluation_protocol.md) and
retained [configuration](configs/research_evaluation.toml) specify a staged comparison of
FairPoint and finite-scenario FairRobust, reusing the Step5 feedback engine.
The primary comparison uses group-dependent corrupted note-supported gold facts
(D-matched); actual Qwen extraction is separately benchmarked and compared with
exact-content sparse controls. This distinction prevents attributing observation
or note loss to an extractor. Outcome claims concern simulated withdrawal only.
These commands describe the existing runner, not authorization to repeat held-out
analyses under the old scientific assumptions. The saved historical run retains
its own [frozen protocol](results/research_evaluation_v1/research_evaluation_protocol_frozen.md)
and [manifest](results/research_evaluation_v1/configuration_manifest.json); its
protocol hash differs from the restored main copy after historical naming/wording
edits. Preserve that record rather than amending it to match the current checkout.

```sh
.venv/bin/python scripts/run_research_evaluation.py --stage freeze
.venv/bin/python scripts/run_extraction_benchmark.py --live
.venv/bin/python scripts/run_research_pilot.py
.venv/bin/python scripts/run_primary_experiment.py
.venv/bin/python scripts/run_research_sensitivity.py
.venv/bin/python scripts/run_research_evaluation.py --stage live
.venv/bin/python scripts/generate_research_report.py
```

Use `--output results/research_evaluation/new_run` on every research command for
an independent run; give the extraction command the corresponding
`--output-dir results/research_evaluation/new_run/extraction`. Existing completed
cells resume from saved artifacts. Input/source hash changes require an explicit
`--amend 'reason'`, create an immutable linked version under `versions/<identity>/`,
and require a fresh pilot. The original root manifest and protocol remain unchanged;
`current_version.json` selects the active version. New episodes, tables and reports
live inside that version. Historical unversioned runs cannot be amended in place.
Use `python scripts/verify_experiment_records.py <run-directory>` to verify all
retained manifests, protocols, predecessor links and completed episode artifacts
without rerunning experiments. New manifest version 4 also seals aggregates and
reports in append-only `versions/<identity>/reports/<generation>/` directories.
Each report manifest identifies its source experiment, contributing episodes and
the digest of every table, figure and report file. Convenience table/report paths
in the version directory point into the current sealed generation. Regenerating
a report preserves all earlier generations; editing, deleting or adding a file
inside one, or substituting a convenience link, fails verification.

Aggregation reports actual/expected primary cells and missing, failed or invalid
cells in `aggregation_status.json`. Primary completion requires both frozen
policies on every held-out seed in the primary D-matched setting, with validated,
compatible execution records. Partial reports and figures say
`INCOMPLETE / EXPLORATORY`; their paired statistics are conditional on completed
pairs and are exported as `exploratory_primary_comparison.csv`. A completed
`primary_policy_comparison.csv` and `primary_complete.json` are published only
after the full frozen matrix validates. Sealing an exploratory snapshot does not
make its research evaluation complete.

Episode and replay files are written in private staging directories and published
by rename only after validation, persistence and sealing. Research failures retain
an explicit failed-cell record and quarantined diagnostics; the same identity is
not silently retried. Interrupted locks/staging remain visible for diagnosis.
Use a fresh experiment identity/directory after inspecting a failed attempt.
Replay failures leave diagnostics outside the requested destination; an existing
successful replay is never replaced.

The verifier exits 0 for a fully verified current-contract record, 1 for a failed
integrity check, and 2 for partial historical verification. Version-3 records can
verify their original manifests and completed episodes, but lack the new derived
artifact guarantee. `--allow-historical` permits exit 0 while still reporting
`historical_partial` and `fully_verified: false`. Older unversioned evidence is
explicitly rejected. Historical records are never silently upgraded or resealed;
create an explicit amendment or a new run directory for the new contracts.

Extractor identity now includes backend implementation, a canonical endpoint
hash, actual execution options, available weight digest, prompt/schema hashes
and implementation fingerprints. Missing weight digests are explicitly labelled
as mutable model tags. Identities require no inference request. Authentication
URL components and arbitrary configuration/metadata are excluded from extractor
provenance and cache contexts; credentials must stay outside frozen configuration.
Do not amend a held-out analysis to select favorable policies. The real-model
cache records complete note/context, prompt/schema, source and model digest.
Failed extractions remain unknown and are recorded, never replaced with fixtures.

Outputs include episode/monthly, group access and frozen memberships, belief/risk,
solver/workload and paired confidence-interval CSVs; compressed complete episode
traces; sensitivity/ablation tables; failure cases; standalone figures; and a
research report under `results/research_evaluation/`. Consult the generated
report for actual results and incomplete acceptance items. Standalone regression
checks do not require Ollama:

```sh
.venv/bin/python -m unittest discover -s tests
```

The historical [acceptance audit](results/research_evaluation_v1/acceptance_audit.json)
records the old evaluation's scope gaps; it does not validate the Phase 1 implementation.

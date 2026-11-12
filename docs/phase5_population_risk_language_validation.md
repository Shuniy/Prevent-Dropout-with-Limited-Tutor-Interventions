# Phase 5 implementation and validation record

## Compatibility review (checkpoint 1)

Starting branch: `fix/phase-5-research-evidence-fix`; clean revision
`2d5f8ddf3ef9deeee52282a6bebb786ff4c8034c`. No merge is authorized.

The monthly `loading.load_students` selects a fixed prefix. The weekly demo uses
fictional profiles, while `WeeklyDeliveryEnvironment.from_students` already
adapts source context and privately calls the established reset mapping. Neither
path needs replacement. Source sampling belongs upstream of this adapter.

`WeeklyFeedbackController` creates notes only from authorized emissions, validates
sources and extraction, updates the filter, then prepares immutable weekly
snapshots. Fairness freezes after filtering. Policies consume those snapshots;
the environment alone applies delivery and transitions. Keep these boundaries.

`WeeklyRisk` and `WeeklyCommittedRisk` predict terminal non-enrollment, respectively
under usual support and accepted commitments. The new event-within-horizon model
must have its own records and may only affect an explicitly named baseline.
Offline reference labels can fork the current weekly world and execute WAIT,
which preserves accepted obligations. Truth is used only by that label generator.

Replay v3 seals and compares full public records and evaluator trajectories and
requires matching source/runtime. Phase 5 will wrap those artifacts in a new
versioned population/model envelope rather than relabel historical contracts.

The existing extraction benchmark explicitly shares canonical phrases with the
extractor and prompt. It is a composition benchmark, not independent language
validation. The production validator rejects unfamiliar sentences even when
quoted accurately. Evaluate this limitation honestly; do not broaden its grammar
using held-out answers. Human annotation and live inference are not available
from the repository and cannot be claimed.

## Implemented interfaces and file inventory

| File | Purpose |
|---|---|
| `src/school/population_sampling.py` | Frozen whole-profile sampler, validated split/group pool, immutable population/lineage records, context/missingness and distribution checks |
| `src/school/trained_withdrawal_risk.py` | Authorized feature allowlist, JSON logistic model, train-only preprocessing, validation-world calibration/selection, typed prediction/unavailability/OOD records |
| `src/school/phase5_delivery.py` | Opt-in legacy/source-held-out environment adapter, separate prediction records, trained-event-risk baseline, information conditions and new sealed replay envelope |
| `src/evaluation/phase5_prediction_evaluation.py` | Evaluator-only reference branches and event labels; target-matched analytical comparator; calibration, discrimination and world-level scoring |
| `src/evaluation/phase5_language.py` | Versioned prose cases/gold provenance, separated scoring, matched decision snapshots and actual-session continuation example |
| `src/evaluation/phase5_experiments.py` | Frozen execution, prediction/language/development/primary/secondary runners, four scorecards and independent recomputation |
| `configs/phase5_evaluation_v1.toml`, `configs/phase5_evaluation_v2.toml` | Retained original and amended explicit source/population/world partitions and bounded settings |
| `docs/phase5_research_protocol_v1.md`, `docs/phase5_research_protocol_v2.md` | Frozen original and dated non-vacuity amendment; assumptions, selection and interpretation rules |
| `docs/phase5_adverse_effect_protocol_v1.md` | Separate frozen custom-matrix stress test correcting the earlier adverse-effect support classification |
| `tests/test_phase5_population_prediction.py` | Lineage isolation, inheritance, missingness, RNG, model/feature/label boundaries, commitments, first-passage and replay regressions |
| `tests/test_phase5_language_research.py` | Language partitions, unsupported evidence, dates/unknown/conflict, actual downstream decisions, fixed-action invariance and research scorecards |
| `docs/phase5_acceptance_results.json` | Measured results, input hashes, runtime, model identity and acceptance status |
| `README.md` | Opt-in execution, verification and explicit live-inference commands |
| This document | Compatibility map, measured evidence and limitations |

The sampler returns `SampledPopulation`, containing immutable context rows and
separate evaluator lineage. `students()` returns ordinary `StudentSimulation`
objects with no anchor/group/seed fields. Model features are built only from a
`WeeklyStudent`; they contain no lineage, labels, private reset variables or
future outcomes. `PredictionController` records a separate prediction list and
caches its prepared cutoff. It does not substitute the analytical risk records
or planner's treatment-benefit calculation. `TrainedRiskPriorityPolicy` is an
explicit secondary baseline. The simulator still owns all treatment effects.

`phase5_source_weekly/replay/v1` is a new envelope, not a relabelled v3 record.
It saves sampled context/lineage, source fingerprints, generator settings,
population/world identities, model coefficients/calibration, full weekly payload,
protocol, source/runtime versions and evaluator draws/trajectory. Exact replay
regenerates population and declared information conditions and checks complete
decision/prediction/event/resource/fairness histories. The experiment verifier
also regenerates label branches, refits using train/validation only, and
recomputes metrics and all four saved scorecards. JSON model artifacts do not
execute arbitrary serialized model objects.

## Mathematical and data assumptions

The risk target is a first withdrawal event in the next `min(4,remaining)` weeks,
for current enrolled registry records. Accepted schedules continue with existing
attendance/delivery/cancellation assumptions and no new offers. A cloned reference
world executes the established weekly `step` mechanism. Labels observe whether
withdrawal occurs at any step. Analytical comparison kills withdrawn mass after
each transition; terminal non-enrollment is not substituted for the event target.
Current production transitions require absorbing withdrawal; a separate test
checks first-passage arithmetic for a hypothetical re-entry trajectory without
weakening that contract.

Source profiles are sampled jointly within their retained source split. The
sampler never derives school-dropout labels from grades. Missing mathematics is
preserved; income, verified disadvantage and observed school dropout remain
unknown. Other required source context is complete in this retained dataset;
missing required values cause an explicit error instead of silent imputation
into the historical runtime schema. Sampling is unstratified. Replacement is
explicit when requested cohort size exceeds the split pool. Reset attendance
and engagement ranges are declared synthetic assumptions, not source data fit.

Predictive preprocessing fits only source-train/worlds 100–109. Validation uses
source-validation/worlds 200–205, split by world into calibration and selection.
The three candidate L2 strengths and optional sigmoid calibration are fixed
before test labels are generated. Final prediction evaluation uses source-test
and worlds 300–307, with separately seeded cohorts. No landmark-level confidence
interval treats repeated students as independent. Pooled discrimination and
reliability are descriptive; mean-Brier intervals use world aggregates.

Primary allocation comparison uses the unchanged analytical risks and
FairPoint/FairRobust. The amended design uses 48 profiles and the supported
source-sex F/M audit grouping, with an explicitly artificial reporting-quality
difference. Thirty fresh world pairs 2000–2029 on one source-test cohort quantify
conditional simulation variation. Population seeds 55001/55002 and effect/capacity
sensitivities are separate exploratory factors, not replacements for this
primary estimate. Trained-risk law mismatches abstain during effect sensitivity;
they are not silently scored under a different reference regime.

## Language independence and remaining scientific limits

The 16/12/20 development/validation/test cases have disjoint scenario, paraphrase
and template-family identifiers. Their semantics and evidence annotations are
authored separately from the production grammar. Development includes canonical
phrases. Validation/test use new syntax; the extractor and prompt are not tuned
to those outputs. However, all cases share one synthetic author and the narrow
semantic schema. This is a bounded unseen-style challenge, not unrestricted
mentor-language generalization, independent human annotation, or an independent
note-generator study. No reviewers, adjudication or disagreement rates exist.
The larger requested corpus sizes are not claimed.

Structured-form gold is a non-language control. Downstream gold uses an explicit
canonical semantic bridge into the historical filter. Actual extracted prose
always passes through the existing validator; empty outputs lose recall.
Out-of-schema transport-cost and support-lifecycle constructs are retained in
annotation metadata but cannot establish verified income or educational success.
Static matched cases and an actual-session boundary fixture are engineering
evidence. The source-population closed-loop style conditions use observations
from each arm's own trajectory; no counterfactual note histories are reused.

Live LLM inference is optional and was not authorized as an automatic substitute
for offline evaluation. The offline runner records it as unexecuted. Explicitly
enable it with `--stage language --live-llm-model qwen3.5:latest`; unavailable
inference stays unexecuted with retained failures. No fixture replacement is
reported as a live result. Real-school calibration, causal effects, calibrated
uncertainty guarantees and broad natural-language generalization remain
unestablished. Delayed and individually heterogeneous effects are outside the
current weekly implementation and are explicitly unexecuted. Adverse effects
are supported through a custom valid weekly matrix and are evaluated in a
separate frozen follow-up; this corrects the earlier protocol classification.

## Execution evidence

Work resumed on 2026-11-13. The earlier `/tmp` environments were unavailable;
verification recreates CPython 3.12.12 with `requirements-offline.txt` at
`/tmp/phase5-venv`. The workspace `.venv` uses Python 3.14.8 and is not used for
research execution. Runtime/dependency identities are recorded in each run.

The first focused checks found a null-denominator aggregation error in empty
fairness cells; the aggregate now sums only defined nonempty-cell shortfalls and
retains empty-cell diagnostics. A first-passage test initially tried to pass a
re-entry matrix through production v1; the test now uses a future-world stub,
preserving the established absorbing contract. A supported-runtime rerun passed
39 focused tests. The ten-world development preflight completed without solver
failures or incomplete optimization stages. Earlier failure logs are not
reported as successful experiments. Final full-suite and retained-run evidence
is recorded below after completion.

## Non-vacuity audit and amendment

The first complete run passed 505 tests and exact verification of 217 episodes,
including regeneration of 24 reference-label worlds. Its primary policy cell,
however, was **unexercised**: population seed 55000 at size 12 selected no profiles
whose primary source-context need was tutoring. Both policies made zero offers,
spent zero and had undefined comparable-need access gaps. The zero paired
retention difference cannot answer the policy question. This is a scientific
acceptance failure despite executable replay and passing constraint tests.

The complete v1 artifacts remain sealed at
`results/phase5_evaluation_20261113_v1`; its matching source, configurations,
documents, tests and CSV inputs are preserved in the separately sealed
`results/phase5_v1_source_archive_20261113`. Running that archive's verifier from
its own root preserves exact v1 execution after current-source changes.

A public-context audit identified that only one of 55 source-test tutoring
anchors belongs to the True disadvantage-proxy group. The amended design uses
source sex, already supported by the weekly fairness contract, and 48
unstratified whole profiles with the unchanged population seed. No source need,
eligibility rule or transition changes. The original proxy-based comparison is
not silently relabelled as this new audit-group design. This amendment follows
inspection of v1 feasibility and public context; it is not an untouched first-look
evaluation of that population design. Fresh held-out world seeds are frozen in
v2 before any v2 policy outcomes are inspected. No best-outcome seed search occurs.

New public-input gates require feasible support for both audit groups and a
shared nonempty need stratum before any primary/development action. Publication
also requires actual offers and extraction attempts in both methods. Zero-offer
rows cannot claim an exercised comparison. Regression tests reproduce the v1
failure and verify the amended development cohort's public compatibility.

## Final measured results (2026-11-13)

### Verification and reproducibility

| Check | Measured result |
|---|---|
| Final focused Phase 5 suite | 47 tests passed, 6.109 seconds |
| Final complete offline suite | 513 tests passed, 114.729 seconds; no failures, errors or skips |
| Frozen v2 study | 217 exact episode replays: 214 source-based episodes and three controlled fictional mentor examples |
| Independent label verification | All 24 training/validation/test reference worlds regenerated; model refit on train/validation only; predictive report matched exactly |
| Independent derived records | All 190 main-study four-layer scorecards, extraction metrics and matched snapshot measurements recomputed |
| Adverse-effect follow-up | 15 exact episode replays and four-layer scorecards; all matrices checked against the frozen override |
| Exercised final episodes | 232, counting study plus adverse follow-up; these are not 232 independent statistical replicates |
| Final primary design check | Exactly 30 prescribed pairs / 60 cells; wrong/missing/duplicate/unexercised cells rejected |
| Historical entrypoints | Seven weekly demonstration episodes and exact replays; monthly fixture comparison completed for 3 students / 2 months / 35 cells |
| Original data and historical protocol | Unchanged; original monthly/weekly engine, analytical risk and extractor modules untouched |

The final study and adverse follow-up independently reconstruct resource ledgers,
decision-prefix spending, full schedules, mentor hours/slots/caseload and frozen
offer cohorts. Across their 205 four-scorecard episodes there were no solver
failures, incomplete optimization stages or quarantined extractions. Fairness
shortfalls remain nonzero where physical opportunities are insufficient. Zero
quarantines do not establish language quality: unfamiliar prose often produces
accepted empty extractions, whose missed facts are separately scored.

The complete-suite run immediately before the tuple normalization repair had
three new replay failures out of 505 tests; all 466 pre-existing tests passed.
The corrected 505-, 508-, 512- and final 513-test suites passed. The missing-model
HTTP regression failed before its repair, then passed. Invalid returned model
payloads remain executed extraction failures; all-backend-error requests are
unexecuted model evaluations, without fixture substitution. These live-backend
tests use mocks; no live language-model experiment was run.

An early overlapping baseline invocation was invalidated by source fingerprints
changing during implementation and is not a clean-baseline success claim.
Failed/preflight outputs and the unexercised v1 run were not overwritten.

### Population and prediction

The retained source pool has 674 anchors: train 404, validation 130, test 140.
All source linkage-group intersections across partitions are empty. The primary
uses 48 distinct test anchors without replacement. Every episode saves its full
lineage and numeric/categorical/missingness/relationship validation report.

Prediction labels: train 2,383; validation 1,404; test 1,915. The test comprises
eight independent world/cohort draws and **99 positive landmark labels**, not
99 independent observed students or necessarily 99 distinct withdrawal events.
The model selected by validation was L2 logistic regression, C=.1, with **no
additional calibrator**. Sigmoid alternatives were evaluated on the disjoint
validation calibration/selection partitions. Reliability is evaluated against
held-out simulated outcomes; empirical real-school calibration is unestablished.

| Target-matched predictor | Brier | Log loss | AUROC | Average precision |
|---|---:|---:|---:|---:|
| Trained logistic | 0.047464 | 0.185878 | 0.748109 | 0.144668 |
| Training-horizon prevalence | 0.048954 | 0.201292 | 0.604450 | 0.064903 |
| Analytical first-event / accepted commitments | 0.047973 | 0.189356 | 0.701539 | 0.097671 |

The reported test has two OOD predictions and zero abstentions. Discrimination
and pooled reliability are descriptive; world-level Brier summaries account for
shared/overlapping landmarks. JSON reports include horizon, missingness,
documentation and audited-group breakdowns, exact review-capacity denominators
and a calibration plot. The training benchmark uses two-session programmes;
the five-session allocation experiment can produce OOD inputs. Its diagnostic
predictions are not a new calibration validation under documentation stress.

### Extraction and downstream decisions

| Corpus partition | Notes | Supported gold facts | Correct extracted facts | Recall / F1 |
|---|---:|---:|---:|---:|
| Development | 16 | 10 | 10 | 1 / 1 |
| Validation | 12 | 8 | 0 | 0 / 0 |
| Held-out test | 20 | 11 | 0 | 0 / 0 |

Two notes across validation/test are temporally unavailable and are rejected
before inference; the test has 19 eligible notes. Test precision is undefined,
because no facts are predicted. Abstention is not scored as correct recall.
The structured-form gold control supplies the compatible semantic ceiling.
Production validation, prompt and controlled grammar are unchanged; this result
measures the validated pipeline, not unconstrained LLM comprehension.

Nineteen matched test-note snapshots actually invoked extraction. They showed
belief/risk differences but zero assignment disagreements in that selected
snapshot. The actual-session boundary example changed the cutoff-2 review from
cancel (supported regular observation) to continue (held-out prose produced no
fact), and changed a later feasible offer. Each subsequent arm used its own
trajectory and observations. This is a selected engineering example, not a
population effect estimate or independent human language validation.

### Frozen primary comparison

All 30 pairs were exercised. FairPoint made 9–13 offers per world; FairRobust
made 8–13. Executed offers/cancellations differed in 26 of 30 pairs.

| World-level outcome | FairPoint mean | FairRobust mean |
|---|---:|---:|
| Terminal retention | 77.8472% | 77.9167% |
| Worst audited-group retention | 73.3157% | 73.5097% |
| Unique offer rate, whole cohort | 21.5278% | 20.4861% |
| Programme completion rate, whole cohort | 4.4444% | 4.7917% |
| Sum normalized fairness shortfalls | 3.508108 | 3.545225 |
| Maximum comparable-need access gap | 41.5437% | 47.2090% |
| Actual expenditure, budget 40 | 31.9167 | 31.7733 |

FairRobust minus FairPoint retention: **+0.0694 percentage points**, paired
95% interval **[-0.3631, +0.5020]**, n=30. The comparable-need access-gap
difference is **+5.6653 points**, interval **[-2.5262, +13.8569]**. The upper
interval exceeds the prespecified five-point deterioration threshold. These
results establish neither a retention advantage nor a favorable tradeoff, and
do not establish equivalence. Small estimated-need cells make gap estimates
unstable. The intervals condition on this source cohort and assumed effects;
source resampling and effect/capacity sensitivities remain separate exploratory
results. The 110 secondary episodes were executed without choosing a preferred
grid cell as the primary finding.

### Adverse-effect correction and follow-up

Source review confirmed that a valid custom tutoring matrix is supported, despite
the earlier v1/v2 protocol classification. A separately frozen addendum records
an adverse matrix with withdrawal probabilities .003/.020/.080 versus usual
support .001/.010/.040 in the enrolled rows. No simulator or treatment mechanism
changed. Five paired worlds compared WAIT, FairPoint and FairRobust, with 15
episodes. Fair methods actually delivered 9–16 sessions per world; their observed
retention differences versus WAIT were zero in all five pairs. This small sample
does not establish zero causal effect or safety. A hand-computable transition
test confirms that the adverse matrix can change an enrolled state to withdrawal
under a draw that leaves usual-support enrollment intact. The positive-world
trained predictor abstained on all changed-law inputs, without a replacement
probability. Delayed and individual heterogeneous effects remain unexecuted.

## Commands and retained artifacts

The new immutable study is `results/phase5_evaluation_20261113_v2`; the separate
follow-up is `results/phase5_adverse_20261113`. The machine-readable acceptance
record is `docs/phase5_acceptance_results.json`. Logs and verification identities
are retained in `results/phase5_verification_20261113_final`.

Actually executed, from the repository unless an archived root is indicated:

```sh
/tmp/phase5-venv/bin/python -m pip install -r requirements-offline.txt
MPLCONFIGDIR=/tmp/phase5-mpl /tmp/phase5-venv/bin/python -m unittest discover -s tests -p 'test_phase5*.py'
MPLCONFIGDIR=/tmp/phase5-mpl /tmp/phase5-venv/bin/python -m unittest discover -s tests
/tmp/phase5-venv/bin/python -m src.evaluation.phase5_experiments --stage pilot --output results/phase5_v2_preflight_20261113
/tmp/phase5-venv/bin/python -m src.evaluation.phase5_experiments --stage all --output results/phase5_evaluation_20261113_v2
/tmp/phase5-venv/bin/python -m src.evaluation.phase5_experiments --stage adverse --model results/phase5_evaluation_20261113_v2/prediction/model.json --output results/phase5_adverse_20261113
/tmp/phase5-venv/bin/python -m src.evaluation.phase5_experiments --verify results/phase5_adverse_20261113
/tmp/phase5-venv/bin/python -m src.school.delivery_experiments --output results/phase5_legacy_weekly_20261113
/tmp/phase5-venv/bin/python -m src.main --extractor fixture --students 3 --months 2 --output results/phase5_legacy_monthly_20261113
git diff --check
```

The v2 study is frozen to its archived source. Subsequent changes only repaired
optional unavailable-backend reporting, strengthened primary-matrix verification
and added the separate adverse runner. The final source exactly reproduces the
saved predictive and extraction metrics, and independently checks all 60 frozen
primary cells. Exact whole-study replay correctly still requires the matching
source/runtime; guards were not weakened. The command actually used was:

```sh
cd results/phase5_v2_source_archive_20261113
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/phase5-mpl-run XDG_CACHE_HOME=/tmp/phase5-cache-run \
  /tmp/phase5-venv/bin/python -m src.evaluation.phase5_experiments \
  --verify /Users/shuniy/Documents/projects/school-dropout/results/phase5_evaluation_20261113_v2
```

Disable bytecode writing when using sealed source archives. The v1 archive was
also executed successfully; automatically generated import caches were removed
and its original inventory verified. Source snapshots preserve the matching
scientific version rather than claiming today's checkout equals an older run.
These local ignored result directories are not distributed by Git; commands
recreate new runs in fresh destinations. No remote CI success is claimed.

## Acceptance status and unresolved requirements

- **Implemented and tested:** source sampling/lineage, weekly integration, exact
  replay, trained event-risk interface, reference labels, selection/calibration
  comparison, failure/OOD handling, benchmark/gold metrics, actual downstream
  filtering/allocation, frozen primary and separate scorecards.
- **Experimentally validated within the declared simulator:** source-held-out
  episodes; prediction on held-out source groups/worlds; 30 exercised policy
  pairs; capacity/effect/cohort sensitivities; adverse stress and exact replay.
- **Partially satisfied language acceptance:** separate styles/scenarios and
  content labels exist, but the corpus is small and single-author, without
  independent human annotation or an independent external generator. The
  validated grammar fails on all supported held-out facts. Broader independent
  language generalization is **not established**. Live LLM comparison is
  unexecuted; the explicit command is in the README. No substitute fixture result
  is described as a live model result.
- **Not established:** real-school dropout prediction/calibration, causal
  educational effects, unrestricted natural-language performance, favorable
  uncertainty/fairness tradeoff, equivalence, or broad population conclusions
  from one primary cohort. No full-acceptance or positive-research-result claim
  follows from passing tests.

Git remains at `2d5f8ddf3ef9deeee52282a6bebb786ff4c8034c` on
`fix/phase-5-research-evidence-fix`, with uncommitted Phase 5 additions and README
navigation. Source fingerprints identify those additions separately from HEAD.
No commit, push, pull request, merge or historical-output overwrite was made.

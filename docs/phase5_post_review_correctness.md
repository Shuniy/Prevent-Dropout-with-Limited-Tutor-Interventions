# Phase 5 post-review correctness and Python 3.13

Implemented and locally verified on 13 November 2026. Scientific evidence below
is a bounded synthetic pilot. Remote CI is pending the first push of this change;
its three required jobs are unit tests, adaptive acceptance and Phase 5 acceptance.
Measured identities and denominators are retained in
[phase5_post_review_results.json](phase5_post_review_results.json).

## Findings and corrections

- A: Aggregate session counts omitted future timing; the fingerprint omitted
  duration/cadence, while training used two sessions. Model/schema v2 adds four
  future reservation indicators, validates commitments, fingerprints programme
  and transition/delivery assumptions, and abstains on unseen training schedule
  patterns or incompatible regimes. The new five-session model is separately fit
  and evaluated. The original model implementation is retained byte-for-byte in
  `trained_withdrawal_risk_v1.py`; the active v2 loader rejects v1 artifacts.
- B: The original extractor's exact language allowlist generalized poorly. Its
  frozen development 10/10, validation 0/8 and test 0/11 results remain unchanged.
  A separate synthetic language v2 corpus, development-only evidence rules,
  prompted Ollama path, external annotation contract and downstream comparisons
  were added. No independent human review is claimed.
- C: Event prediction and treatment benefit are different quantities. Analytical
  FairPoint/FairRobust benefit calculations are unchanged. Trained risk priority
  is a separate baseline, with explicit incompatible-regime rejection.
- D: The original 30-world result was conditional on one fixed cohort. A separate
  three-population/two-world pilot now reports nested world variation, population
  mean clusters, ancestry reuse, support feasibility and fairness separately.
- E: Active CI used an unavailable fixed Python 3.12 patch. All three jobs now
  consume one minor-version declaration, Python 3.13, and retain failure logs.
  `bash -euo pipefail` preserves failures through `tee`; missing required reports
  fail acceptance. Upload failure cannot mask an earlier failure, and successful
  acceptance additionally requires successful evidence upload.

## Runtime and dependencies

`.python-version` is `3.13`; packaging requires `>=3.13,<3.14`. README,
bootstrap, provenance checks and verification commands use Python 3.13 only.
CI selects the runner's latest available 3.13 patch. Local `python` and `python3`
inside the isolated environment both reported **3.13.5**.

Both requested installation commands succeeded: frozen offline requirements and
`python -m pip install --no-deps -e .`. Offline pins were retained without a
version change. Their original Python 3.12 freeze comment remains true historical
provenance. The complete `requirements.txt` also installed in a separate Python
3.13 environment; `pip check` and imports of NumPy, pandas, matplotlib, sklearn,
SciPy, torch, torchvision and notebook passed. The optional environment was not
used for the scientific results or claimed to have passed the full suite.

## Prediction design and results

Target remains at least one withdrawal event over min(4, remaining weeks), for a
currently enrolled simulated student continuing accepted schedules with no new
scarce offers. Features contain authorized beliefs, documentation, identities,
horizon, programme state/counts and `scheduled_session_week_0` through `_3`.
Future attendance/delivery realizations, hidden state, source ancestry, labels,
measurements and draws do not enter features. Future realized session statuses
are rejected. The law fingerprints duration, cadence, first-session convention,
commitment/cancellation semantics, acceptance, attendance, delivery and transitions.

The new model uses five sessions at weekly cadence, training worlds 1200–1203,
validation calibration worlds 1300/1302 and selection worlds 1301/1303. Test worlds
1400/1401 are generated only after the selected artifact is saved. Preprocessing,
coefficients, categories and supported schedule patterns use source-train only.
Selection chose C=10 and sigmoid calibration. Fourteen training schedule patterns
are supported; other patterns abstain. Test source lineages and worlds cannot
enter selection. Unsupported two-session/cadence configurations and old schemas
are rejected or explicitly unavailable. Missingness and range/category OOD remain
reported rather than silently suppressed.

Model ID: `d8b42b2685d907c7d2e06f84c72ac0c281d49e0bfec157d4ccfef236e4fed046`.
429 held-out landmarks, 33 events, zero abstentions, 3 OOD flags and 11 records
with missing features. These overlapping landmarks are descriptive; uncertainty
uses the two independent test-world draws, with very limited precision.

| Predictor | Pooled Brier | AUROC | Log loss |
| --- | ---: | ---: | ---: |
| Schedule-aware trained | 0.070380 | 0.591177 | 0.268065 |
| Training constant by horizon | 0.069205 | 0.659053 | 0.255308 |
| Target-matched analytical | 0.069292 | 0.702556 | 0.253006 |

There is no established trained-model advantage. Calibration tables, by-world,
by-horizon, documentation, missingness and group results are retained in the
prediction output; the target-matched comparator is not a planner benefit model.

## Language execution and decision effects

Real `qwen3.5:latest` inference executed: **19 requests, 19 responses**, temperature
0, context 8192, timeout 45 seconds and zero retries. The observed inventory digest
was `d63f830f28d515fefea546f213fca7a75e9dd5176ef51a6deabc952d1c99a911`;
this is recorded provenance, not independent server attestation. Prompt and rule
hashes, raw/validated outputs, rejection reasons and latency are retained. An
initial development-only response invented status fields and was rejected; the
prompt was clarified using complete development mappings before the final
validation/test evaluation. No prompt or evidence rule was selected using test
outcomes. Superseded attempts remain retained separately.

| New corpus partition | Supported facts recovered | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Development | 6/6 | 1.00 | 1.00 | 1.00 |
| Validation | 3/3 | 1.00 | 1.00 | 1.00 |
| Test | 3/6 | 1.00 | 0.50 | 0.667 |

Three supported test sentences exceeded conservative entailment-rule coverage and
were quarantined. This is a remaining recall failure. The original deterministic
extractor recovered zero facts in this follow-up corpus; gold/structured controls
are references, not model successes. Shared semantic categories/development
grammar and one synthetic author prevent an independent-template, natural-language
or human-validation claim. See the
[external annotation contract](phase5_external_annotations_v2.md).

The controlled actual-session comparison made **one additional real model request
and received one response**. All non-focal notes use the common canonical control;
only the focal mentor note goes to the model. Backend failure cannot change the
matched pre-note prefix, and a failed focal call supplies no fallback. The real
validated fact matched gold beliefs, risks and cancellation at week 2, releasing
resources for a feasible week-3 offer. Existing deterministic extraction missed
the fact, continued the programme and changed later allocation. This proves an
exercised information-to-decision path, not an improvement in simulated retention.
Each arm subsequently generates notes from its own trajectory with keyed exogenous
mechanisms. Source-held-out closed loops ran all five offline controls; the full
real-LLM source-held-out trajectory is implemented and mock-tested but unexecuted.

## Population robustness

The prespecified new source-test seeds are 65000, 65001 and 65002, with two nested,
non-overlapping world seeds each. Each cohort has 48 unique anchors drawn without
replacement from 140 held-out anchors. Cohort pairs reuse 13, 21 and 13 anchors.
These are seeded simulator draws from a finite pool, not independent observed
schools. Source-train/validation/test boundaries remain disjoint.

All 12 policy episodes had nonzero offers and exercised audited comparable-need
groups; there were zero solver failures and zero incomplete optimization stages.
Eligible support types/groups, feasible offers, cohort/lineage identities and
replacement/repeated ancestry are saved. No draw was replaced based on outcomes.
Population means, not students or overlapping worlds, are the summary clusters;
within-population world variance and a labelled method-of-moments decomposition
are retained. With only three clusters, these intervals are exploratory.

| FairRobust minus FairPoint | Population mean | Descriptive 95% cluster interval |
| --- | ---: | ---: |
| Retention | +0.347 percentage points | [-1.147, +1.841] pp |
| Comparable-need access gap | +0.03953 | [0.03493, 0.04413] |
| Normalized fairness shortfall | +0.34509 | [-0.31582, 1.00599] |
| Worst-group retention | 0 | [0, 0] in this small pilot |

Retention advantage is not established. Larger access gaps/shortfalls are not
fairness improvements. The observed zero worst-group difference does not establish
equivalence. The original fixed-cohort confirmatory conclusion remains unchanged.

## Verification and retained outputs

| Verification | Actual result |
| --- | --- |
| Isolated original commit on Python 3.13 | 513/513 passed |
| Complete corrected offline suite | 552/552 passed, zero errors/failures |
| Focused Phase 5 suite | 86/86 passed |
| Phase 2 harness | 69 focused + 552 full tests passed; four recorded replay conditions |
| Phase 3 harness | 124 focused + 552 full tests passed; 40 episodes, eight policies replayed |
| Phase 4.1 acceptance | 12 exact replays passed |
| Phase 4.2 acceptance | 5 exact replays passed |
| Original monthly and weekly entrypoints | Both executed successfully |
| New bounded acceptance | 22 episodes, 9 reference worlds regenerated |
| New research pilot | 33 episodes, 10 reference worlds regenerated |
| Real-language run | 11 episodes, recorded inference replay with zero new requests |
| CI failure pipeline probe / shell syntax / diff whitespace | Passed |

Final output root: `results/phase5_post_review_20261113/`. Definitive directories
are `bounded_acceptance_verified`, `research_pilot_verified`,
`real_language_verified`, `phase2_verified`, `phase3_verified`,
`phase4_1_verified`, `phase4_2_verified`, `legacy_weekly_verified` and
`legacy_monthly_verified`; logs are under `logs/`. These full local outputs are
ignored by git. The committed measured summary records their inventory hashes.
CI uploads its separately generated synthetic acceptance evidence and diagnostics.

Every final Phase 5 run verifies complete inventories, exact notes/extractions,
beliefs, predictions, decisions, resources, fairness, truth and keyed draws.
Reference branches are regenerated, train/validation fitting is recomputed and
held-out scores/cluster summaries/derived scorecards are independently checked.
Resealed forged summaries and missing artifacts are regression-tested as failures.
An earlier architecture import failure was fixed without weakening its existing
test. Runs that overlapped source edits were rejected by provenance and are not
claimed as definitive verification. Final source-fingerprint identity:
`de2263f301589e4639e92fb88bb0a18e5050fdef87d8d3ae6ba29e61724d8ea9`.

Historical inputs and the copied original model passed ten byte-hash checks.
Old protocols, datasets, results and Python/runtime provenance were not rewritten.
Old exact replay still requires the original source and dependency environment;
no claim of bit-for-bit Python 3.12-to-3.13 replay is made.

## Reproduction

Use a fresh output path for each execution and activate Python 3.13 first:

```bash
bash scripts/bootstrap.sh .venv313
source .venv313/bin/activate
python --version
python -m pip install -r requirements-offline.txt
python -m pip install --no-deps -e .
python -m unittest discover -s tests
python -m unittest discover -s tests -p 'test_phase5*.py'
python scripts/verify_phase2.py --output results/new_phase2
python scripts/verify_phase3.py --output results/new_phase3
python -m src.school.delivery_acceptance --output results/new_phase41
python -m src.school.delivery_feedback_acceptance --output results/new_phase42
python -m src.evaluation.phase5_followup --stage acceptance --output results/new_acceptance
python -m src.evaluation.phase5_followup --stage all --output results/new_pilot
python -m src.evaluation.phase5_followup --verify results/new_pilot
python -m src.evaluation.phase5_followup --stage language --llm-model qwen3.5:latest \
  --timeout 45 --retries 0 --llm-downstream boundary --output results/new_llm
python -m src.evaluation.phase5_followup --verify results/new_llm
# Explicit larger inference scope, not executed in the retained pilot:
python -m src.evaluation.phase5_followup --stage language --llm-model qwen3.5:latest \
  --timeout 45 --retries 0 --llm-downstream all --output results/new_llm_closed_loop
python -m src.main --extractor fixture --students 3 --months 2 --output results/new_monthly
python -m src.school.delivery_experiments --output results/new_weekly
git diff --check
```

## Exact changed files

```text
.github/workflows/offline-tests.yml
.gitignore
.python-version
README.md
configs/phase5_followup_v3.toml
configs/phase5_historical_inputs_v1.json
docs/phase5_external_annotations_v2.md
docs/phase5_post_review_correctness.md
docs/phase5_post_review_protocol_v3.md
docs/phase5_post_review_results.json
pyproject.toml
requirements-offline.txt
scripts/bootstrap.sh
scripts/verify_phase2.py
src/evaluation/phase5_experiments.py
src/evaluation/phase5_followup.py
src/evaluation/phase5_language_decisions.py
src/evaluation/phase5_language_followup.py
src/evaluation/phase5_prediction_evaluation.py
src/evaluation/provenance.py
src/intervention/followup_extractor.py
src/intervention/observation_extractor.py
src/intervention/ollama_client.py
src/school/followup_notes.py
src/school/phase5_delivery.py
src/school/population_sampling.py
src/school/state_estimator.py
src/school/trained_withdrawal_risk.py
src/school/trained_withdrawal_risk_v1.py
tests/test_phase5_acceptance_integrity.py
tests/test_phase5_language_followup.py
tests/test_phase5_population_robustness.py
tests/test_phase5_schedule_followup.py
```

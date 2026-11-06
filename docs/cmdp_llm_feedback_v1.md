# Step 5: sequential language feedback

Step 5 connects the existing finite-horizon CMDP to observable events, dated notes,
validated extraction, categorical state estimation and model-based synthetic risk.
Both existing MILP planners consume the resulting immutable decision snapshots.
The environment still owns all true transitions, programme execution and resources.
This implementation stops before the Step 6 research evaluation.

## Entry points and reused code

Use `School.run_cmdp_feedback(policy, config=..., mode=..., extractor=...)`, or the
[pilot](../scripts/run_cmdp_feedback_pilot.py) and
[integration](../scripts/run_cmdp_feedback.py) commands.
The existing `run_cmdp`, recorded-intervention simulation, SimpleLLM and RAG APIs
remain available.

The new extraction adapter reuses [OllamaClient](../src/intervention/ollama_client.py)
and the strict schema builders in [findings](../src/intervention/findings.py).
It uses the same installed `qwen3.5:latest` model, JSON inference API,
temperature zero and initialized client reuse. Model weights are unchanged.
The existing SimpleLLM and RAG analyze recorded histories with their own chronology;
those histories are not observations of the current synthetic trajectory. They are
therefore preserved rather than being attached to unrelated simulated students.
No retrieval architecture or training is added.

## Files

| Responsibility | Implementation |
| --- | --- |
| Neutral event, registry and note contracts | [observable_events](../src/observations/observable_events.py) |
| Versioned synthetic observation emissions | [observation_model](../src/school/observation_model.py) |
| Restricted event-to-note rendering | [feedback_notes](../src/intervention/feedback_notes.py) |
| Schema, fixtures, validation and cached Ollama extraction | [observation_extractor](../src/intervention/observation_extractor.py) |
| Immutable beliefs and Bayesian filtering | [belief_state](../src/school/belief_state.py), [state_estimator](../src/school/state_estimator.py) |
| Synthetic endpoint risk | [simulated_withdrawal_risk](../src/school/simulated_withdrawal_risk.py) |
| Monthly orchestration | [closed_loop_controller](../src/school/closed_loop_controller.py) |
| Experiment exports and figures | [feedback_experiments](../src/school/feedback_experiments.py) |
| Independent ledger checks and paired feedback demonstration | [feedback_validation](../src/school/feedback_validation.py), [verification command](../scripts/verify_cmdp_feedback.py) |
| Saved-extraction replay | [feedback_replay](../src/school/feedback_replay.py), [replay command](../scripts/replay_cmdp_feedback.py) |
| Research assumptions | [configuration](../configs/cmdp_llm_feedback.toml) |
| Tests | [extraction](../tests/test_feedback_extraction.py), [estimation](../tests/test_feedback_estimation.py), [closed loop](../tests/test_feedback_closed_loop.py) |

Existing files extended: [School](../src/school/school.py),
[environment](../src/school/cmdp_environment.py),
[student observation](../src/school/student_observation.py),
[decision snapshot](../src/school/decision_state.py),
[retention values](../src/school/retention_value.py),
[resource planner](../src/school/constrained_planner.py),
[fairness planner](../src/school/fairness_planner.py),
[fairness cohorts](../src/school/fairness_audit.py), and
[window forecasting](../src/school/window_optimization.py).
The unchanged keyed-draw algorithm now lives in
[keyed_random](../src/utils/keyed_random.py) and remains importable through
[transition_model](../src/school/transition_model.py). This preserves existing
random draws while keeping intervention modules independent of the school package.

## Information boundaries and observation assumptions

Only the environment supplies current realized conditions to the observation
generator. The note renderer accepts the neutral `ObservableEvent` dataclass and
has no environment, transition matrix, future outcome, grade or attendance input.
Source student/mentor objects are copied by the existing environment and stay unchanged.

The declared emission matrix has four qualitative signals: regular participation,
assignment difficulty, low participation and no recent contact. Its rows overlap;
the same note can arise from different conditions. Missingness and delay are
independent keyed draws. Misleading reports are a uniform mixture with the
configured emission row, and that mixture is included in the estimator likelihood.
All probabilities are synthetic research assumptions, with no empirical calibration.
The configuration can express more accurate or less informative emissions without
introducing a new intervention model.

Administrative enrollment is a separate, explicitly declared exact observation
shared by all information modes. A dated `EnrollmentRecord` supplies initial
cohort membership and each subsequent operational enrollment status. It is never
inferred from missed contact. Ordinary decision snapshots compute eligibility and
waiting time from these authorized records and committed programme histories;
they do not inspect hidden conditions. Holding these records fixed while changing
hidden truth leaves the serialized ordinary decision input unchanged. This exact
registry assumption reveals registered withdrawal, while the three active
conditions remain uncertain. It is not a model of delayed withdrawal registration.

Monitoring events are generated for untreated students, supported students and
registered withdrawals. The existing programme execution establishes completion
of its five appointments; it does not establish helpfulness, barrier resolution or
causal effectiveness. Original numeric attendance and grades never evolve.
Support routing uses the existing static primary-need rules and mentor skills.
The LLM cannot change a support need or protected attribute. An unsupported need
has no invented compatible mentor and remains visible in the existing
no-compatible-student accounting.

Every note retains its student, optional mentor/programme, type, source event IDs,
event month, ISO creation time and availability cutoff.
The synthetic calendar begins on 2026-01-01 UTC and uses 30-day periods.
Creation must follow its event and precede availability. An event at month `t`
is available no earlier than decision cutoff `t+1`; configured delays add periods.
Post-final-transition records can inform terminal estimates, never a thirteenth action.

## Extraction contract

An `ExtractedObservationBatch` identifies the student, note and cutoff. Each fact
separately carries:

- `field`, `assertion_status`, `trend`, `condition_status` and qualitative `value`;
- `barrier_status` and `workflow_status`;
- verbatim `evidence`, Python character offsets `[start,end)`, and `source_month`;
- trusted source-event identity and a stable evidence hash assigned by validation.

This supports reported/observed facts, negation, insufficient evidence, unresolved
contradictions, improvement/worsening, unchanged status, partial resolution,
unresolved barriers and pending/completed support. A pending application remains
an unresolved barrier. A low participation level alone does not establish worsening.

Extraction deliberately supports a finite synthetic sentence grammar. Semantic
validation requires a complete supported source sentence and its exact field
mapping. This rejects hallucinated claims even when a citation mentions the same
topic. Unsupported prose is omitted or quarantined; there is no automatic repair.
`numeric_value` and `unit` must be null because no dynamic numeric observation
process is declared. Risk, treatment effects, diagnoses, poverty and protected
attributes are outside the schema. There is no confidence-to-probability mapping.

The model receives verified sentence offsets as source formatting, and copies
them into its extraction. Output offsets are still checked; no incorrect model
output is silently corrected. Note text is JSON-encoded untrusted data in a user
message. Instructions inside it never become code, configuration, allocations or
eligibility changes. Embedded/negated supported phrases are not accepted as facts.

The controller sends only intervention programme notes to the LLM. Routine
monitoring, including month-zero observations and students without interventions,
uses the deterministic synthetic-grammar extractor. This preserves the actual
note-supported content and timing in every mode. No programme failure is replaced
with deterministic facts.

Cache keys include note identity, a hash of the entire note record, extractor,
prompt, schema and as-of cutoff. Only newly available notes are processed.
Accepted results, raw model outputs, cache hits and quarantined failures are logged.
Each policy still generates notes from its own realized trajectory. Cache reuse
requires identical authorized note content and context.

`FixtureObservationExtractor` uses fixed payloads or exact grammar lookups and
runs the same validator. Fixture runs are explicitly labeled and never reported
as successful LLM inference. Unavailable or invalid programme inference preserves
the prediction and records the failure; it does not substitute gold facts.

## Estimation, risk and allocation mathematics

The initial prior is `(1/3, 1/3, 1/3, 0)`, conditional on cohort enrollment.
The estimator records its prior, emission assumptions and assumed transition
matrices separately from the environment's parameters. For a boundary after
admission month `t`, prediction uses:

`b_minus = b_previous @ P_action`

The programme matrix applies once for the actual admission-month transition.
Subsequent transitions use WAIT. An administrative record conditions on observed
enrollment. A supported signal then uses the explicitly declared emission column:

`b_updated[s] = likelihood[signal|s] * b_minus[s] / sum(likelihood * b_minus)`

One source event contributes at most one emission. Duplicate evidence hashes are
ignored; incompatible signals from the same event are retained as unresolved and
quarantined from the numerical update. Qualitative evidence without a declared
signal likelihood stays in the uncertainty record. Zero-likelihood updates preserve
the prediction and record a reason; impossible registry observations fail explicitly.
Missing notes still permit model prediction and entropy/uncertainty tracking.

Late evidence is inserted at its source time and the current belief is recomputed
through known actions and available observations. Previously persisted estimates
and decisions remain unchanged. Every update records previous/predicted/posterior
beliefs, accepted/rejected evidence, reasons, provenance and uncertainty.

For `h` transitions remaining and `e = [1,1,1,0]`, risk is:

`risk = 1 - b @ P_WAIT**h @ e`

Its target is synthetic terminal non-enrollment under no additional programmes,
with a horizon, cutoff, input estimate ID and missingness flags.
Absorbing withdrawal makes endpoint non-enrollment compatible with withdrawal by
the endpoint. Re-entry would require revising the target. This is not a real-world
dropout predictor or a relabeled source-course-failure classifier.

The shared Step 3 benefit function now also accepts:

`benefit = b @ (P_PROGRAMME - P_WAIT) @ P_WAIT**(h-1) @ e`

Oracle mode retains the original point-state benefit. Risk never replaces benefit.
Both planners validate that all estimates and risks belong to the same decision
cutoff and estimate ID. The existing candidates, MILP variables, exact-money
budget checks, mentor compatibility, capacity and independent validation remain.
Future fairness-window benefits propagate the current belief under WAIT.

At every existing four-month fairness boundary, estimated-mode cohorts use the
observed eligible students, authorized audit attributes and their MAP condition
only when its probability is at least 0.6. Other enrolled students enter an
explicit `uncertain` stratum. Denominators stay frozen throughout the window.
Actual programme admissions update the existing coverage ledger; shortages use
the existing shortfall variables and never relax hard resource constraints.
Oracle cohorts retain their original categorical-condition strata.

## Monthly order and modes

At reset the environment initializes truth, emits initial observable/registry
records, and the controller builds beliefs and risks. Each decision cutoff then:

1. Processes available monitoring deterministically and sends only available
   intervention programme notes to the LLM in C/D modes.
2. Updates beliefs with known past admissions and recalculates risks.
3. Builds an immutable, consistent decision snapshot and plans/validates allocation.
4. Lets the existing environment commit resources, execute support and transition.
5. Emits the next monitoring/programme records and notes, then advances the cutoff.

The information modes are `oracle`, `structured` (B), `b_matched`, `llm_notes` (C)
and `noisy_notes` (D). B-matched contains exactly the available note-supported
content, including omissions and dates. D additionally corrupts/omits/delays notes
or introduces conflicts. Note-layer corruption is intentionally not treated as a
new calibrated emission model. Ordinary modes share the same estimator and solvers.
Oracle snapshots expose only current truth for the diagnostic benchmark; their
auxiliary belief/risk traces remain the observation-based estimates.

Only one programme per student is allowed. Updated evidence for supported students
changes their estimates but cannot enable another programme. The principal feedback
allocation effect therefore concerns untreated students.

## Outputs, verification and reproduction

Every episode has initial observations, observable events, registry records,
mentor notes, extracted observations/attempts/failures, estimate updates, risks,
decision snapshots, allocation decisions, fairness-window rows and a configuration
manifest. Truth trajectories are under a separate `evaluator_only` directory.
Policies receive in-memory snapshots and have no evaluator-file API. This is an
application information boundary, not an operating-system sandbox for arbitrary
malicious policy code.

Root outputs include episode/comparison CSVs and three actual-execution figures:
belief evolution, synthetic risk evolution and admissions over time. Configuration,
seed, transition matrices, observation assumptions, policy type,
solver settings and available model digest are saved. Output directories
must be new. The independent trace checker recomputes feasibility, unique admissions
and resource balances from the episode records.

Run from the repository root, with the existing environment:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m unittest tests.test_feedback_extraction tests.test_feedback_estimation tests.test_feedback_closed_loop -v
.venv/bin/python scripts/verify_cmdp_feedback.py --output results/cmdp_llm_feedback_v1/my_feedback_evidence
.venv/bin/python scripts/run_cmdp_feedback_pilot.py --output results/cmdp_llm_feedback_v1/my_fixture_pilot
.venv/bin/python scripts/run_cmdp_feedback.py --output results/cmdp_llm_feedback_v1/my_fixture_integration
.venv/bin/python scripts/run_cmdp_feedback_pilot.py --extractor ollama --max-notes-per-month 1 --modes b_matched llm_notes noisy_notes --output results/cmdp_llm_feedback_v1/my_ollama_pilot
.venv/bin/python scripts/run_cmdp_feedback.py --extractor ollama --max-notes-per-month 1 --output results/cmdp_llm_feedback_v1/my_ollama_integration
.venv/bin/python scripts/replay_cmdp_feedback.py --source results/cmdp_llm_feedback_v1/my_ollama_integration/resource_llm_notes_seed_42 --output results/cmdp_llm_feedback_v1/my_replay
```

Ollama must already serve `qwen3.5:latest`; `--model` and `OLLAMA_BASE_URL` retain
the existing runtime choices. `--seed`, `--policies`, `--modes`, `--timeout` and
`--max-notes-per-month` support limited development runs. The limit selects only
intervention programme notes per source month, identically in B-matched and C;
routine monitoring is retained without LLM calls. Delays can bring notes from
multiple source months to the same decision cutoff. With the default one monthly
admission per mentor, two mentors and twelve months, each policy/LLM mode makes at most 24 calls, compared
with the former population-wide ceiling of 1,300. Missing notes, delayed terminal
notes, limits and cache hits can reduce this count. Historical result reports retain their
original population-wide extraction and note-selection semantics.

Replay uses the saved configuration, seed and accepted extraction payloads with
no model call, and verifies exact decision snapshots, admissions, resource balances
and evaluator trajectories. Historical inference failures remain missing evidence.

The feedback configuration intentionally permits only one admission/five
appointments per mentor per month, so untreated students remain actionable across
months. The pilot has 12 students, two mentors, four months and 20 budget units.
The integration has 100 students, two mentors, 12 months and 150 units. These
explicit capacity choices differ from the earlier baseline's larger monthly capacity.

See the [execution report](cmdp_llm_feedback_v1_results.md) for actual test,
pilot, paired-feedback and 12-month results and links to the saved traces.

## Limits and Step 5 acceptance scope

The emission probabilities, prior, uncertainty threshold and note grammar are
declared assumptions. Open-domain human notes require a broader validated semantic
adapter before research use. Numeric extraction is deliberately unsupported.
Observation likelihoods are not calibrated and no statistical superiority claim
follows from these single-development-seed runs. Sparse real-model runs validate
integration under a stated note limit, not full-population extraction quality.
Model JSON generation is deterministic in configuration but hardware/runtime
variations can affect regenerated output; saved extraction records support audit.
The configured environment reports Python 3.14.8, while the project's declared
support range remains 3.12–3.13; this task does not certify a new Python version.

There is no repeated mentoring, new treatment model, model training, new RAG,
multi-agent negotiation, dashboard or held-out Step 6 evaluation.

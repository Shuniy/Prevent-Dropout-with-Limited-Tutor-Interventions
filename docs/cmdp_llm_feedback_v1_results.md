# Step 5 execution report

Implementation details, changed files, interfaces, mathematical assumptions and
exact reproduction commands are in the [Step 5 contract](cmdp_llm_feedback_v1.md).
All results below are actual development executions with seed 42. No Step 6
held-out or large-scale research evaluation was launched.

## Tests and independent checks

Before implementation, `.venv/bin/python -m unittest discover -s tests` passed
all 162 existing tests in 44.588 seconds. The final command
`.venv/bin/python -m unittest discover -s tests` passed **189 tests in 49.214 seconds**,
including all previous regressions and the saved-extraction replay test. Its
complete output is saved in
[test_results_final_189.txt](../results/cmdp_llm_feedback_v1/test_results_final_189.txt).

The focused command is:

```bash
.venv/bin/python -m unittest tests.test_feedback_extraction tests.test_feedback_estimation tests.test_feedback_closed_loop -v
```

It covers schema/identity/evidence/offset validation; qualitative trends, pending
support and negation; prompt instructions and embedded negated phrases; invalid or
unavailable inference; date gating, omission and delay; hand-calculated Bayes;
correct action-specific prediction applied once; duplicate/correlated/contradictory
evidence; zero likelihood; delayed source-time replay; endpoint risk and point-state
equivalence; stale risk rejection; both planners, frozen uncertain fairness strata,
one programme, resource limits, information isolation and exact saved replay.

All new core modules were checked with editor diagnostics. The existing
School module retains its prior package-resolution/type warnings; runtime package
imports and the full regression tests succeed. `git diff --check` passes.
The selected environment reports Python 3.14.8; declared project support remains
Python 3.12–3.13 and was not changed by this task.

## Small pilot

The pilot uses 12 students, two mentors, four months, one monthly admission/five
appointments per mentor and a 20-unit budget. All ten fixture planner/mode runs
completed with 12 terminal enrolled students, four unique programmes and exactly
20 units spent. No hard constraint failed. Its complete data are under
[pilot_fixture_v3](../results/cmdp_llm_feedback_v1/pilot_fixture_v3), including
[the comparison](../results/cmdp_llm_feedback_v1/pilot_fixture_v3/episode_results.csv)
and [the belief figure](../results/cmdp_llm_feedback_v1/pilot_fixture_v3/figures/belief_evolution.png).

The final real-model pilot used one note per period (five generated notes including
initial and terminal records), B-matched/C/D, and both planners. All six episodes
also ended with 12 enrolled, four programmes, 20 units spent and zero quarantined
extractions. The local Qwen runtime performed six actual inference calls; identical
authorized notes/context could reuse accepted cached output. See
[pilot_ollama_v3](../results/cmdp_llm_feedback_v1/pilot_ollama_v3) and its
[comparison](../results/cmdp_llm_feedback_v1/pilot_ollama_v3/episode_results.csv).

Earlier exploratory outputs remain under their original v1/v2 directories.
The first prompt produced incorrect character offsets, which were quarantined.
It was stopped after preserving the completed episode outputs. Supplying verified
source spans corrected the issue; no invalid extraction was converted into a fact.
The v3 runs use the final trend semantics and prompt version.

## Evidence that feedback changes allocation

The [paired demonstration](../results/cmdp_llm_feedback_v1/allocation_evidence_v3/feedback_allocation_evidence.json)
uses three students, one mentor and three decisions. It deliberately fixes the
observable-record fixture to isolate the information-flow mechanism.
Both trajectories admit SYN00001 first and have identical first-transition truth.

At the next cutoff, the unchanged-record run assigns SYN00002. A new monitoring
note for untreated SYN00003 says:

> The school reports low participation in recent activities.

After validated extraction and Bayesian assimilation, SYN00003's estimated
programme benefit rises from 0.009540436888 to 0.037169581983. SYN00002 remains at
0.009540436888. The same resource planner consequently assigns SYN00003 in month 2.
No note changes the already executed action or its hidden transition. Both runs'
complete notes, estimates, risks, snapshots, allocations and evaluator-only
trajectories are saved alongside the demonstration JSON.

Reproduce this mechanism check with:

```bash
.venv/bin/python scripts/verify_cmdp_feedback.py --output results/cmdp_llm_feedback_v1/my_feedback_evidence
```

## 100-student, 12-month fixture comparison

Each run uses two mentors, one admission/five appointments per mentor per month,
150 budget units and the existing four-month fairness target of 0.2. Every run
made 24 unique programme admissions, spent 120 units, respected all hard resource
constraints and had zero quarantined fixture extractions.

| Information mode | Resource planner: terminal enrolled | Fairness planner: terminal enrolled |
| --- | ---: | ---: |
| Oracle | 72 | 72 |
| Full structured observations B | 74 | 71 |
| Note-content matched B | 72 | 71 |
| Extracted notes C, fixture adapter | 72 | 71 |
| Noisy/missing notes D, fixture adapter | 72 | 73 |

These are wiring controls, not real-model inference results. Matching B and C here
is expected from exact extraction of the declared grammar. See
[integration_fixture_v3](../results/cmdp_llm_feedback_v1/integration_fixture_v3),
[the CSV](../results/cmdp_llm_feedback_v1/integration_fixture_v3/episode_results.csv),
and [the configuration](../results/cmdp_llm_feedback_v1/integration_fixture_v3/experiment_config.json).
The extra initial/final observations explain why note and extraction counts can
exceed the twelve decisions. Delayed notes beyond the final cutoff remain unavailable.

## 100-student, 12-month real-Qwen comparison

The real-model run uses the same scenario, with one generated note per period
for B-matched/C/D. Full structured mode continues to receive all emitted records.
Each note-based episode has thirteen notes, including initial and terminal records.

| Information mode | Resource: terminal enrolled | Fairness: terminal enrolled | Resource/fairness normalized window shortfall |
| --- | ---: | ---: | --- |
| Oracle | 72 | 72 | 3.402085 / 0.782392 |
| Full structured B | 74 | 71 | 3.682429 / 0.918061 |
| Note-content matched B | 71 | 73 | 1.750346 / 0.411423 |
| Existing Qwen extracted notes C | 71 | 73 | 1.750346 / 0.411423 |
| Existing Qwen noisy/missing notes D | 71 | 73 | 1.750346 / 0.411423 |

All ten episodes completed twelve decisions, made 24 unique admissions, spent
120/150 units, and respected budget, capacity, compatibility and history checks.
All available real-note batches passed validation; zero were quarantined in the
final run. There were twenty actual model calls: thirteen resource/C, four
resource/D, two fairness/C and one fairness/D. Other identical note requests used
the content/context cache. The raw outputs and cache keys are retained per episode.

An exact fact-level comparison against note-supported grammar facts found 15/15
supported facts in each C episode and 19/19 in each D episode: 68/68 across both
planners, with no omitted supported facts in this sample. This is restricted to
the declared synthetic grammar. Per-episode counts are saved in each
`extraction_quality.json`, for example
[resource/C quality](../results/cmdp_llm_feedback_v1/integration_ollama_v3/resource_llm_notes_seed_42/extraction_quality.json).

The installed model was `qwen3.5:latest` (Qwen 3.5, 9.7B, Q4_K_M), with model digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`,
temperature zero and an 8,192-token context. See
[integration_ollama_v3](../results/cmdp_llm_feedback_v1/integration_ollama_v3),
[the comparison](../results/cmdp_llm_feedback_v1/integration_ollama_v3/episode_results.csv),
[runtime metadata](../results/cmdp_llm_feedback_v1/integration_ollama_v3/experiment_config.json),
[resource/C extraction attempts](../results/cmdp_llm_feedback_v1/integration_ollama_v3/resource_llm_notes_seed_42/extraction_attempts.jsonl),
and [fairness/C extraction attempts](../results/cmdp_llm_feedback_v1/integration_ollama_v3/fairness_llm_notes_seed_42/extraction_attempts.jsonl).

The shortfall is the sum of each cell's end-window uncovered requirement divided
by its frozen denominator, across windows. It is not a probability and need not
be below one. The existing shortfall-aware fairness planner keeps resource
constraints hard; lack of enough slots can leave a positive fairness shortfall.
Different information modes can freeze different observed need strata, so these
values do not establish a causal or statistical fairness improvement.

The C/D agreement in this sparse single-seed run is not evidence that missing/noisy
information has no effect. Full-observation fixture controls, the paired mechanism
test and future Step 6 experiments have different purposes. Oracle realized
enrollment can also be below an ordinary mode on one seed: the planner optimizes
expected benefit, not future random outcomes.

## Exact saved-extraction replay

The resource/C real-model episode was replayed without calling Ollama. All twelve
decision snapshots (including beliefs and risks), admissions, budget balances and
evaluator truth trajectories matched exactly, with 71 students terminal enrolled.
See [the replay verification](../results/cmdp_llm_feedback_v1/replay_real_resource_v3/replay_result.json).
The fairness/C replay also matched all twelve snapshots, allocations, resources
and truth trajectories exactly, with 73 terminal enrolled and zero model calls;
see [its verification](../results/cmdp_llm_feedback_v1/replay_real_fairness_v3/replay_result.json).
The same replay mechanism is also exercised in the tests.

```bash
.venv/bin/python scripts/replay_cmdp_feedback.py --source results/cmdp_llm_feedback_v1/integration_ollama_v3/resource_llm_notes_seed_42 --output results/cmdp_llm_feedback_v1/my_resource_replay
.venv/bin/python scripts/replay_cmdp_feedback.py --source results/cmdp_llm_feedback_v1/integration_ollama_v3/fairness_llm_notes_seed_42 --output results/cmdp_llm_feedback_v1/my_fairness_replay
```

## Acceptance and remaining limits

Step 5's observation, note, extraction, estimator, risk, planner, fairness,
one-programme, closed-loop, information-mode, pilot, full-scenario, isolation and
replay interfaces have been implemented and exercised. Real LLM inference was
executed successfully rather than inferred from fixture tests. All prior Step 1–4
regressions pass.

The explicit V1 limits remain: finite synthetic note grammar; null numeric values;
synthetic uncalibrated likelihoods; exact administrative enrollment; fixed source
grades/attendance and support needs; one programme per student; and sparse
real-model extraction. General human-note extraction, full-cohort monthly real-LLM
evaluation, empirical calibration and statistical conclusions have not been
validated. They are not reported as completed acceptance evidence here. No
remaining Step 5 code blocker is known within the declared V1 scope. Step 6 is
intentionally unimplemented.

# Implementation review — 8 November 2026

Reviewed revision: `7eb519d18ef0e1fe6be0ab2dc2c7b89d5cd05317`. Application code was left unchanged. This review added only this report and offline reproduction artifacts.

The project implements a working synthetic allocation benchmark, but it only partially delivers the broader research workflow. The most consequential current problem is that LLM extraction no longer supplies information about students who can receive a future allocation. A second, independently reproduced defect gives the robust planner incorrect evidence-freshness information.

**Validation:** the existing offline suite passed all **231 tests in 57.939 seconds**. Targeted probes then reproduced the problems below. Those probes use controlled offline extractors; they are not new live-model accuracy results. The interpreter was Python **3.14.8**, outside the declared Python 3.12–3.13 support range. No supported-version certification or new held-out research execution was performed.

The machine-readable results are in [evidence.json](/Users/shuniy/Documents/projects/school-dropout/outputs/implementation_review_2026-11-08/evidence.json). Reproduce them from the project root with:

```sh
.venv/bin/python outputs/implementation_review_2026-11-08/reproduce_findings.py
```

## What “the plan” means here

The repository has several generations of plans. The [original implementation brief](/Users/shuniy/Documents/projects/school-dropout/docs/CODEX_IMPLEMENTATION_PROMPT_v2.md:86) describes a richer system with uptake, delayed delivery, mutable numeric state, commitments, population resampling and further support decisions. The [CMDP specification](/Users/shuniy/Documents/projects/school-dropout/docs/cmdp-design.md:13) explicitly narrows the first simulator to categorical monthly dynamics, five appointments completed in one admission month, fixed needs and one programme per student. The [Step 5 contract](/Users/shuniy/Documents/projects/school-dropout/docs/cmdp_llm_feedback_v1.md:220) and [research protocol](/Users/shuniy/Documents/projects/school-dropout/docs/research_evaluation_protocol.md:8) describe feedback and evaluation on top of that narrower world.

Findings below distinguish incorrect behavior from intentional simplifications. An omitted future feature is not automatically an implementation bug. Recent changes also create contradictions between the narrowed plans: programme-only LLM calls satisfy the call-reduction description, but remove the allocation effect the language-feedback experiment is intended to measure.

## Findings requiring correction

### F1 — High: programme-only LLM extraction cannot affect future allocations

**Location:** [extractor routing](/Users/shuniy/Documents/projects/school-dropout/src/school/closed_loop_controller.py:92), [eligibility](/Users/shuniy/Documents/projects/school-dropout/src/school/student_observation.py:24).

Every monitoring note uses deterministic grammar extraction. The injected LLM extractor receives only programme notes, which are produced after admission. Admission permanently makes the student ineligible for another programme. The current planners value individual candidates; they do not use treated students' extracted outcomes to learn shared treatment effects, change other students' eligibility, or revise resource commitments. Consequently, the LLM can change a treated student's recorded belief and displayed risk, but has no modeled route to change later support decisions.

**Reproduction:** ran the resource, fairness and robust-fairness planners with seeds 0, 1 and 42. For each policy/seed, compared a correct extractor, a schema-valid extractor returning no facts, and an extractor that always fails. Across all **nine policy/seed comparisons**, assignments including mentor identity and entire truth trajectories were identical. Some cutoff beliefs differed, and failures were recorded, confirming that the probe exercised extraction rather than accidentally bypassing the channel.

**Impact:** a current C-versus-matched-control allocation or retention comparison cannot measure the effect of programme-note extraction errors. Observation-driven replanning still works for untreated students through deterministic monitoring; the narrower defect concerns the LLM's contribution. Noisy monitoring can also still affect allocation, so this finding does not imply that all information modes are equivalent.

**Required decision/change:** align the experiment with the action model. To study extraction effects on allocation, provide bounded pre-admission note extraction for actionable students, or explicitly model an authorized decision that programme evidence can change. If programme-only extraction is retained, describe its role as post-programme tracking and narrow the research claims accordingly. Add a test where changing only extractor output changes an eligible candidate's next allocation under fixed exogenous draws.

### F2 — High: rejected or uninformative evidence incorrectly reduces robust uncertainty

**Location:** [evidence rejection](/Users/shuniy/Documents/projects/school-dropout/src/school/state_estimator.py:103), [freshness calculation](/Users/shuniy/Documents/projects/school-dropout/src/school/state_estimator.py:121), [uncertainty construction](/Users/shuniy/Documents/projects/school-dropout/src/school/uncertainty_scenarios.py:80).

The filter correctly rejects conflicting condition evidence. Afterwards it calculates `last_observation_month` over every stored fact, including rejected and insufficient evidence. It also determines `missing_current_signal` from the presence of a recognized phrase, even when that phrase belongs to a quarantined conflicting event. The robust planner trusts those two fields to choose a documentation subset and perturbation radius.

**Reproduction:** start with valid condition evidence at source month 0. At cutoff 2, compare no new usable condition evidence with a conflicting source-month-1 report. The posterior is identical in both cases, but the conflicting report changes the metadata from missing/stale to `fresh_documented`, and reduces the radius from **0.50 to 0.25**. A source-month-1 “insufficient evidence” report also leaves the posterior unchanged but resets age and reduces the radius to **0.375**.

**Impact:** the uncertainty-aware policy can become less conservative when the latest reports are unusable. This directly affects the declared missingness/age-based uncertainty set, not merely a display label. The earlier November 6 audit identified the same cross-module defect; it remains present.

**Correction:** derive condition freshness and current-signal availability from successfully assimilated condition events. Preserve receipt dates, workflow facts and unresolved reports separately. Test conflict, insufficient evidence, zero-likelihood rejection, delayed evidence and completion-only facts through the estimator-to-scenario boundary.

### F3 — Medium: the extraction snapshot comparison runs before any LLM extraction

**Location:** [live snapshot comparison](/Users/shuniy/Documents/projects/school-dropout/src/evaluation/research_experiments.py:362).

The comparison always initializes fresh controllers and scores cutoff 1. At that point there are only monitoring notes. F1 routes every such note through the deterministic extractor in both the gold and nominal LLM modes.

**Reproduction:** injected an extractor that would fail every call. The function made **zero extractor calls**, yet exported **24 comparison rows** for a 12-student probe, all with zero belief differences and equal mentor assignments.

**Impact:** an agreement table from this function is not evidence that LLM extraction preserves beliefs, risks, rankings or assignments. This is a separate evaluation omission caused by the routing change in F1.

**Correction:** require actual accepted or failed extraction attempts in the compared history, record their count, and evaluate a shared snapshot with actionable decisions. An empty extraction contrast should be labeled unavailable. Resolve F1 before interpreting the resulting allocation comparison.

### F4 — Medium: the feedback controller does not support the five baseline policies

**Location:** [controller construction](/Users/shuniy/Documents/projects/school-dropout/src/school/closed_loop_controller.py:42), [per-decision benefit logging](/Users/shuniy/Documents/projects/school-dropout/src/school/closed_loop_controller.py:150), [default comparison](/Users/shuniy/Documents/projects/school-dropout/src/school/simulation_comparison.py:81).

The public feedback method accepts an allocation policy, but the controller assumes that it exposes `wait_matrix` and `programme_matrix`. `BaselinePolicy` exposes neither. Even supplying an estimator separately would leave the same dependency in benefit logging.

**Reproduction:** WAIT, random, severity, need-priority and longest-waiting each fail at construction with `AttributeError: 'BaselinePolicy' object has no attribute 'wait_matrix'`.

The default comparison works around this by running baselines in the fully observed runner and feedback planners separately. Its caveat discloses this information difference, but the implementation still lacks the matched baseline integration called for by the broader plan. In particular, severity uses exact conditions while ordinary planners use estimates; that contrast combines policy and information effects. WAIT and random do not themselves rank on latent condition, so their information sensitivity should not be overstated.

**Correction:** give the controller explicit model/estimator dependencies independent of the policy interface. Run the baseline subset and planners in the same information condition, with identical resources, cohort and seed sets. Keep separately labeled oracle comparisons.

### F5 — Medium: saved episode replay ignores important saved configuration

**Location:** [saved configuration](/Users/shuniy/Documents/projects/school-dropout/src/school/feedback_experiments.py:66), [replay reconstruction](/Users/shuniy/Documents/projects/school-dropout/src/school/feedback_replay.py:31).

Episode export saves student-specific note quality, estimator assumptions and policy settings. Replay restores only part of this configuration. It drops `note_quality_by_student`, regenerates the note stream, and reconstructs the policy from the scenario rather than its actual saved settings. Every policy class other than exactly `FairnessPlanner` is silently treated as a resource planner. The saved custom estimator configuration is also not passed back into the controller.

**Reproduction:** exported a valid 12-student episode with explicit per-student omission settings. The manifest contains all 12 settings. Replaying it fails with **`replay allocation/resource mismatch`**, because replay regenerates a different information channel.

**Impact:** the advertised exact-replay behavior holds only for a restricted subset of configurations. Group-dependent information-quality experiments are especially affected. The probe establishes the group-quality failure; the additional reconstruction omissions above follow from inspection of the same function.

**Correction:** reconstruct the complete recorded configuration and supported policy type, or reject unsupported configurations explicitly before execution. Prefer replaying the saved authorized event/note stream when evaluating saved extraction. Validate the full replay before exposing a completed output.

### F6 — Medium: the research policy factory ignores `fairness_enabled`

**Location:** [research policy factory](/Users/shuniy/Documents/projects/school-dropout/src/evaluation/research_experiments.py:126).

`ScenarioConfig` accepts `fairness_enabled`, and the ordinary policy factory forwards it. The research factory omits `enabled` when constructing both fair planners, so their constructor default remains true.

**Reproduction:** set `scenario.fairness_enabled = false`. Both `FairPoint.enabled` and `FairRobust.enabled` are still **true**.

**Impact:** an accepted research configuration can claim fairness is disabled while executing fairness constraints. The dedicated `ResourceOnlyPoint` ablation is a separate path and does not repair this ignored flag.

**Correction:** forward the flag consistently or explicitly reject it for named policies whose identity requires fairness. Verify that configuration and actual planner settings agree.

### F7 — Medium: the zero-budget validation rejects legitimate free programmes

**Location:** [null-world validation](/Users/shuniy/Documents/projects/school-dropout/src/school/cmdp_experiments.py:195).

The configuration permits zero appointment prices, and the allocator correctly permits an affordable free programme. The experiment runner nevertheless assumes that every zero-budget scenario must have the same trajectory under all policies, regardless of programme price.

**Reproduction:** 12 students, three months, zero budget, zero appointment price, alpha 1. The random policy delivers 12 programmes at zero expenditure and legitimately changes the trajectory relative to WAIT. The development runner rejects this valid run with **`zero-effect/zero-budget matched trajectories differ`**.

**Correction:** require trajectory equality for zero treatment effect. Use a zero-budget equality control only when the available resource/pricing configuration actually prevents all effective programmes.

## Reproducibility and plan conflicts

**Amendments overwrite the supposed immutable freeze.** The [research protocol](/Users/shuniy/Documents/projects/school-dropout/docs/research_evaluation_protocol.md:3) requires appending amendments while retaining the original manifest. [The implementation](/Users/shuniy/Documents/projects/school-dropout/src/evaluation/research_experiments.py:75) overwrites `configuration_manifest.json`, `protocol.json` and the frozen protocol copy. An isolated temporary-directory probe, with a held-out execution marker present, accepted an amendment and left one manifest containing no copy of the original input digest. The [README](/Users/shuniy/Documents/projects/school-dropout/README.md:433) now explicitly describes replacement. This is a real conflict between documented plans, rather than a hidden departure from every current document. Keep immutable per-run input records and append an amendment chain, or create a new run; reconcile the documentation. Digest guards do correctly exclude old-digest episodes from active aggregation, which limits accidental mixing but does not preserve the overwritten manifest.

**Saved research results do not certify the current implementation.** Of the 120 paths recorded by the saved Step 6 manifest, **50 now have different contents and one is absent at its former path**; 69 match. These counts are source-identity facts, not proof that every changed file affects outcomes. In particular, the programme-only extraction semantics postdate the saved evaluation. Preserve the historical results as results for their generating code, and run affected comparisons under the corrected current code before claiming current acceptance. The existing historical acceptance file also discloses nine incomplete robust solver months and sparse real-model execution.

**The new default comparison has weaker provenance than the research runner.** Its [manifest](/Users/shuniy/Documents/projects/school-dropout/src/school/simulation_comparison.py:119) records parameters and a model name, but no source/data fingerprints, installed model digest, or runtime dependency identity. The rigorous persistent extractor cache exists in the research path; the default comparison uses the lighter extractor. Removing display version labels need not remove the input identity required to reproduce a result.

**Supported-runtime validation remains outstanding.** `pyproject.toml` declares Python `>=3.12,<3.14`; the available environment and this passing test run use 3.14.8. This review confirms that mismatch, not that the implementation fails on 3.12/3.13. Establish the documented fresh-install/test gate on a declared supported interpreter.

## Implementation against the wider research plan

| Planned area | Current implementation | Assessment |
| --- | --- | --- |
| Finite-horizon simulator, keyed stochastic draws, terminal enrollment and hard resources | Implemented, with independent allocation validation and passing tests | Substantially matches the narrowed CMDP specification. Monthly/rolling optimization remains a documented heuristic. |
| School/intervention ownership, immutable request/results, recorded-session reconciliation and monthly reports | Implemented through the separate recorded-history workflow | Broadly matches the module refactor. It is a different workflow from the stochastic feedback experiment. |
| Evidence-to-belief-to-next-allocation flow | Works for untreated students via deterministic monitoring | The LLM's allocation role is absent under current routing; F1/F3 require correction or narrower claims. |
| Uncertainty-aware fairness | Finite scenarios and lexicographic fairness are implemented | Freshness metadata is incorrect in reproduced cases; F2 affects the uncertainty construction. |
| Offers, acceptance, partial/missed delivery, session schedules, cancellation and future commitments | A programme is automatically five completed appointments in its admission month | Explicit later-spec simplification; the broader intervention model remains unimplemented. Counted admissions/completions do not validate uptake or delivery behavior. |
| Mutable attendance, grades, engagement, barriers and support reassessment | Only categorical condition evolves; support need and original numeric inputs remain fixed | Matches v1, falls short of the richer original plan. A new note cannot reroute an untreated student to a newly identified support type. |
| Follow-up, additional support, switching and re-entry | One programme for life of episode; withdrawal is absorbing | Explicitly deferred. Post-treatment deterioration has no new support action. |
| Diverse mentoring effects and structural sensitivities | Support types share one effect matrix; generated mentors are generalists; alpha sweeps interpolate zero to positive effects | Adequate for studying scarce admission under assumed dynamics; insufficient for comparing intervention types, mentor effectiveness, harmful/delayed effects, or broad structural robustness. |
| Dynamic dropout-risk prediction | Analytical terminal non-enrollment under the declared WAIT model | A clearly named model-based alternative, not the original fitted short-horizon predictor. It should not be described as an empirically trained dropout model. |
| Population/source generalization | Fixed enrolled prefix across world seeds | Seeds replicate stochastic mechanisms on one cohort; they do not test new schools or source-disjoint populations. This is disclosed in the narrower protocol. |
| Independent extraction evaluation | Small controlled-grammar benchmark with shared canonical phrases and no human annotation | Useful for integration and exact semantic checks; the planned held-out language/style/generator evaluation remains missing. The current protocol acknowledges that limit. |
| Real-LLM effectiveness/equity evidence | Saved real closed-loop work is sparse and uses one world seed; primary robust-versus-point experiment uses exact note-supported facts | Does not complete the broader multi-seed language-error research question. Current routing further limits what a new real-LLM run could establish. |
| RAG, adaptation and dashboard | Recorded-history RAG exists; evidence retrieval/adaptation/dashboard are deferred | Appropriate deferral under the plan's gates; adding them would not resolve the demonstrated correctness problems. |

## Recommended correction order

1. Resolve the LLM/actionability contradiction, and replace the empty snapshot contrast with a comparison that actually exercises extraction.
2. Fix freshness from usable condition evidence and rerun the uncertainty-aware comparisons affected by it.
3. Make baseline policies usable in the shared feedback controller and compare information-matched policy cells.
4. Restore complete replay configuration, honor fairness settings, and correct the free-programme control.
5. Preserve immutable experiment inputs, record complete default-run provenance, and establish tests on a supported Python version.
6. Re-execute the affected evaluation under the corrected implementation. Extend delivery realism, population variation and language evaluation only as required by the selected research scope.

The offline suite should retain its existing guarantees while adding cross-module acceptance checks for these failures. Passing tests currently establish many useful contracts, but they do not establish that the LLM changes an actionable decision, that robust uncertainty reflects usable evidence, or that all saved configurations replay.

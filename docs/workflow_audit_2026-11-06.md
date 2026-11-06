# End-to-end school dropout workflow audit

Audit date: 6 November 2026. Audited Git revision: `7187bd9910dd381d1bd36c6e724573bbaa4e9b35`.

This is an audit, not an implementation change. No application code, tests, configurations, datasets, or existing results were edited. The checkout was clean before and after execution checks. This report is the only added deliverable.

Evidence labels: **verified** means inspected in the active source or reproduced during this audit; **saved evidence** means inspected existing experiment artifacts; **unverified** means an empirical property or a proposed downstream effect that was not established. Source links identify the exact file and starting line at the audited revision.

## A. Overall assessment

**Partial implementation of the requested workflow, with a genuine working closed loop in the newer CMDP feedback path.** It would be incorrect to conclude that observations never affect later allocations. That link exists and was reproduced. It would also be incorrect to describe the repository as a complete, realistic simulation of distinct mentoring interventions or a validated dropout-prevention system.

There are three separate execution paths:

1. The default CLI runs a fully observed synthetic policy benchmark. It does not use mentor-note feedback.
2. The newer feedback/research runners execute transitions → observable events → notes → extraction → categorical belief updates → risk recalculation → subsequent allocation. Fairness-aware point and robust planners work through this path.
3. The older recorded-intervention APIs analyze prewritten histories with SimpleLLM/RAG and update reported outcomes. They do not generate stochastic withdrawal or the newer CMDP's evolving state.

The most important verified implementation defect is **incorrect observation-freshness metadata feeding the robust planner**. Contradictory evidence can be rejected by the Bayesian filter while being classified as fresh documentation; an “insufficient evidence” note also resets observation age. The current tests do not catch this connection.

Major scope gaps are automatic full completion of every programme, identical effects across support types and mentors, static support routing, no repeat support, no delayed delivery or re-entry, and no usual-support/random/risk-ranked comparator in the newer closed-loop research runner. Most are explicitly disclosed simplifications, not concealed runtime failures.

**No P0 failure was established in the tested closed-loop execution.** No evidence was found that active ordinary planners use future outcomes or that LLM outputs overwrite true state. Numerical transition validity and resource checks passed. Empirical calibration, generalization to real notes, and real-world causal effectiveness remain unverified.

## B. Workflow compliance matrix

| Stage | Status | Executed code and data flow | Problems | Required changes |
| --- | --- | --- | --- | --- |
| Environment and baseline | Partial | CSV → fixed enrolled prefix → student/mentor copies → initial categorical state. [Population construction:12](../src/school/cmdp_scenarios.py#L12), [loading:55](../src/school/loading.py#L55), [initial state:25](../src/school/cmdp_environment.py#L25). WAIT baseline exists in the default benchmark: [baselines:11](../src/school/baseline_policy.py#L11). | Seeds do not sample new populations; default mentors are identical generalists. The feedback runner lacks a compatible WAIT/random baseline. Initial attendance/engagement are assumptions. | Add matched baselines to the same feedback runner; retain explicit provenance and fixed-cohort interpretation. |
| CMDP allocation | Partial | Immutable snapshot → feasible pairs → nominal/robust rolling MILP → independently checked admissions. [Planner:92](../src/school/constrained_planner.py#L92), [fairness:76](../src/school/fairness_planner.py#L76), [robust objective:109](../src/school/robust_fair_planner.py#L109), [validator:42](../src/school/constraints.py#L42). | This is approximate constrained planning, not a globally optimal CMDP/POMDP solution. Needs are fixed; no duration/hour commitments. Robust uncertainty metadata is incorrect in reproduced cases. | Correct metadata first; preserve heuristic labels and add only the action/resource detail needed by the research question. |
| Intervention execution | Partial | An assignment immediately charges five appointments and selects the treatment matrix for that month's transition. [Assignment contract:57](../src/school/constraints.py#L57), [execution:234](../src/school/cmdp_environment.py#L234). | No offer, refusal, partial delivery, completion draw, cancellation, delivery delay, or mentor-specific response. All support types share one effect matrix. | Introduce explicit uptake/delivery states if those claims remain in scope; let delivered dose determine effects and charges. |
| Student transitions | Partial | All cohort students receive a keyed stochastic transition; withdrawal is absorbing. [Matrices and validation:9](../src/school/transition_model.py#L9), [sampling:252](../src/school/cmdp_environment.py#L252). | Valid categorical dynamics, but no evolving attendance/grades/barriers, re-entry, seasonality, shared shocks, or calibrated hazards. Default effect sweep excludes adverse effects. | Validate horizon-level usual-support outcomes; add declared structural/effect sensitivity before interpreting policy rankings broadly. |
| Feedback and risk | Partial; uncertainty metadata Incorrect | Authorized events → dated notes → validated facts → source-time Bayesian replay → separate analytical risk. [Controller:66](../src/school/closed_loop_controller.py#L66), [extraction:123](../src/intervention/observation_extractor.py#L123), [filter:64](../src/school/state_estimator.py#L64), [risk:29](../src/school/simulated_withdrawal_risk.py#L29). | Only four qualitative signal likelihoods update condition beliefs. Conflicts/missing evidence can report false freshness. Exact phrase extraction does not validate unrestricted mentor prose. | Base freshness on usable condition evidence; separately preserve unresolved/workflow facts. Evaluate independent notes before broad LLM claims. |
| Sequential reallocation | Implemented within the one-programme model | Each month processes available evidence, rebuilds risk/snapshot/resources, replans, executes, and generates next observations. [Cycle:129](../src/school/closed_loop_controller.py#L129). | Once treated, a student is permanently ineligible even if later evidence shows deterioration. Support type never changes. | Clarify one-shot admission scope; add explicit repeat eligibility or revised needs only if required. |
| Evaluation | Partial | Retention, withdrawal, costs, utilization, waiting, frozen-cell access, solver failures, belief/risk diagnostics, paired seeds and Student-t intervals exist. [Scorecards:223](../src/evaluation/scorecards.py#L223), [paired statistics:55](../src/evaluation/paired_statistics.py#L55). | No complete baseline comparison in the feedback experiment; genuine LLM runs are sparse and use one world seed. Existing run hashes differ from current source. No type-specific effect evaluation or empirical calibration. | Version/rerun affected results, add matched baselines, and separate implementation checks from empirical validation. |

“Implemented” in the sequential row describes actual execution, not fulfillment of the richer intervention model. No stage is credited solely from a class name.

## C. Actual execution flow

### Default command

```text
src.main
  → run_experiments
  → fixed enrolled cohort + generalist mentors
  → CMDPSimulation
      → observe exact current condition (oracle benchmark)
      → baseline or explicitly selected optimizer
      → independently validate assignments
      → charge five appointments + sample condition transitions
      → monthly records → repeat → comparison exports
```

References: [CLI:13](../src/main.py#L13), [experiment loop:189](../src/school/cmdp_experiments.py#L189), [simulation:23](../src/school/cmdp_simulation.py#L23). WAIT, random, ordinal severity, fixed need, and longest waiting are the five defaults. Optimizers require explicit selection.

### New feedback/research path

```text
build_school → CMDPEnvironment
  → initial true condition [environment/evaluator]
  → sampled qualitative event + exact administrative enrollment record
  → dated monitoring/programme note
  → available-by-cutoff filter
  → exact fixture extraction OR actual Ollama extraction
  → evidence/semantics/identity/timestamp validation
  → categorical Bayesian replay of available evidence and past actions
  → estimated condition distribution + uncertainty metadata
  → separate WAIT-continuation endpoint risk
  → immutable decision snapshot
  → nominal-benefit / fair / robust-fair MILP
  → actual current-month assignments only
  → exact budget/capacity revalidation
  → automatic five-appointment completion
  → stochastic true-state transition
  → next events/notes → next monthly allocation
  → terminal evidence at T+1, with no extra allocation
```

References: [research controller construction:148](../src/evaluation/research_experiments.py#L148), [feedback coordinator:112](../src/school/closed_loop_controller.py#L112), [observation boundary:190](../src/school/cmdp_environment.py#L190).

This realizes the central feedback sequence. The risk service and action-benefit service are separate: allocation maximizes estimated incremental retention from the belief, rather than ranking students directly by the displayed risk.

### Older recorded-history path

```text
School.run_simulation
  → need-priority allocation
  → choose a support-matched prewritten history
  → SimpleLLM or RAG extracts reported outcomes
  → school reconciles recorded sessions/refunds
  → reported categorical outcomes and participation counters
  → numeric attendance/grades/enrollment remain unchanged
```

References: [legacy monthly loop:17](../src/school/simulation.py#L17), [history selection:43](../src/intervention/intervention.py#L43), [outcome application:35](../src/school/performance.py#L35). Its chain breaks before a simulated outcome-driven true-state transition and dynamic withdrawal risk. Those histories are not current-world observations. Keeping them separate is appropriate; attaching their conclusions to unrelated CMDP students would fabricate evidence. RAG is not used in the new loop; no QLoRA training implementation was found in the active source/runners.

### Representative student: complete executed cycle

Reproduced with 12 students, one mentor, four months, one admission/five appointment slots per month, budget 15, seed 42, FairnessPlanner target 0.2/window four, fixture extraction, and observation missing/delay probabilities set to zero. Other observation defaults remained unchanged. This is a deterministic implementation probe, not a live-LLM or effect estimate.

Student **SYN00003**:

| Step | Actual value |
| --- | --- |
| Initial true condition | Stable; never supplied as the ordinary policy's condition label. |
| Initial observation/note | “The school reports low participation in recent activities.” Event month 0, available at cutoff 1. A noisy signal can differ from true state. |
| Initial estimated distribution | Stable 0.127219; vulnerable 0.295858; disengaged 0.576923; withdrawn 0. |
| Initial risk | 0.278792 for terminal non-enrollment under four remaining WAIT transitions. |
| Allocation | Month 1, mentor-1, wellbeing_checkin; model-derived incremental retention benefit 0.073975. |
| Delivery and resources | Five appointments recorded completed; cost 5; budget 15 → 10. Completion is assumed by the action contract. |
| True transition | Keyed draw 0.8854071529942187; stable → stable under the treatment row `[.94, .05, .008, .002]`. |
| New observable event | Low participation, event month 1, available at cutoff 2, support_completed=true. |
| New note | “The school reports low participation in recent activities. The student completed the scheduled mentoring appointments.” |
| Extracted information | Participation=low, assertion=reported; mentoring workflow=completed. Evidence spans and timestamps validated; no numeric attendance invented. |
| Updated estimated distribution | Stable 0.112407; vulnerable 0.339848; disengaged 0.547745; withdrawn 0. |
| Revised risk | 0.225010 with three remaining WAIT transitions. This drop combines the model, information and shorter horizon; it is not measured mentoring success. |
| Next allocation | Student is ineligible because a programme was already used. Month 2 serves SYN00008; month 3 serves SYN00001; month 4 serves nobody after budget exhaustion. |

The true state remaining stable does not imply no transition was processed. The draw selects the stable cell. For the same starting state and draw, the WAIT row would select vulnerable; this is a synthetic common-random-number comparison, not real causal evidence.

The one-programme constraint limits feedback for treated students: updated beliefs are retained and scored, but cannot trigger a second programme. For untreated students, the next allocation really responds to evidence. I executed the existing [controlled feedback demonstration:35](../tests/test_feedback_closed_loop.py#L35): both runs admitted SYN00001 in month 1 and had identical first-month truth; changing the third student's monitoring observation changed month-2 admission from SYN00002 to SYN00003.

## D. Research and mathematical correctness

### State, action, transition and objective

The simulator's dynamic state is four categorical conditions per student, programme history, remaining budget, and time. Source demographics, initial measurements, support needs and mentor calendars are fixed inputs. Augmenting with programme history/time/resources makes the stated one-shot finite-horizon world Markov. Partial-information controllers maintain beliefs and histories; they are not fully observed controllers.

An action is a feasible joint set of student–mentor admissions. Conditional on these actions, students transition independently with their row of `P_WAIT` or `P_PROGRAMME`. Keyed draws depend on seed, student, month, and event type, so extra policy calls do not shift other environmental randomness: [keyed draws:7](../src/utils/keyed_random.py#L7). There is no modeled common school shock or strategic student/mentor behavior.

The reward is terminal enrolled count with zero intermediate reward and gamma=1: [terminal reward:287](../src/school/cmdp_environment.py#L287). With `e=(1,1,1,0)`, belief `b`, and `h` remaining transitions:

```text
WAIT terminal retention = b P_wait^h e
Endpoint withdrawal risk = 1 − b P_wait^h e
Admit-now benefit = b (P_programme − P_wait) P_wait^(h−1) e
```

The benefit is “treat now, then WAIT” minus “always WAIT,” not an optimal stochastic Q-value. References: [retention values:13](../src/school/retention_value.py#L13), [belief benefit:76](../src/school/retention_value.py#L76). The rolling-window planner uses WAIT projections for future candidate values, assumes candidates can remain available for projected coverage, and executes only current assignments: [forecast:21](../src/school/window_optimization.py#L21). It can report projected feasibility and subsequently incur realized shortfall after withdrawal or replanning.

The small exact dynamic-programming comparator exists, but is limited to four students/three months and excludes partial observation and fairness: [exact reference:34](../src/school/exact_tiny_mdp.py#L34). Its presence does not certify global optimality of the larger fair policies. The code and current reports generally label this limitation correctly.

### Resource accounting and delivery semantics

Monthly admission and appointment limits, mentor compatibility, no repeated programme, and episode budget are checked independently of solver outputs. Costs use exact monetary helpers. This is sound for five appointments delivered entirely within one month.

Hours are not enforced as a meaningful resource: generated mentors have zero available hours, and compatibility requests zero hours: [mentor creation:129](../src/school/loading.py#L129), [compatibility:198](../src/school/loading.py#L198). There are no multi-month commitments to release, and admission automatically establishes completion. Source support types affect eligibility/matching labels, but not transition-effect parameters.

### Withdrawal accumulation and calibration

Monthly WAIT withdrawal hazards are 0.5%, 3%, and 15% for stable, vulnerable, and disengaged states. They are explicitly monthly assumptions; I did not find an annual probability mistakenly applied monthly. However, deterioration/recovery across months materially changes cumulative withdrawal.

I calculated the withdrawal column of `P_WAIT^12`:

| Initial condition | Twelve-month withdrawal probability |
| --- | ---: |
| Stable | 25.5841% |
| Vulnerable | 42.7279% |
| Disengaged | 61.0893% |

The default fixed cohort has 80 stable and 20 vulnerable students, giving **29.0129% expected twelve-month withdrawal without extra programmes**. This is an analytical consequence of the current matrices, not a rate estimated from school dropout data. The code cannot establish that this is plausible for the target school population. A constant-hazard calculation such as `1−(1−.005)^12` would be inappropriate because condition changes.

Withdrawal is absorbing and initial non-enrollment is excluded, so terminal withdrawal and cumulative first withdrawal coincide for the included cohort. Re-entry is absent. This equality must be reconsidered if re-entry is added.

### Effect model and risk interpretation

All support types and mentors use the same treatment matrix. Effects differ by current categorical condition, and realized outcomes are stochastic, but there is no context- or support-specific response model. The configured interpolation restricts alpha to `[0,1]`: [effect strength:47](../src/school/transition_model.py#L47). Those rows improve ordered-state transition distributions relative to WAIT; the configured sweep cannot test a systematically harmful programme. Custom matrices are accepted by the lower-level environment/planner APIs, so adverse tests are possible without a wholesale rewrite.

The risk estimator is independent of the LLM, but uses the controller's assumed WAIT matrix. It is an analytical simulator-model forecast, not a fitted school-dropout predictor. The experiments normally give the environment, estimator, and planner matching transition assumptions: [controller construction:43](../src/school/closed_loop_controller.py#L43), [research policy:126](../src/evaluation/research_experiments.py#L126). This is a useful controlled experiment, but does not establish robustness to unknown treatment effects or misspecified dynamics.

The risk evaluation correctly uses an evaluator-owned WAIT reference instead of treated realized outcomes: [risk score:46](../src/evaluation/scorecards.py#L46). Its expected Brier/log loss is a model-based diagnostic; it is not empirical dropout calibration. No active code path was found relabeling course failure as simulated withdrawal. Initial grade-derived need, predicted endpoint risk, and realized simulated withdrawal remain different quantities.

### Fairness meaning

The main fairness constraint is minimum unique programme access in frozen group × condition cells, using one selected audit axis. Required coverage is `ceil(q N_g)`; shortfall is normalized by cell size. In soft mode, the lexicographic objective first minimizes summed normalized shortfall, then maximizes retention benefit, then minimizes cost, then resolves ties deterministically: [coverage:23](../src/school/fairness_audit.py#L23), [MILP:129](../src/school/fairness_planner.py#L129).

Consequences that must remain explicit:

- This is minimum coverage, not equal access rates, equal outcomes, or need-proportional allocation.
- Enrolled, untreated students with announced compatible slots define the denominator; lack of budget does not remove them. Students without compatible support are excluded and counted separately.
- Estimated need uses MAP probability at least 0.6; other cases enter an uncertain stratum: [cohorts:45](../src/school/fairness_audit.py#L45). Small changes can move students across this threshold.
- Membership freezes within a window, but later windows and different information trajectories can contain different people. Comparing like-named cells is not automatically a fixed-population comparison. Existing exports preserve memberships, which is a useful safeguard.
- Coverage may deliberately spend on zero-benefit or harmful actions if fairness has higher priority. My alpha=0 probe found equal truth trajectories despite fair planners spending 10 and the resource-only planner spending zero. That is the stated access objective, not artificial retention improvement.
- The exported `unique_offers` field is an alias of admissions, and completion rate equals admission rate: [audit fields:114](../src/school/fairness_audit.py#L114). Uptake fairness is not measured.

The robust planner maximizes `min_k sum_j benefit[j,k] x[j]`, implemented with a continuous eta variable. It does not sum student-wise minima. Its finite belief mixtures are assumed sensitivity scenarios, not calibrated confidence sets; they shift documentation subsets separately and omit simultaneous arbitrary errors: [scenario construction:54](../src/school/uncertainty_scenarios.py#L54).

### Information boundaries

The environment alone supplies current truth to the observation generator. Notes are rendered from emitted `ObservableEvent` records; ordinary snapshots use explicit enrollment records, estimates and programme histories: [operational snapshot:200](../src/school/cmdp_environment.py#L200). The enrollment registry is exact and immediately available at the next decision cutoff by assumption. That is disclosed administrative information, not evidence of latent-condition leakage.

Extraction requires a verbatim complete sentence, compatible semantics, timestamps and source offsets; numeric values must be null. Duplicate source evidence is prevented from gaining repeated likelihood weight. Delayed facts replay at source time without rewriting past actions. Invalid extraction is quarantined, with no automatic gold substitution. These are substantive implemented safeguards.

The entire likelihood-bearing vocabulary is four phrases, and the prompt includes the full phrase-to-field dictionary: [prompt:44](../src/intervention/observation_extractor.py#L44). A correct extraction of a synthetic false report does not make that report true. Extra note-channel misreporting is not included in the filter's observation-model likelihood; the noisy conditions therefore also test estimator misspecification. General performance on human-authored notes remains unverified.

### Documents versus implementation

All three requested references were located: [research plan](references/school_dropout_research_plan.md), [research brief](Research%20Project%20on%20Student%20Dropout.md), and [implementation prompt](CODEX_IMPLEMENTATION_PROMPT_v2.md). The research brief is stored with RTF-style escapes despite its Markdown extension. The implementation prompt labels itself historical at its opening; this audit treats its contents as intended design, not instructions to implement changes now.

| Design/reference | Current behavior | Assessment |
| --- | --- | --- |
| [Research plan:125](references/school_dropout_research_plan.md#L125): illustrative weekly horizon, richer latent/observed states, multiple support actions. | Twelve monthly categorical transitions by default. | Deliberate scope reduction; weekly effect/hazard values cannot be transferred unchanged. |
| [Implementation prompt:88](CODEX_IMPLEMENTATION_PROMPT_v2.md#L88): offer, uptake, delayed delivery; [line 103](CODEX_IMPLEMENTATION_PROMPT_v2.md#L103): heterogeneous/delayed/harmful worlds. | Admission means immediate full completion; standard alpha sweep is non-adverse. | Missing relative to the supplied expected workflow. |
| [Implementation prompt:224](CODEX_IMPLEMENTATION_PROMPT_v2.md#L224): proposed next-four-step first-withdrawal risk; [line 228](CODEX_IMPLEMENTATION_PROMPT_v2.md#L228): fitted predictor. | Separately named remaining-horizon endpoint risk computed analytically. | The prompt permits a separately named alternative endpoint target at line 226; the current target is not mathematically wrong, but fitted prediction is unimplemented. |
| [Implementation prompt:80](CODEX_IMPLEMENTATION_PROMPT_v2.md#L80): source-split whole-profile sampling; [line 145](CODEX_IMPLEMENTATION_PROMPT_v2.md#L145): lineage/world separation. | Same enrolled CSV prefix in every world. | Current reports correctly restrict inference to stochastic episodes of a fixed cohort; no source-population generalization test. |
| [Guidance](../Guidance.md): recorded-history school workflow and one programme per student. | Default CLI now runs an oracle CMDP; new scripts run estimated feedback. | Distinct workflows need explicit names in entrypoint documentation; legacy behavior does not describe the default CLI. |
| [Roadmap:102](roadmap.md#L102) calls LLM-driven closed-loop fairness evaluation future work, while [README:77](../README.md#L77) and newer research material describe executed integration. | Both fixture and real-extractor adapters exist; sparse saved real-LLM results exist. | Stale/ambiguous roadmap wording. It should distinguish the legacy workflow, implemented sparse integration, and deferred full-scale evaluation. |

## E. Prioritized issues

P0 means a demonstrated invalid model, broken central workflow, leakage, or misleading scientific conclusion. P1 means a major defect or missing capability. P2 means a material modeling/evaluation limitation. P3 means reproducibility/documentation maintenance.

| ID | Priority and evidence | Finding and consequence |
| --- | --- | --- |
| F1 | **P1 — verified bug** | Rejected/conflicting or uninformative evidence can look fresh to the robust planner. [Filter:106](../src/school/state_estimator.py#L106) rejects correlated conflicts, but [metadata:125](../src/school/state_estimator.py#L125) uses all facts; [scenario weighting:82](../src/school/uncertainty_scenarios.py#L82) trusts it. This changes the optimization uncertainty set. |
| F2 | **P1 — verified integration gap** | The feedback controller assumes every policy has transition matrices. `ClosedLoopCMDPController(env, BaselinePolicy('wait'))` raises `AttributeError: 'BaselinePolicy' object has no attribute 'wait_matrix'`. [Construction:44](../src/school/closed_loop_controller.py#L44). The research factory only accepts three planners: [factory:126](../src/evaluation/research_experiments.py#L126). |
| F3 | **P1 — verified scope gap** | Automatic completion and one generic effect matrix cannot answer intervention-type, uptake, dose, delay or harm questions. [Execution:247](../src/school/cmdp_environment.py#L247), [completion event:63](../src/school/observation_model.py#L63). |
| F4 | **P1 — verified provenance gap** | The existing Step 6 manifest differs from current source in 11 files, including scenario configuration, school construction, constants and baseline policy. The current manifest guard would reject this old directory. [Fingerprint:70](../src/evaluation/research_experiments.py#L70), [guard:116](../src/evaluation/research_experiments.py#L116). Saved arithmetic is reproducible, but generation under the current revision is unverified. |
| F5 | **P2 — verified model limitation** | Monthly transition rates imply about 29% twelve-month WAIT withdrawal in the default cohort. No target-population calibration or alternative structural transition family is wired into the standard sensitivity runner. [Matrices:9](../src/school/transition_model.py#L9), [sensitivity runner:311](../src/evaluation/research_experiments.py#L311). |
| F6 | **P2 — verified scope limitation** | Feedback changes condition beliefs and priority but cannot change a student's support type, need score, or eligibility after first treatment. [Fixed profiles:78](../src/school/cmdp_environment.py#L78), [eligibility:24](../src/school/student_observation.py#L24). A deteriorating treated student cannot receive further support. |
| F7 | **P2 — verified evaluation limitation** | Fixed cohort, matching dynamics assumptions, exact grammar, and one-seed sparse real-LLM diagnostics limit external validity. [Research protocol:35](research_evaluation_protocol.md#L35), [live runner:355](../src/evaluation/research_experiments.py#L355). The primary comparison uses exact note-supported extraction, not LLM outputs. |
| F8 | **P2 — verified fairness limitation** | Minimum access can be mistaken for parity; cross-trajectory need cohorts differ, and “offers” are only admissions. [Cohorts:45](../src/school/fairness_audit.py#L45), [aliases:119](../src/school/fairness_audit.py#L119). No actual refusal/uptake or delivered-dose disparity is estimated. |
| F9 | **P2 — design alignment** | Risk is analytical remaining-horizon endpoint risk, not a learned short-horizon dropout forecast. [Risk contract:10](../src/school/simulated_withdrawal_risk.py#L10). It should not be advertised as independently calibrated or interpreted as mentoring's causal effect. |
| F10 | **P3 — verified environment/docs mismatch** | The configured interpreter is Python 3.14.8, while [package metadata:9](../pyproject.toml#L9) declares `>=3.12,<3.14`; several dependencies remain unpinned. The suite ran successfully, but this does not certify a reproducible supported installation. Roadmap wording also needs reconciliation. |

F1 reproduction: a regular-participation + low-participation + explicit-conflict note kept the prior `(1/3,1/3,1/3,0)` and logged `conflicting_correlated_event`, yet returned `missing_current_signal=false`, `last_observation_month=0`, `documentation_subset=fresh_documented`, and radius **0.25**. An “insufficient evidence” note kept the same prior but set age zero and radius **0.375**. The scenario unit fixture for genuinely missing/no history expects **0.75**: [test:35](../tests/test_uncertainty_scenarios.py#L35). Thus absence of usable evidence is treated differently depending on whether a noninformative sentence was emitted. The existing conflict test checks posterior preservation, not resulting uncertainty metadata: [test:68](../tests/test_feedback_estimation.py#L68).

The exact effect of fixing F1 on the primary retention/fairness estimates is **unverified**; it requires a versioned rerun. It would be unsupported to claim that this bug explains the saved null result.

## F. Recommended corrections

These are proposals only. No fixes were applied.

| ID | Root cause and bounded correction | Validation | Changes assumptions/results? |
| --- | --- | --- | --- |
| F1 | Separate all received facts from successfully assimilated condition signals. Derive condition freshness/missingness from accepted nonconflicting likelihood updates; retain independent timestamps for workflow and unresolved evidence. Update the estimator/scenario boundary, not a reporting-only patch. | Through the real extractor→estimator→scenario chain, compare no note, insufficient evidence, completion-only, conflicting, delayed, and valid signal cases. Noninformative facts must not rejuvenate condition evidence; valid delayed evidence retains source age. | Yes: robust scenarios, allocations and results may change. Version estimator/scenario metadata and rerun primary comparison. |
| F2 | Supply transition assumptions explicitly to the coordinator/estimator and benefit diagnostics instead of requiring them on every allocation policy. Reuse existing baselines; add a risk-ranked baseline consuming the same current snapshot if required. | Run WAIT, random, risk-first, benefit-first, fair-point and robust-fair from identical cohorts, budgets, observation rules and keyed seeds. Verify WAIT delivers/spends zero and alpha=0 truth equality. | Enables missing comparisons; need not alter environment assumptions. |
| F3 | First choose whether the benchmark is explicitly generic one-month support. If the requested richer model is retained, add minimal offer/acceptance/delivery/completion records, actual dose costs, and a versioned support/need effect table with delays/adverse scenarios. Do not attach legacy narrative outcomes as effects. | Refusal gives no delivered effect; zero delivered dose cannot receive full effect; delayed delivery changes only the declared later transition; concurrent sessions/hours/commitments stay within capacity; different supported needs/actions can produce different declared kernels. | Yes: materially changes causal simulation assumptions and outcomes. |
| F4 | Preserve the old manifest/results. Identify the generating revision or source snapshot; reproduce there, or freeze a new run at the current revision with an explicit amendment. Review the 11 changed files for behavioral relevance before claiming equivalence. | All relevant hashes match the selected generating source; cached results cannot masquerade as new-revision executions; rerun/replay checks compare deterministic trajectories. | May or may not change numerical results; provenance must change. |
| F5 | Add an explicit monthly usual-support calibration/sensitivity table using endpoint probabilities and cohorts. Include low/base/high withdrawal worlds and decouple controller assumptions from true matrices. Use empirical calibration only with suitable target-domain data. | Compare Monte Carlo WAIT means to matrix-power expectations; test all horizons and probability rows; hold controller fixed while changing true dynamics; include adverse/delayed effects where modeled. | Yes when dynamics change. Calibration cannot be inferred from course failure. |
| F6 | Document the one-shot rule if intentional. Otherwise define narrowly scoped reassessment/repeat rules and dynamic observable support needs, including cooldown and cost commitments. | New evidence changes supported action eligibility where specified; treated deterioration can trigger only authorized repeat actions; no accidental duplicates or overbooking. | Yes if repeats or need updates are introduced. |
| F7 | Keep current claims bounded. Add matched multi-seed real extraction, an independently annotated varied-note set, source-cohort resampling where justified, and transition/observation misspecification tests. QLoRA/RAG should remain optional until a measured extraction/retrieval need exists. | Hold resources/estimator/policy fixed across matched information modes; distinguish extraction errors from note omission and trajectory divergence; report both source and episode uncertainty appropriately. | Broadens the evidence; no guaranteed retention improvement. |
| F8 | Continue calling the objective minimum access coverage. Remove/deprecate ambiguous offer aliases or explicitly label admission counts; retain observed-window metrics and add an evaluator-only common reference cohort for cross-mode comparisons if needed. | Hand-count ceilings, cell membership, withdrawals, incompatibility exclusions, unknown groups, and realized versus projected coverage. After uptake modeling, reconcile offered/accepted/delivered counts separately. | Metric definitions may change; version them. Never feed evaluator-only truth strata back into ordinary policies. |
| F9 | Retain the accurately named analytical endpoint risk if that is the intended benchmark. If the earlier fitted, enrolled-only four-step target remains a requirement, implement it separately with training-world labels and held-out scoring. Avoid treating shrinking-horizon risk reductions as intervention success. | Check one-hot risks against matrix powers; test terminal/currently withdrawn semantics; compare fixed-horizon forecasts when discussing risk changes. | Target changes alter predictions/evaluation, not necessarily the benefit optimizer. |
| F10 | Align tested interpreter support and environment documentation; pin the experiment environment and link reports to their generating revision. Reconcile stale workflow descriptions. | Fresh install and tests under declared supported Python; manifest captures actual versions; entrypoint smoke checks match documented modes. | Usually no research assumption change; dependency/solver changes require revalidation. |

Recommended order: **F1 metadata correction → F4 versioned provenance → F2 matched baselines**, then decide and document the intervention scope before implementing F3/F6. This preserves the existing working simulator and avoids an unnecessary rewrite.

## G. Minimum validation tests and audit evidence

### Executed in this audit

- Ran the full repository command `python -m unittest discover -s tests` through the configured virtual-environment interpreter, with bytecode disabled and a temporary Matplotlib cache. It completed with **exit code 0**. VS Code test discovery did not expose matching items, so the repository's unittest command was used. No live LLM was required.
- Ran the four-month FairnessPlanner student trace above and its independent feedback-ledger validator.
- Ran the fixed-record feedback demonstration: identical first actions/truth, different second allocation after changed evidence.
- Ran zero-effect WAIT/random/severity worlds: identical complete true-state trajectories, while spending differed appropriately.
- Ran zero-effect resource-only/fair-point/robust-fair feedback worlds: identical complete evaluator truth; resource-only spent 0, both fair planners spent 10.
- Reproduced F1 metadata errors and F2 baseline construction failure.
- Calculated exact twelve-month WAIT withdrawal probabilities from the current transition matrix.
- Recomputed the saved primary paired result from existing episode rows: FairRobust − FairPoint **−0.166667 percentage points**, paired 95% CI **[−0.427652, 0.094319]**, 30 seeds. Raw means were 0.730000 and 0.731667. This agrees with the saved report, and establishes neither superiority nor equivalence.
- Compared the saved manifest with current source fingerprints: **11 mismatches**. This is distinct from recomputing the saved numerical summary.
- Inspected saved live metadata: one world seed, model `qwen3.5:latest`, 16 new inference calls recorded for that live stage. Actual live inference was **not rerun** during this audit.

The mismatched source paths are the six files under [basic_examples](../src/basic_examples/), [scenario_config](../src/school/scenario_config.py), [constants](../src/utils/constants.py), [school](../src/school/school.py), [baseline_policy](../src/school/baseline_policy.py), and the [dialogue generator](../src/intervention/student_mentor_dialogues/tools/dialogue_banks_and_generator.py). The fingerprints alone do not establish which changes affect results.

### Required regression/acceptance matrix

| Required property | Existing evidence | Minimum additional acceptance check |
| --- | --- | --- |
| 1. Zero-effect interventions cannot create retention gains | [Reproducibility tests:36](../tests/test_cmdp_reproducibility.py#L36), [fairness null-effect test:269](../tests/test_fairness_step4.py#L269); audit probes passed. | Test exact complete trajectory equality against explicit WAIT for every closed-loop policy and information mode with effect=0, not just equal terminal means. Keep costs allowed to differ. |
| 2. Mentor/budget limits always hold | [Constraint tests:12](../tests/test_cmdp_constraints.py#L12), independent per-step validators; suite passed. | Exhaustive tiny feasible/infeasible joint actions, fractional costs, calendar gaps, and eventual multi-month commitments/partial-delivery accounting. Reject invalid actions before any budget/state mutation. |
| 3. Valid transitions/probabilities | [Transition tests:23](../tests/test_cmdp_transitions.py#L23); current rows normalized and withdrawal absorbing. | Verify custom-matrix validation, sampling frequencies and Monte Carlo horizon outcomes against exact matrix powers, including adverse/no-effect worlds. |
| 4. Outcomes/observations affect later decisions | [Feedback test:44](../tests/test_feedback_closed_loop.py#L44), audit demonstration passed. | Pair an actual transition-driven observation change with the next belief/benefit/action, while keeping unrelated randomness fixed. Explicitly test the intended behavior for previously treated students. |
| 5. No hidden/future information | [Hidden-state mutation test:80](../tests/test_feedback_closed_loop.py#L80), [fixed-action note test:93](../tests/test_feedback_closed_loop.py#L93); suite passed. | Hold authorized records fixed while changing truth/future events: serialized ordinary snapshots and actions must stay fixed. Unavailable notes cannot affect current estimates; no numeric invented fields; no LLM write to environment state. |
| 6. Fair baseline comparisons | [Initial-world check:195](../src/school/cmdp_experiments.py#L195), [seed validation:55](../src/evaluation/paired_statistics.py#L55). | Add all comparators to the feedback runner with the same observation density, cohort, model assumptions and seed sets. Reverse policy execution order and require identical traces excluding timing. |
| 7. Correct fairness definition | [Frozen-denominator tests:65](../tests/test_fairness_step4.py#L65), [infeasibility:182](../tests/test_fairness_step4.py#L182); suite passed. | Hand-count `ceil(qN)`, unique actual admissions, exclusion counts and shortfalls at deadlines; distinguish uncertain cells and compare membership identities across modes. Check offers/uptake only after those events exist. |
| 8. Reproducibility | [Repeated-seed tests:15](../tests/test_cmdp_reproducibility.py#L15), [research pilot order check:263](../src/evaluation/research_experiments.py#L263); suite passed. | Require source/config/data/dependency/model-cache identity, replay preserved extraction, and complete seed grids. A new source revision must not silently inherit old results. |
| 9. Robust uncertainty uses actual usable evidence | Existing posterior-conflict and synthetic scenario tests pass independently but miss their connection. | Add a cross-module regression for F1: conflict/insufficient/completion-only facts cannot make condition evidence current or fresh. Assert both posterior and scenario radius/subset. |

These tests verify software and declared models. They cannot prove real-world mentoring effectiveness, validate synthetic causal coefficients, or turn observational grades/failure labels into an identified dropout treatment effect.

### Final answer

**Yes, the newer repository path genuinely implements a closed-loop, fairness-aware sequential allocation benchmark. It only partially implements the full workflow requested here.** Its central observation-to-decision link works. The main problems are incorrect robust uncertainty metadata, missing matched baseline integration, simplified automatic delivery and generic treatment effects, static one-shot support eligibility, and incomplete alignment between saved results and current source. Correct the verified metadata defect and establish versioned, matched evaluation first; then extend intervention realism only to the extent required by the research question.

# Step 6 research evaluation results

## 1. Introduction

The prespecified primary estimate is **-0.167 percentage points** (FairRobust minus FairPoint), paired 95% CI [-0.428, 0.094], n=30 worlds. Raw mean retention: FairPoint 0.7317; FairRobust 0.7300. The interval includes zero; these executions do not establish a retention difference or equivalence.

This evaluation separates language extraction, state estimation, risk prediction, feasible allocation and simulated outcomes. It reuses the implemented school environment and allocation pipeline.

## 2. Research questions and hypotheses

How do incomplete, delayed, misleading and contradictory observations propagate to beliefs, risk, assignments, retention and comparable-need access? Does the finite-scenario FairRobust policy improve the effectiveness/equity trade-off relative to FairPoint? Which differences reflect missing observations, note corruption, extraction, filtering and optimization? The directional hypothesis allows robustness to help under group-dependent information errors; zero or adverse effects remain reportable findings. No empirical algorithmic novelty or real-world causal claim was prespecified.

## 3. Data and simulator

Source records are the existing [synthetic population CSV](../results/research_evaluation_v1/../../data/synthetic/populations/synthetic_student_population.csv), whose exact SHA256 is in the frozen manifest. No source record was rewritten. The initial mapping labels disengaged when assumed attendance is below 0.70 or engagement below 0.40; otherwise vulnerable when attendance is below 0.85, engagement below 0.60, or learning gap at least 0.30; remaining initially enrolled students are stable. Initially non-enrolled records are excluded. Existing source-anchor and source-split files were not used as online condition labels.

The cohort is a fixed enrolled prefix of the existing synthetic/semi-synthetic source data. Seeds change transitions and information mechanisms, not the population. Executable scenario: {"budget": 150.0, "fairness_min_access": 0.2, "fairness_window": 4, "horizon": 12, "monthly_admissions": 10, "monthly_appointments": 50, "num_mentors": 2, "num_students": 100, "planner_failure_mode": "raise", "planner_time_limit": 10.0}.

Four conditions, WAIT/programme transition matrices, intervention alpha, enrollment registry, observation likelihoods and group-dependent note quality are declared assumptions. Source course failure is not observed school dropout. All support needs share the declared programme transition matrix. No empirical causal or school-withdrawal calibration is claimed.

## 4. Allocation methods

Existing audited baseline policies are WAIT-only (no admission), random local student ordering followed by feasible greedy matching, highest ordinal condition severity, fixed initial need priority, and longest waiting time. Unsupported survivors can tie on waiting time in this closed cohort. These implementations were regression-tested; Step 6 did not add a new multi-seed comparison of all five. ResourceOnlyPoint is the existing nominal-benefit binary MILP with hard resources and no coverage target; its focused ablation isolates the declared fairness objective.

FairPoint and FairRobust share the original candidate generation, five-appointment programmes, exact episode budget, compatibility, one-programme rule, announced capacity and rolling-window fairness cohorts. Objectives are lexicographic: normalized access shortfall, nominal or worst-scenario aggregate benefit, exact cost, canonical assignment bits. Only current admissions execute.

FairRobust constrains continuous eta below each complete scenario's sum of assignment benefits. The finite set includes nominal and separate optimistic/pessimistic shifts for fresh/documented and missing/stale subsets, at most five scenarios. Mixture parameters: {"freshness_months": 3, "missingness_multiplier": 1.5, "radius": 0.25}. The set is a synthetic sensitivity assumption, not a calibrated confidence region or a guarantee that truth lies within it. Risk and treatment benefit remain distinct quantities. Both planners are rolling heuristics, not exact POMDP solvers.

## 5. Language and estimation pipeline

The existing pipeline renders authorized observable events into dated notes, validates exact evidence spans and structured assertions, then replays source-time categorical Bayes updates. Administrative enrollment remains explicit. Delayed evidence may update a current belief but does not rewrite previous decisions. Unknown, negated, conflicting and absent observations remain distinguishable; unresolved events do not become condition labels or treatment effects. The risk estimator propagates the belief under WAIT and the allocator separately computes incremental programme benefit. Unsupported or quarantined extraction supplies missing evidence and never an invented gold replacement.

The primary D-matched comparison uses exact note-supported facts from the corrupted channel, so it isolates the uncertainty/allocation study without claiming LLM extraction effects. Actual Qwen outputs are measured in the independent extraction benchmark and matched sparse C/D propagation controls. Those controls have fewer independent worlds and a different monitoring density.

## 6. Experimental design

Development seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]. Frozen primary evaluation seeds: [1000, 1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020, 1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028, 1029]. Completed episode rows: 273; primary rows: 60; sparse real-LLM rows: 8. Source/configuration hashes and package versions are in [configuration_manifest.json](../results/research_evaluation_v1/configuration_manifest.json). The frozen protocol is [available here](../results/research_evaluation_v1/research_evaluation_protocol_frozen.md).

One episode seed is one independent simulation replicate. Intervals use paired world differences with Student-t critical values and sample SD (ddof=1). Students and months are not independent replicates. Secondary contrasts are exploratory without multiplicity adjustment. These intervals quantify simulation Monte Carlo uncertainty; they do not cover source-population or causal-model uncertainty.

## 7. Results

### 7.1. Extraction benchmark

| Comparator | Execution | Micro F1 | Macro field F1 | Raw schema-valid / eligible | Failed/quarantined notes | Raw unsupported observations |
| --- | --- | --- | --- | --- | --- | --- |
| gold_reference | completed | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| exact_rule | completed | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| real_llm | completed | 0.9677 | 0.9571 | 1.0000 | 2 | 3 |

The benchmark uses newly declared synthetic note identities and compositions with independently declared semantic gold. Canonical vocabulary and phrase semantics overlap development and the prompt. It has no independent human annotation and does not establish generalization to unrestricted mentor prose. Failed/quarantined outputs remain misses; no gold substitution occurs. Full field/component TP/FP/FN and pre-validation diagnostics are in [extraction_metrics.csv](../results/research_evaluation_v1/extraction_metrics.csv), with raw inference records and model digest under [extraction/](../results/research_evaluation_v1/extraction/).

![Exact-fact extraction on the executed controlled-grammar benchmark; no population confidence interval is implied.](../results/research_evaluation_v1/figures/extraction_performance.png)

Exact-fact extraction on the executed controlled-grammar benchmark; no population confidence interval is implied.

### 7.2. Belief quality

| Policy | Primary worlds | Four-class Brier | Clipped NLL |
| --- | --- | --- | --- |
| FairPoint | 30 | 0.4400 | 0.7464 |
| FairRobust | 30 | 0.4396 | 0.7458 |

Brier scores sum errors over all four classes (range 0–2). Primary means cover decision cutoffs only; terminal diagnostics are exported separately. [belief_metrics.csv](../results/research_evaluation_v1/belief_metrics.csv) records accuracy, confusion, entropy, missingness and freshness by cutoff and authorized group. Reliability figures use individual records from the first five completed primary world seeds and are descriptive; trajectory-dependent rows are not independent trials.

![Maximum-probability confidence versus actual MAP accuracy, excluding terminal diagnostics.](../results/research_evaluation_v1/figures/belief_calibration.png)

Maximum-probability confidence versus actual MAP accuracy, excluding terminal diagnostics.

### 7.3. Risk quality

| Policy | Expected Bernoulli Brier | Expected Bernoulli log loss | Probability MSE |
| --- | --- | --- | --- |
| FairPoint | 0.1325 | 0.4124 | 0.0115 |
| FairRobust | 0.1324 | 0.4120 | 0.0115 |

The reference target is terminal withdrawal under WAIT from the evaluator's current true condition and declared reference matrix. Scores use its conditional probability, not realized treated endpoints. Fractional reference probabilities are not observed dropout labels; no empirical AUC or real-world risk validation is claimed. See [risk_metrics.csv](../results/research_evaluation_v1/risk_metrics.csv).

![Binned predicted risk versus conditional true-state WAIT reference probability in the declared five-world diagnostic sample.](../results/research_evaluation_v1/figures/risk_calibration.png)

Binned predicted risk versus conditional true-state WAIT reference probability in the declared five-world diagnostic sample.

### 7.4. Allocation propagation and information modes

[snapshot_assignment_comparison.csv](../results/research_evaluation_v1/snapshot_assignment_comparison.csv) compares fresh point/robust planners on exactly the same first-cutoff input and feasible set. [extraction_snapshot_comparison.csv](../results/research_evaluation_v1/extraction_snapshot_comparison.csv) compares matched gold/LLM notes for belief, risk, benefit, eligibility and mentor assignment changes; it is available only when that live stage ran. Rank diagnostics use average ties. Divergent closed-loop trajectories are not presented as identical later snapshots.

![Selection disagreement counts the student symmetric difference divided by cohort size; mentor overlap is exported separately.](../results/research_evaluation_v1/figures/allocation_disagreement.png)

Selection disagreement counts the student symmetric difference divided by cohort size; mentor overlap is exported separately.

![FairPoint held fixed across information modes, restricted to the same secondary seeds. Oracle is an upper-information diagnostic, not an ordinary-policy comparator.](../results/research_evaluation_v1/figures/retention_by_information_mode.png)

FairPoint held fixed across information modes, restricted to the same secondary seeds. Oracle is an upper-information diagnostic, not an ordinary-policy comparator.

| Contrast/setting | Metric | Paired worlds | Reference mean | Cell mean | Cell − reference | 95% paired CI | Difference units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| oracle | retention_rate | 5 | 0.7400 | 0.7480 | 0.8000 | [-0.8189, 2.4189] | percentage points |
| structured | retention_rate | 5 | 0.7400 | 0.7360 | -0.4000 | [-1.0801, 0.2801] | percentage points |
| b_matched | retention_rate | 5 | 0.7400 | 0.7360 | -0.4000 | [-1.0801, 0.2801] | percentage points |

### 7.5. Primary retention and fairness

The prespecified primary estimate is **-0.167 percentage points** (FairRobust minus FairPoint), paired 95% CI [-0.428, 0.094], n=30 worlds. Raw mean retention: FairPoint 0.7317; FairRobust 0.7300. The interval includes zero; these executions do not establish a retention difference or equivalence.

| Contrast/setting | Metric | Paired worlds | Reference mean | Cell mean | Cell − reference | 95% paired CI | Difference units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| primary | retention_rate | 30 | 0.7317 | 0.7300 | -0.1667 | [-0.4277, 0.0943] | percentage points |
| primary | normalized_shortfall | 30 | 3.6655 | 3.5398 | -0.1257 | [-0.3723, 0.1209] | metric units |
| primary | access_gap | 30 | 0.3758 | 0.3739 | -0.0019 | [-0.0137, 0.0098] | metric units |
| primary | worst_group_access | 30 | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| primary | waiting_disparity | 30 | 1.0072 | 1.1010 | 0.0938 | [-0.1293, 0.3168] | metric units |
| primary | spending | 30 | 150.0000 | 150.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| primary | solver_runtime_seconds | 30 | 2.1980 | 5.4411 | 3.2431 | [1.9561, 4.5300] | metric units |

Fairness outcomes must be read alongside retention. Lower normalized shortfall/access gap/waiting disparity and higher worst-cell access are preferable. An interval containing zero does not demonstrate no harm or equivalence. Access cohorts freeze within each four-month trajectory window; the same reported group/stratum label can contain different students after observations or actions diverge. Membership identities are exported, so cross-mode access differences are not silently treated as a fixed-denominator comparison. A retention increase alone does not establish a superior effectiveness/equity trade-off.

![Each line is one paired world; points show policy means. All completed primary worlds are included regardless of sign.](../results/research_evaluation_v1/figures/point_vs_robust.png)

Each line is one paired world; points show policy means. All completed primary worlds are included regardless of sign.

![World-level retention versus access shortfall, without implying that cells or students are independent replicates.](../results/research_evaluation_v1/figures/fairness_retention_tradeoff.png)

World-level retention versus access shortfall, without implying that cells or students are independent replicates.

![Descriptive group access averages nonempty frozen-cell/world rows equally; paired fairness contrasts above are the primary inferential summaries.](../results/research_evaluation_v1/figures/group_access_comparison.png)

Descriptive group access averages nonempty frozen-cell/world rows equally; paired fairness contrasts above are the primary inferential summaries.

### 7.6. Sensitivity and operational burden

| Contrast/setting | Metric | Paired worlds | Reference mean | Cell mean | Cell − reference | 95% paired CI | Difference units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| budget_150 | retention_rate | 5 | 0.7400 | 0.7440 | 0.4000 | [-0.2801, 1.0801] | percentage points |
| budget_300 | retention_rate | 5 | 0.7460 | 0.7480 | 0.2000 | [-1.4189, 1.8189] | percentage points |
| budget_50 | retention_rate | 5 | 0.7340 | 0.7340 | 0.0000 | [-0.8780, 0.8780] | percentage points |
| effect_0 | retention_rate | 5 | 0.7320 | 0.7320 | 0.0000 | [0.0000, 0.0000] | percentage points |
| effect_0.25 | retention_rate | 5 | 0.7320 | 0.7320 | 0.0000 | [0.0000, 0.0000] | percentage points |
| effect_0.5 | retention_rate | 5 | 0.7380 | 0.7380 | 0.0000 | [0.0000, 0.0000] | percentage points |
| effect_1 | retention_rate | 5 | 0.7400 | 0.7440 | 0.4000 | [-0.2801, 1.0801] | percentage points |
| missingness_0 | retention_rate | 5 | 0.7360 | 0.7380 | 0.2000 | [-0.3553, 0.7553] | percentage points |
| missingness_0.1 | retention_rate | 5 | 0.7360 | 0.7400 | 0.4000 | [-0.2801, 1.0801] | percentage points |
| missingness_0.25 | retention_rate | 5 | 0.7360 | 0.7380 | 0.2000 | [-0.3553, 0.7553] | percentage points |
| missingness_0.4 | retention_rate | 5 | 0.7380 | 0.7400 | 0.2000 | [-0.3553, 0.7553] | percentage points |
| uncertainty_0 | retention_rate | 5 | 0.7400 | 0.7400 | 0.0000 | [0.0000, 0.0000] | percentage points |
| uncertainty_0.1 | retention_rate | 5 | 0.7400 | 0.7420 | 0.2000 | [-0.3553, 0.7553] | percentage points |
| uncertainty_0.25 | retention_rate | 5 | 0.7400 | 0.7440 | 0.4000 | [-0.2801, 1.0801] | percentage points |
| uncertainty_0.5 | retention_rate | 5 | 0.7400 | 0.7360 | -0.4000 | [-1.5106, 0.7106] | percentage points |

All sensitivity fairness metrics are retained in [all_policy_comparisons.csv](../results/research_evaluation_v1/all_policy_comparisons.csv). [ablation_results.csv](../results/research_evaluation_v1/ablation_results.csv) contains zero-radius uncertainty and resource-only fairness controls. Zero treatment effect checks use exact keyed-draw truth equality, rather than a claim from an interval around zero. Missingness changes note omission in addition to the fixed observation model. Budget, effect and radius sweeps use their frozen settings and secondary seed subset.

![Paired exploratory retention differences with world-level 95% intervals; these sweeps are not multiplicity-adjusted confirmatory tests.](../results/research_evaluation_v1/figures/missingness_sensitivity.png)

Paired exploratory retention differences with world-level 95% intervals; these sweeps are not multiplicity-adjusted confirmatory tests.

| Policy | Programmes/world | Spending/world | Budget utilization | Admission capacity utilization | Appointment capacity utilization | Solver seconds/world | Incomplete stages/world | Fallbacks/world |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FairPoint | 30.0000 | 150.0000 | 1.0000 | 0.1250 | 0.1250 | 2.1980 | 0.0000 | 0.0000 |
| FairRobust | 30.0000 | 150.0000 | 1.0000 | 0.1250 | 0.1250 | 5.4411 | 0.3000 | 0.0000 |

Solver status, timings and constraint checks are retained in [solver_diagnostics.csv](../results/research_evaluation_v1/solver_diagnostics.csv); workloads and exact delivery remain in each episode trace. Runtime is descriptive and machine-dependent. Sparse C/D runs use one rotating note per month and only the frozen live seeds; they cannot replace a full-cohort multi-seed LLM evaluation.

### 7.7. Additional group and scoring audits

The raw real-model unsupported-assertion rate was 0.0882; the raw timestamp-error rate was 0.0588. Evidence-span correctness was 1.0000. Component accuracies count missing or quarantined gold facts as errors; see [the additional extraction metrics](../results/research_evaluation_v1/extraction_additional_metrics.csv).

Across 1575 audited cross-policy/mode cells, 453 had different frozen student memberships. [Denominator comparisons](../results/research_evaluation_v1/denominator_comparison.csv) report membership and size changes explicitly. [Group retention contrasts](../results/research_evaluation_v1/group_retention_comparison.csv) use paired episode seeds and are exploratory. [Live extraction by source group](../results/research_evaluation_v1/live_extraction_by_group.csv) reports sparse trajectory-note scores without treating those notes as independent worlds. [Enrolled-only belief/risk scores](../results/research_evaluation_v1/enrolled_information_metrics.csv) exclude absorbing withdrawn cases and terminal evidence. These summaries do not tune allocation parameters; [the analysis manifest](../results/research_evaluation_v1/analysis_manifest.json) records their code and inputs.

The missingness sweep uses a uniform note-omission channel with the other additional note corruptions disabled, while retaining the fixed observation model. Budget, effect and radius sweeps retain the primary group-dependent note channel. The missingness sweep is consequently a separate mechanism sensitivity rather than a direct dose-response interpretation of the combined primary channel.

Additional traced cases identify early budget exhaustion and model-based benefit underestimation of a vulnerable/disengaged student when observed. They are in [failure_cases.jsonl](../results/research_evaluation_v1/failure_cases.jsonl), with explicit operational/model comparators.

The following sparse real-LLM comparisons use one held-out world and one rotating note per month. B-matched matches C, and D-matched matches noisy C, at identical monitoring density. There is no episode-level confidence interval from one world. [Matched information contrasts](../results/research_evaluation_v1/live_information_comparison.csv) preserve that limitation.

Full trajectory replay using the configuration-complete real-output cache is recorded in [real_cached_replay.json](../results/research_evaluation_v1/real_cached_replay.json) when explicitly requested.

| Policy | Mode | Retention | Shortfall | Belief Brier | WAIT risk MSE | Spending | Failed extractions |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FairPoint | b_matched | 0.77 | 0.8641405764047274 | 0.5352218241548511 | 0.014053322301711735 | 150.0 | 0 |
| FairPoint | d_matched | 0.77 | 0.8641405764047274 | 0.534925788654929 | 0.014011197081456395 | 150.0 | 0 |
| FairPoint | llm_notes | 0.77 | 0.8641405764047274 | 0.5352218241548511 | 0.014053322301711735 | 150.0 | 0 |
| FairPoint | noisy_notes | 0.77 | 0.8641405764047274 | 0.534925788654929 | 0.014011197081456395 | 150.0 | 0 |
| FairRobust | b_matched | 0.76 | 1.9272247360482655 | 0.5286500908234518 | 0.013976647540688598 | 150.0 | 0 |
| FairRobust | d_matched | 0.76 | 1.8772247360482655 | 0.5293509668614811 | 0.014009582585776767 | 150.0 | 0 |
| FairRobust | llm_notes | 0.76 | 1.9272247360482655 | 0.5286500908234518 | 0.013976647540688598 | 150.0 | 0 |
| FairRobust | noisy_notes | 0.76 | 1.8772247360482655 | 0.5293509668614811 | 0.014009582585776767 | 150.0 | 0 |

## 8. Ablation studies

| Contrast/setting | Metric | Paired worlds | Reference mean | Cell mean | Cell − reference | 95% paired CI | Difference units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| uncertainty_0 | retention_rate | 5 | 0.7400 | 0.7400 | 0.0000 | [0.0000, 0.0000] | percentage points |
| uncertainty_0 | normalized_shortfall | 5 | 3.5792 | 3.5792 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0 | access_gap | 5 | 0.5585 | 0.5585 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0 | worst_group_access | 5 | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0 | waiting_disparity | 5 | 0.9048 | 0.9048 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0 | spending | 5 | 150.0000 | 150.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0 | solver_runtime_seconds | 5 | 2.2384 | 2.2613 | 0.0229 | [-0.0033, 0.0491] | metric units |
| uncertainty_0.1 | retention_rate | 5 | 0.7400 | 0.7420 | 0.2000 | [-0.3553, 0.7553] | percentage points |
| uncertainty_0.1 | normalized_shortfall | 5 | 3.5792 | 3.6839 | 0.1047 | [-0.7433, 0.9526] | metric units |
| uncertainty_0.1 | access_gap | 5 | 0.5585 | 0.5585 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.1 | worst_group_access | 5 | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.1 | waiting_disparity | 5 | 0.9048 | 0.9337 | 0.0289 | [-0.0197, 0.0774] | metric units |
| uncertainty_0.1 | spending | 5 | 150.0000 | 150.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.1 | solver_runtime_seconds | 5 | 2.2384 | 4.3778 | 2.1394 | [-2.1403, 6.4192] | metric units |
| uncertainty_0.25 | retention_rate | 5 | 0.7400 | 0.7440 | 0.4000 | [-0.2801, 1.0801] | percentage points |
| uncertainty_0.25 | normalized_shortfall | 5 | 3.5792 | 3.6839 | 0.1047 | [-0.7725, 0.9819] | metric units |
| uncertainty_0.25 | access_gap | 5 | 0.5585 | 0.5585 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.25 | worst_group_access | 5 | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.25 | waiting_disparity | 5 | 0.9048 | 0.9334 | 0.0286 | [-0.0201, 0.0774] | metric units |
| uncertainty_0.25 | spending | 5 | 150.0000 | 150.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.25 | solver_runtime_seconds | 5 | 2.2384 | 4.8851 | 2.6468 | [-1.3720, 6.6655] | metric units |
| uncertainty_0.5 | retention_rate | 5 | 0.7400 | 0.7360 | -0.4000 | [-1.5106, 0.7106] | percentage points |
| uncertainty_0.5 | normalized_shortfall | 5 | 3.5792 | 3.6714 | 0.0922 | [-0.6832, 0.8676] | metric units |
| uncertainty_0.5 | access_gap | 5 | 0.5585 | 0.5585 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.5 | worst_group_access | 5 | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.5 | waiting_disparity | 5 | 0.9048 | 0.9969 | 0.0921 | [-0.0317, 0.2160] | metric units |
| uncertainty_0.5 | spending | 5 | 150.0000 | 150.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| uncertainty_0.5 | solver_runtime_seconds | 5 | 2.2384 | 10.4942 | 8.2558 | [5.3025, 11.2092] | metric units |
| ResourceOnlyPoint_minus_FairPoint | retention_rate | 5 | 0.7400 | 0.7400 | 0.0000 | [-0.8780, 0.8780] | percentage points |
| ResourceOnlyPoint_minus_FairPoint | normalized_shortfall | 5 | 3.5792 | 3.8613 | 0.2821 | [-0.4321, 0.9963] | metric units |
| ResourceOnlyPoint_minus_FairPoint | access_gap | 5 | 0.5585 | 0.2504 | -0.3081 | [-0.6681, 0.0519] | metric units |
| ResourceOnlyPoint_minus_FairPoint | worst_group_access | 5 | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| ResourceOnlyPoint_minus_FairPoint | waiting_disparity | 5 | 0.9048 | 0.9316 | 0.0268 | [-0.5170, 0.5706] | metric units |
| ResourceOnlyPoint_minus_FairPoint | spending | 5 | 150.0000 | 150.0000 | 0.0000 | [0.0000, 0.0000] | metric units |
| ResourceOnlyPoint_minus_FairPoint | solver_runtime_seconds | 5 | 2.2384 | 0.1139 | -2.1245 | [-2.3691, -1.8798] | metric units |

Zero radius deliberately removes the uncertainty perturbation while retaining the same robust implementation and feasibility constraints. ResourceOnlyPoint removes the fairness objective and is compared on matched world seeds. These are exploratory controls with the frozen secondary sample. Their complete outcome metrics are retained, including unfavorable changes. Exact null-effect trajectory checks are documented in the development gate and held-out effect sweep.

## 9. Failure analysis

| Observed case | Seed | Policy | Deterministic selection rule |
| --- | --- | --- | --- |
| largest_negative_primary_robust_difference | 1028 | paired | minimum paired primary retention difference; seed breaks ties |
| largest_belief_error_in_declared_five_world_diagnostic_sample | 1003 | FairPoint | maximum summed four-class Brier in first five primary world seeds |
| note_omission | 1000 | FairPoint | first actual qualifying note in declared diagnostic sample, ordered by seed/policy |
| note_contradiction | 1000 | FairPoint | first actual qualifying note in declared diagnostic sample, ordered by seed/policy |
| fairness_shortfall | 1000 | FairPoint | first actual positive projected shortfall in declared diagnostic sample |

Full selected traces are in [failure_cases.jsonl](../results/research_evaluation_v1/failure_cases.jsonl). Each separates evaluator truth, observable events, note text, note-supported reference facts, accepted extraction, belief, risk, estimated benefit, assignment and subsequent outcome. Note-supported reference facts are reconstructed with the existing controlled-grammar adapter for explanation, not fed back to execution. Largest belief-error and note cases use the declared first-five-world diagnostic sample; adverse primary retention searches all completed primary pairs. Positive coverage slack is not a hard-resource violation. Later withdrawal is not evidence that an intervention was unnecessary.

Every declared diagnostic category had an actual qualifying trace.

## 10. Limitations

No claim here establishes observed school-dropout prediction, causal programme efficacy, fairness outcome parity or robust-policy superiority outside the declared simulator. Group information-quality differences, transition dynamics and uncertainty radii are assumptions. The fixed prefix excludes source-cohort sampling uncertainty; controlled language favors exact-rule extraction. Oracle consumes present state only, not future draws. Post-action observations belong to each policy's own trajectory. Secondary and subgroup estimates have few worlds and no multiplicity correction.

Execution Python: 3.14.8; declared support: >=3.12,<3.14. The recorded interpreter must not be described as a verified supported runtime if outside that declared range. Real inference is distinguished from deterministic cache replay; temperature zero does not guarantee bitwise model determinism. See [development_gate.json](../results/research_evaluation_v1/development_gate.json), [primary_complete.json](../results/research_evaluation_v1/primary_complete.json), [live_runtime.json](../results/research_evaluation_v1/live_runtime.json), frozen manifests, per-episode summaries and compressed traces for completed stages and remaining acceptance items. An unavailable table or plot is explicitly labeled and does not count as completed evidence.

### Execution acceptance audit

The [executed acceptance audit](../results/research_evaluation_v1/acceptance_audit.json) verifies 221 passing tests, 273 logical cells, 228 unique episodes, 5 exact held-out null-effect pairs and 4 exact real-cache replays. Unique episode execution time totaled 1184.7 seconds; 40 new real-model calls totaled 468.0 seconds. The scope gaps and qualifications are:

- Full-cohort multi-seed real-LLM C/D evaluation was not executed; real closed-loop comparisons use one world and one note per month.
- No independent human annotation or template-disjoint unrestricted-language generalization study was performed.
- Uncertainty sets and transition/observation assumptions are synthetic, not empirically calibrated.
- Several robust objective refinements remained incomplete; feasible incumbents and statuses are reported.
- The execution used Python3.14.8; declared Python3.12-3.13 support was not separately certified.
- No real-world intervention efficacy, algorithmic novelty, POMDP optimality or effectiveness-equity superiority is established.

## 11. Research contribution assessment

The implemented contribution is a reproducible, auditable evaluation of an existing language-to-belief-to-allocation system, with a small explicitly assumed robust belief-scenario extension, paired simulation inference and evaluator-only trace diagnostics. Exact-rule extraction is a substantive comparator in this controlled grammar. The evidence does not establish a new general-purpose extraction method, a learned dropout model, an optimal POMDP policy or real-world programme efficacy. Whether the robust extension is useful must be judged from its reported retention and equity estimates together, rather than its name or a favorable isolated example.

## 12. Conclusion

The prespecified primary estimate is **-0.167 percentage points** (FairRobust minus FairPoint), paired 95% CI [-0.428, 0.094], n=30 worlds. Raw mean retention: FairPoint 0.7317; FairRobust 0.7300. The interval includes zero; these executions do not establish a retention difference or equivalence.

The observed direction and uncertainty apply to the frozen synthetic setting. Extraction accuracy, state/risk diagnostics, access outcomes, operational cost and negative cases remain part of the result. A positive retention estimate alone does not establish a superior fairness trade-off, and an interval spanning zero is not equivalence.

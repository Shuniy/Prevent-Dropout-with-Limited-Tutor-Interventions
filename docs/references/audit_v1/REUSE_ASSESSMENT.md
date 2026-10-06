# Assessment of `student_cmdp_study`

6 October 2026

**Recommendation: retain the existing CSVs as a versioned population-initialization package. Repair the build process before regenerating them, then implement and validate the simulator incrementally.** The current package supports a semi-synthetic research benchmark. It does not contain measured school-dropout outcomes or evidence that mentoring prevents dropout.

The pasted research brief was used as evaluation context. This review did not execute its proposed implementation programme. All original datasets, the existing workbook, generated files and synced project references were left unchanged. This companion audit is saved separately in the ChatGPT project workspace.

## What can be reused

| Existing artifact | Decision | Conditions |
|---|---|---|
| `data/student_dataset.csv` | Retain | 674 profiles × 44 fields. Use its 649 Portuguese anchors for the primary study; the extra 25 math-only profiles are a sensitivity cohort. |
| `data/synthetic_student_population.csv` | Retain as reset fixtures | 2,000 × 51. They are bootstrap descendants, with assumed initial dynamics, not 2,000 independently observed students. Filter by split. |
| `data/split_manifest.csv` | Retain | Known linkage groups and their descendants remain within one split. This cannot establish true identity or household separation where source IDs are absent. |
| `data/student_outcomes_reference.csv` and `subject_records_reference.csv` | Retain for reference/evaluation | Keep outside the policy input path. Final grades, total absences and failure proxies cannot become reset observations. |
| `data/higher_ed_enrollment_features.csv` and `higher_ed_outcomes_reference.csv` | Retain separately | University prediction only. Do not pool or join these students with the school population. |
| `data/simulator_hidden_truth.csv` | Retain as environment diagnostics | Hidden hazards, response tendency and financial barriers are assumed/generated. Exclude the static future dropout draw from sequential episode outcomes and every policy. |
| `analysis/` and `student_analysis.xlsx` | Retain as existing analysis | Prediction readback agrees with saved metrics. Their checks do not establish simulator or allocator correctness. The workbook was structurally inspected, not recalculated or re-rendered in this review. |
| `configs/` and `experiment_plan.md` | Keep as a draft specification | Resolve the implementation gaps below before treating them as executable contracts. No sequential trials have been run. |
| `build_study.py` | Repair before rerunning | Its current location causes a missing research-plan path and recursive ingestion of its own outputs. |

Use the existing folder as the input package for future implementation. Write new simulator code and results in separate locations, with explicit source and output paths. The review does not require regenerating or moving the supplied CSVs.

## Independent evidence

The audit profiled **16 source CSVs and 28 package CSVs**. It recomputed all primary missingness and duplicate counts, checked every inherited field in all synthetic rows against its source anchor, verified split isolation, reconstructed the four sets of saved model predictions from coefficients and preprocessing, and rechecked original-file hashes. No inherited-field mismatches or linkage split crossings were found. All available entries in the original source manifest still match, including the relocated project reference resolved by its reference name.

Both supplied UCI archives were also compared with fresh official downloads and matched byte for byte. Source provenance and licence interpretation are supported by the official [Student Performance](https://archive.ics.uci.edu/dataset/320/student+performance) and [Predict Students' Dropout and Academic Success](https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success) pages. Both official datasets are CC BY 4.0. Preserve attribution and state transformations when redistributing derivatives.

| Population | Rows × fields | Outcome and descriptive prevalence | Legitimate role |
|---|---:|---|---|
| Portuguese secondary-school subject records | 649 × 33 | 100/649 = **15.41% course failure**, defined as G3 < 10 | Population grounding, contextual/academic associations, failure prediction, subgroup audits |
| Mathematics subject records | 395 × 33 | 130/395 = **32.91% course failure** | Safe enrichment and separate course prediction |
| Authentic higher education | 4,424 × 37 | 1,421 Dropout, 2,209 Graduate, 794 Enrolled; **32.12% labelled dropout across all rows** | Separate observational endpoint prediction |
| Higher-ed resolved subset | 3,630 | 1,421/3,630 = **39.15% dropout** | Supplementary binary task conditional on resolved outcome |

The higher-ed endpoint is status at the normal course duration. It does not establish permanent school dropout or withdrawal from all education. The 794 enrolled records must not be recoded as successful graduates. These proportions are descriptive sample baselines, not untreated simulator rates. The school data has **no observed dropout label**. The Portuguese cohort is aged 15–22; 181/649 are at least 18, so descriptions restricted to children need a separate age-restricted analysis.

The authentic raw tables have no blank cells or duplicate full rows. However, higher-ed parental qualification code 34 explicitly means unknown: 130 mothers and 112 fathers. Coded unknowns require semantic handling. Parent-qualification codes are categorical and cannot be equated to the school's ordinal Medu/Fedu scale.

There are no verified student/household IDs, mentor records, dated intervention histories, assigned treatment probabilities, weekly attendance windows, note corpus or survey weights in the primary data. School labels GP/MS identify only two schools. Existing support flags describe context; they do not identify causal effects.

The 13-field subject linkage produces 382 naïve merge pairs but only **358 one-to-one matches**, with eight ambiguous shared keys. The conservative package handles these appropriately. It preserves the 12 ambiguous math records in the reference table instead of selecting arbitrary matches.

The Abdullah derivative adds no independent students. Its `Dropped_Out` equals G3 < 10 for all 649 rows, and it swaps the weekday/weekend alcohol headings relative to the original Dalc/Walc definitions. Use the authentic files and their codebook. The processed X/y files and duplicate subject copies likewise add no independent observations.

Keep the all-level bundle outside the primary analysis. Its six files lack sufficient collection documentation. Findings include an exactly reconstructed eight-value probability rule in 25,000 school rows, 5,030 grade-13 rows, 12,607 earned-credit counts exceeding attempted credits in the Spanish table, and a master's file mixing two schemas with 110,225 blank cells. These are audit flags, not proof of any specific generation process. The district table contains aggregate cells without a district identifier. The similarly sized 4,424-row university table has different outcomes and no complete matches on the common original columns; its name and size do not authenticate it.

## Synthetic-data validation

Comparisons used each generated split's corresponding Portuguese source split. For selected features, the largest absolute standardized mean differences were 0.059/0.085/0.064 for train/validation/test. The maximum empirical CDF differences were 0.027/0.042/0.034. These are descriptive diagnostics; bootstrap descendants are dependent on their source, so independent-sample p-values would be misleading.

| Split | Source anchors available | Generated rows | Distinct anchors represented | Largest selected categorical total-variation distance |
|---|---:|---:|---:|---:|
| Train | 388 | 1,200 | 370 | 0.027 |
| Validation | 125 | 400 | 119 | 0.025 |
| Test | 136 | 400 | 126 | 0.055 |
| All, descriptive only | 649 | 2,000 | 615 | 0.016 |

Every inherited column matched its anchor, including missing math enrichment and intentionally unknown fields. There are 1,385 repeated inherited profiles beyond the first occurrence; this is expected from sampling with replacement. One anchor appears up to eight times. The 400 generated test rows do not supply 400 independent real test cases.

The largest absolute change among the selected pairwise Pearson correlations was 0.102, for father education versus commute category in the test split. This is compatible with bootstrap weighting differences; it is not a universal acceptance threshold or external validation. Pearson correlations on ordinal categories are descriptive only. Quantiles, Wasserstein distances, categorical frequencies, correlations and conditional historical-failure relationships are included in the companion CSVs.

Attendance, engagement, latent financial barriers, response tendency and dropout hazards cannot be compared against measured counterparts here because those counterparts are absent. Their validity remains a scenario assumption. The generated learning gap is a deterministic transform of G1, not an independently measured construct. Four primary fields remain entirely unknown: income amount, currency, verified disadvantage and observed school dropout. Do not fill them with zero or inferred labels.

Whole-profile bootstrapping is suitable for empirical joint-distribution grounding. It supplies neither anonymity nor new empirical evidence. Reuse is defensible with preserved lineage, explicit scenario provenance and separate sensitivity analysis.

## Fixes needed before implementation

1. **Make regeneration safe and portable.** `build_study.py:9` resolves the plan to a nonexistent `/Users/shuniy/Documents/projects/sources/...` path. Its lines 115–120 include its own nested output folder in recursive source enumeration. Fixing the path alone would still overwrite files included in the unchanged-input assertion at lines 260–264. Accept explicit data-root, plan and output arguments; enumerate only real sources; exclude output folders and `.git`; write a new version before replacing outputs. Do not run the current builder in place.
2. **Correct a small subject mapping defect.** For all 25 math-only profiles, math-specific G2/final-grade/absences columns are blank, although their anchor columns contain the values. Populate them from the math anchor when regenerating a new version, with a regression check. No raw value has been lost.
3. **Complete provenance and schema contracts.** The existing dictionary covers the 44 primary fields but not all synthetic/hidden additions. `school_id` lacks its `school` source-field mapping. The companion field mapping and provenance register make exclusions and assumptions explicit. They are proposals for the next version, not edits to the original dictionary.
4. **Separate five sessions from block duration.** The package currently uses four-week tutoring blocks and per-session effects without a session schedule. Define configurable session count (initially five if following the brief), length, cadence, delay, cancellation and missed-session rules. Recompute reservations from that schedule. Neither five sessions nor four weeks is an empirical fact from these data.
5. **Choose a mentor model explicitly.** Pooled tutor-hours do not validate individual mentor assignments. If claiming mentor allocation, add synthetic mentor identities, skills, availability, hours and simultaneous caseload limits, initially configurable at 1–2 students. Allow unused mentors and unmet student demand. Otherwise describe the first experiment as allocation of pooled support capacity.
6. **Resolve eligibility and observation boundaries.** Learning-gap, engagement and attendance used by eligibility or fairness must come from authorized observations or beliefs. Latent need is evaluator-only. An unknown eligibility field stays unknown and receives a declared assessment/defer rule. Never pass a whole dataframe to the controller and then rely on a denylist.
7. **Calibrate actual usual-support trajectories.** The 10% calibration is for a static 36-step hazard conversion, not dynamic dropout or endpoint non-enrollment. The supplied Markov matrix and actual reset mixture imply approximately 89.23% endpoint enrollment and 11.76% ever-withdrawn by week 36 in a no-action diagnostic. Re-entry makes those outcomes distinct. Calibrate each transition family on training worlds and record achieved rates before freezing test scenarios.
8. **Complete planning and transition definitions.** A four-week planning horizon with zero intermediate reward requires a continuation value or rollout to the week-36 objective. Define the Markov family's observations and eligibility, re-entry state, event order, cost timing and cancellation rules. Freeze the uncertainty set and objective before evaluating an uncertainty-aware method.
9. **Align the research question with the experiment.** Structured missingness experiments can support claims about information quality. Claims specifically about mentor-note extraction require a separate held-out extraction benchmark and downstream experiment; the current main grid does not establish these results.

## Recommended research design

Use a hypothetical end-of-first-grading-period reset. G1 is available at that point; questionnaire availability must be labelled assumed because collection dates are absent. G2, G3 and full-period absences are unavailable at reset. Student IDs, source rows, split keys and linkage hashes are metadata, never predictive features. Include school as a documented contextual feature only when the deployment question justifies it; its local ID must not be confused with a person identifier.

The saved first-period school logistic model predicts **course failure**: test n=136, positives=22, AP=0.720, AUC=0.937 and Brier=0.077. The context-only version has AP=0.505. Reconstruction from saved coefficients/transforms agrees with saved probabilities to within 2×10⁻¹⁰. This verifies saved numerical consistency, not prospective validity or an independent refit. Preserve the prevalence baseline and training-only preprocessing. Add simple alternative models only after the current pipeline is reproducible. Retain multiclass higher-ed outcomes; use the financial-status-excluded baseline as the conservative early-prediction sensitivity because debt/fees/scholarship timestamps need checking.

The data supports P(course failure | recorded school features) and a separate higher-ed endpoint predictor. It does not identify either P(next state | current state, usual support) or P(next state | current state, intervention). Keep dropout dynamics and every response coefficient explicit. Evaluate zero, weak, moderate, delayed, heterogeneous and adverse effects. Do not select an assumed world because it makes the proposed allocator win.

Start with usual support and a tutoring offer. Add liaison and transport assessment only as separately declared extensions. Record offer, acceptance, scheduled delivery, actual delivery, completion and subsequent outcome separately. Delivered treatment can change mutable state, after which stochastic withdrawal risk changes. It must not overwrite a dropout label or immutable demographics.

With hidden response and imperfect observations, use a constrained history/belief policy or rolling-horizon optimizer for a partially observed process. A fully observed CMDP is a diagnostic setting only when its state contract actually satisfies that description. Student, mentor and school entities can be ordinary simulated entities; no LLM agents are required. An RMAB baseline is appropriate only in a stated binary-action, independent-arm reduction, with shared capacity and indexability assumptions made explicit.

For a fixed observed eligible cohort E(g,k,w) in group g, need stratum k and window w, let z(i,w)=1 if student i receives at least one appropriate offer. An access constraint can be:

`sum[z(i,w), i in E(g,k,w)] + slack(g,k,w) >= q * |E(g,k,w)|`.

Keep resource, availability and caseload constraints hard. First minimize explicitly normalized coverage slack, then optimize expected retention; declare normalization before testing. Empty denominators are undefined, not zero coverage. Freeze denominators at window start. Report offer coverage, completed support, waiting time including unserved students, worst-group endpoint enrollment and mentor workload separately. Equal allocations need not mean comparable access. Use recorded sex/age/context and transparent access proxies for audits; never infer sensitive attributes from notes or call the proxy verified poverty.

Compare usual support, random feasible, waiting-time, failure-risk priority (clearly labelled), simulator-estimated dropout-risk priority, estimated benefit/resource, fair planning and uncertainty-aware fair planning. Use identical observed information, budgets, schedules and feasibility checks. Generate policy-specific trajectories using event-keyed common random numbers. Report paired world-level differences and uncertainty; students or weeks within an episode are not independent replicates. Separate simulation Monte Carlo error from source uncertainty and assumed-effect sensitivity.

For language experiments, generate observable facts first and notes from a selected subset. Store separate gold records with field, value, assertion status, date, source and evidence span. Include negation, missing facts, conflicting dates, uncertainty, failed delivery and partial improvement. Hide future outcomes and latent effects from both note generation and extraction. Hold out anchor groups, note templates, paraphrase families and an independent author/generator. Compare gold observable facts, deliberately corrupted structured facts and prompted extraction under the same allocation policy. Evaluate field accuracy, unknown/conflict handling, dates, evidence spans and downstream outcomes. Use calibrated confidence only if calibration is measured.

RAG is a later test of retrieving programme guidance or support evidence, not a source of causal simulator truth. QLoRA is conditional on a demonstrated, meaningful extraction weakness and held-out improvement over prompting. Do not build either before the data, environment and simple policies pass their checks.

Three suitable research questions are: (1) how observation error affects simulated retention and access under limited capacity; (2) whether declared uncertainty-aware allocation improves the utility–access tradeoff under unequal information quality; and (3) how note-derived observations compare with structured forms in extraction accuracy and downstream allocation. All results remain conditional on the Portuguese source profiles and stated simulated mechanisms; applicability to Indian school dropout needs target-domain data.

## Companion artifacts and next implementation order

The companion directory includes:

- `dataset_inventory.csv` and `field_profiles.csv`: all 44 CSVs, measured dimensions, missingness, duplicates, types and ranges.
- `source_field_mapping.csv`: each authentic source field mapped or explicitly excluded.
- `provenance_register.csv`: each primary, synthetic and hidden field plus every config leaf; unavailable placeholders remain labelled unknown.
- `canonical_schemas.json`: proposed separate student, observation, mentor, event and hidden-state contracts. Adoption requires adapters and tests.
- `synthetic_*_comparison.csv`, `conditional_failure_comparison.csv` and `bootstrap_lineage.csv`: numerical comparison evidence.
- `verified_findings.json`, `prediction_readback.csv`, `original_manifest_readback.csv` and `source_provenance_verification.json`: independent checks and source verification.
- `CODEX_IMPLEMENTATION_PROMPT.md`: a concrete staged handoff based on this review.

Proceed through safe ingestion, schemas, preprocessing, prediction baselines, population generation, stochastic environment, usual-support control, simple policies, fairness evaluation, constrained planning, experiment runner, events/notes, extraction and downstream comparisons. RAG and optional QLoRA come last. The first implementation milestone should reproduce and validate existing data preparation without changing its scientific meaning.

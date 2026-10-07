# School dropout, disadvantage and data preparation

The supplied files support a semi-synthetic allocation benchmark. Use documented secondary-school profiles to initialize students, an explicitly assumed dropout process for the simulator, and the authentic university dataset as a separate observational prediction exercise. No supplied school file establishes observed school dropout, real household income, weekly attendance or a causal tutoring response.

This review covers every local CSV, the archive inventories, all three local dataset READMEs, the school codebook and merge example, and the synced project research plan. Statements and instructions inside those documents were treated as reference material. No source file was changed. Official source pages were checked on 6 October 2026. The review of related methods is scoped to the simulator design, not a systematic literature review.

## Source selection and documentation

| Source | Rows | Decision |
| --- | ---: | --- |
| UCI `student-por.csv` | 649 | Primary secondary-school population. Grades and contextual variables; course failure is the measurable outcome. |
| UCI `student-mat.csv` | 395 | Enrich only 358 unique cross-subject matches. Add 25 math-only profiles for a separate sensitivity cohort. |
| `student-dropout-prediction` original subject files | 395 / 649 | Exact copies of the primary files; exclude from sample counts. |
| Its `X_train`, `X_test`, `y_train`, `y_test` | 316 / 79 | Derived math benchmark. Labels are explicitly final-grade failure; transformed predictors lack the fitted preprocessing metadata. Rebuild from the originals. |
| Abdullah mirror `student dropout.csv` | 649 | Its first 33 fields exactly equal Portuguese records, row for row. `Dropped_Out` equals `Final_Grade < 10` in all 649 rows. Exclude as a duplicate and retain the outcome as a failure proxy only. Mirror licence is unspecified. |
| `Student_Dropout_rate.csv` and its archive | 4,424 | CSV exactly equals the local UCI `data.csv` archive member after header cleanup. Genuine university endpoint; use separately. |
| All-level bundle school table | 25,000 | Quarantine for explicitly synthetic-style stress testing. No collection methodology, dates or individual identifiers. |
| All-level district aggregates | 320 | Group-level year/grade/economic-status cells, not student records; no district key. Do not attach them to students or treat their rows as people. |
| All-level university comprehensive | 4,424 | Has zero full-row matches to the authentic UCI table on common original columns. Similar names and sample size do not establish provenance. Do not combine. |
| All-level Spanish university | 39,364 | No collection/codebook documentation; 12,607 rows have earned credits greater than attempted credits. Keep out of primary analysis. |
| All-level master's table | 10,000 | Heterogeneous schemas: 9,955 rows have the original university fields; 45 have a different master's schema. It contains 110,225 missing cells, mostly structural. Treat the blocks separately if used at all. |
| All-level online table | 5,000 | No documented student linkage, longitudinal sequencing or verified withdrawal outcome. Optional software stress material only. |

The [official school documentation](https://archive.ics.uci.edu/dataset/320/student+performance) describes performance records from two Portuguese schools. It provides no verified dropout label. The [official university documentation](https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success) defines dropout/enrolled/graduate at the normal course endpoint and distinguishes enrollment information from first- and second-semester academic results. Both official datasets are CC BY 4.0.

The [all-level mirror card](https://huggingface.co/datasets/EduDevCommons/Student-Dropout-Success-All-Academic-Levels) states a Kaggle origin and MIT licence but does not document sampling or collection. It also reports incompatible table schemas. This is insufficient to validate the bundle as measured school data.

In the large school table, every supplied probability is exactly reproduced by:

`p = 0.02 × (1 + 0.5 × I[economic_status = Economically Disadvantaged]) × (1 + 0.8 × I[attendance_rate < 80]) × (1 + I[gpa < 2])`.

All 25,000 values match to numerical tolerance 1e-12. The `Low Income` category receives no separate multiplier in this rule. There are 5,030 grade-13 rows. These findings strongly suggest an engineered scenario table; its creator's exact generation method is not documented. A model using `dropout_probability` would recover a supplied label-generation signal, not independently discover risk. The formula can be an explicitly hypothetical alternative hazard scenario.

## Relevant variables

| Construct | School fields and interpretation | University fields and interpretation |
| --- | --- | --- |
| Educational disadvantage | `Medu`, `Fedu`: parental education on documented 0–4 scale | Parent qualification codes require a categorical lookup; numerical order is not educational rank. Code 34 means unknown. |
| Digital access | `internet`: home internet, a direct access indicator | No verified LMS/internet measure in authentic enrollment data. Bundle `lms_interaction_score` has undocumented provenance. |
| Travel barrier | `address`, `traveltime`: rural residence and ordered commute duration | `Displaced` is a coded flag; it does not document refugee status or poverty. |
| Household context | `famsize`, `Pstatus`, `guardian`, `famrel`, parental jobs | Marital status, age, international status and parental occupation. Do not infer income from occupation labels. |
| Existing support | `schoolsup`, `famsup`, `paid` | Scholarship, debt and fee-payment status. These are observations, not assigned treatments. |
| Academic need | Past failures, study time, first-period `G1`; later `G2` only after observed | Admission/previous grades, then semester results at their relevant decision times. |
| Attendance | `absences` is a total count without a dated denominator | Daytime/evening attendance is course schedule, not physical attendance. |
| Outcomes | Final `G3`; failure proxy is `G3 < 10` | Authentic `Target`, preserving unresolved `Enrolled`. |
| Audit variables | Source sex, age and school; transparent access proxy groups | Source gender, nationality and special-needs fields. Retain documented semantics; do not guess protected labels. |
| Missing essential constructs | No household income, administrative withdrawal dates, action/dose histories, tutor identifiers, shocks or dated notes | No weekly intervention logs, propensities or verified tutoring response. |

The school access proxy uses three components: both parents' education codes at most 2, no home internet, and travel over 30 minutes. `disadvantage_proxy_count` sums them; `disadvantage_proxy_group = 1` when at least two apply. This is an analyst-defined grouping for access audits. It is not a poverty label, official economic eligibility rule or validated socioeconomic index. Report each component separately and vary the cutoff in sensitivity tests. Parents living apart and no paid tutoring are not treated as evidence of poverty.

The final variable dictionary gives every primary output column a definition, role, source and provenance. Income, its currency, verified economic disadvantage and observed school dropout remain unknown. Alcohol and relationship-status fields remain in the original reference records; they are omitted from default simulator features because they are not needed for the proposed action catalogue.

## Linkage and preprocessing decisions

1. Read raw sources without changing them. Hash every input, record encoding/delimiter and inventory archive members. Normalize the university BOM and trailing tab in column headers in memory.
2. Remove duplicate dataset copies from the analytical sample. Renaming columns or adding an engineered label does not create new students.
3. Apply the 13-field linkage key from `student-merge.R`. The example's inner merge produces 382 pairs, but the key is not unique: eight shared keys are ambiguous. Only 358 keys have one math and one Portuguese row.
4. Anchor the primary population on all 649 Portuguese rows. Attach math information for those 358 safe matches. Preserve all original subject records separately. Keep 25 math-only profiles as a clearly marked extension; do not arbitrarily choose among the 12 math rows in ambiguous shared keys. They remain in the reference table.
5. The resulting 674 rows are conservative initialization profiles, not a verified census of unique people. Local IDs encode source rows. Hashes of linkage keys define conservative split clusters; identical keys stay together even if they describe different people.
6. Assign entire linkage clusters to training/validation/test by deterministic hash, with expected proportions 60/20/20. The realized combined split is 404/130/140; the primary Portuguese split is 388/125/136. No linkage group spans splits. Subject records, synthetic descendants and later notes must inherit the anchor split.
7. Preserve grades on their 0–20 scale; retain ordinal category semantics. Encode job and other nominal codes as categories. Do not rank university qualification, occupation or course codes by their integer magnitude.
8. Fit medians, means, standard deviations and one-hot vocabularies on training records only. Select the logistic L2 strength using validation log loss. Unknown categories map to the reference indicator pattern and must be counted when scoring new data. No oversampling or class weighting was used, preserving probability interpretation.
9. Do not interpret structural missingness as random absence. Missing math enrichment means absent/ambiguous subject linkage, not a zero grade. Authentic raw school and university CSVs contain no missing cells. Missing primary income/dropout fields are intentionally retained.
10. Keep final grades and full-period absences in reference outputs. `G2` is available only after period 2; `G3` is the target. Full-period `absences` cannot be used as dated first-period attendance. No denominator supports converting it into an observed attendance percentage.

The first-period benchmark assumes contextual questionnaire fields were verified by that decision point; original collection timestamps do not establish prospective availability. The contextual benchmark is therefore a retrospective predictor, not proof of deployable enrollment-time performance. Math enrichment does not automatically establish synchronized grade publication across subjects. The default initialization uses anchor `G1` only.

For university early prediction, the file's fee/debt/scholarship values require a measurement-time audit. A second baseline excludes these financial-status fields. Do not use financial statuses that were updated after the prediction time. Semester records can support separate landmark experiments, but not weekly transition fitting.

## Descriptive findings

Portuguese course failure occurs in 100/649 students (15.4%); mathematics failure occurs in 130/395 (32.9%). They are subject-specific outcomes. The difference does not establish different school dropout rates.

| Portuguese subgroup | Failure count / students | Failure rate | 95% Wilson interval |
| --- | ---: | ---: | ---: |
| Both parents' education at most 2 | 57 / 292 | 19.5% | 15.4–24.5% |
| Other parental education | 43 / 357 | 12.0% | 9.1–15.8% |
| No home internet | 32 / 151 | 21.2% | 15.4–28.4% |
| Home internet | 68 / 498 | 13.7% | 10.9–16.9% |
| Travel over 30 minutes | 15 / 70 | 21.4% | 13.4–32.4% |
| Shorter travel | 85 / 579 | 14.7% | 12.0–17.8% |
| At least two access-proxy components | 27 / 128 | 21.1% | 14.9–29.0% |
| Fewer than two components | 73 / 521 | 14.0% | 11.3–17.3% |
| Any prior course failure | 49 / 100 | 49.0% | 39.4–58.7% |
| No prior failure | 51 / 549 | 9.3% | 7.1–12.0% |

These are unadjusted associations. Group definitions overlap, intervals are descriptive and multiple comparisons were not corrected. The sample consists of two schools with no population weights, so intervals do not quantify geographic transportability. Smaller commute groups have substantial uncertainty. Full-period absences are not consistently higher in disadvantaged proxy groups; do not force a synthetic poverty–attendance relationship from these marginals.

The authentic university file contains 1,421 dropout, 2,209 graduate and 794 enrolled records. Dropout fractions among all source rows are 62.0% for debtors versus 28.3% for non-debtors, 86.6% for unpaid-fee status versus 24.7% for current fees, and 12.2% for scholarship holders versus 38.7% for others. These associations do not estimate scholarship, fee relief or tutoring effects. Unresolved enrollment remains a separate outcome.

## Predictive analysis actually executed

Transparent regularized logistic models were fitted with training-only transforms. L2 candidates were 0.1, 1, 10 and 100 on the summed negative log likelihood. Test records were not used for hyperparameter selection. Five hundred linkage-cluster bootstrap replicates quantify test-sample uncertainty conditional on the fitted model and split. A constant training-prevalence model provides the comparison. Boosted trees and repeated-split validation are proposed next experiments and were not run.

| Held-out task | Test n / positives | Average precision | ROC AUC | Brier score | Recall among top 10% reviewed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Portuguese failure, contextual predictors | 136 / 22 | 0.505 | 0.846 | 0.116 | 31.8% |
| Portuguese failure, context plus `G1` | 136 / 22 | 0.720 | 0.937 | 0.077 | 45.5% |
| University dropout vs graduate, declared enrollment fields | 744 / 288 | 0.835 | 0.867 | 0.140 | 25.7% |
| University dropout vs graduate, financial-status fields excluded | 744 / 288 | 0.702 | 0.780 | 0.182 | 21.9% |

The Portuguese constant baseline has average precision 0.162, Brier 0.136 and expected top-capacity recall 10.3%. Review capacity is rounded up to 14 students; ties receive fractional expected credit. With `G1`, 10 of the 14 reviewed students fail and 10/22 failures are captured. Average precision's 95% bootstrap interval is 0.552–0.891, and Brier's is 0.049–0.108. Only 22 positive test records are available; apparent subgroup differences need cautious reporting. ECE on ten fixed-width bins is 0.068 for that model and depends on binning and sample size.

The university binary model excludes the 794 unresolved `Enrolled` cases from both training and evaluation. Its estimates apply to resolved graduate/dropout cases, not all entrants. The raw three-class data is preserved for a future multiclass experiment. Removing debt, fee-payment and scholarship status reduces average precision from 0.835 to 0.702 on the same split. Those fields are informative, but timing must be established before using them prospectively.

Prediction of a failure proxy is useful for checking preprocessing and initialization. It cannot calibrate a real school-dropout hazard or rank causal tutoring benefit. No off-policy causal evaluation is possible without action histories, outcomes, assignment support and defensible identification assumptions.

## Generated student dataset and provenance

`student_dataset.csv` contains the observed/recoded profiles and transparent derived fields, with unavailable outcomes left blank. `synthetic_student_population.csv` contains 2,000 reset fixtures drawn with replacement from the primary Portuguese cohort inside its existing split. Whole profiles are sampled to preserve empirical joint structure instead of independently assembling socioeconomic marginals. The generated fixture allocation is 1,200/400/400, not 2,000 independent observed students. For 2,000-agent evaluation episodes, sample anew within the held-out source split and retain all descendants together.

Generated initial attendance is `clip(0.90 - 0.12*gap - 0.06*long_commute + Normal(0,0.04), 0.50, 0.99)`. Generated engagement is `clip(0.80 - 0.25*gap + Normal(0,0.08), 0.10, 0.99)`. Here `gap = clip((10-G1)/10,0,1)` is a hypothetical need scale. These relationships are assumptions, not measured attendance or engagement.

The hidden reset fixture uses annual probability `sigmoid(intercept + 0.9*gap + 0.5*long_commute + 0.3*no_internet + 0.4*I[past_failures>0])`. The intercept −2.48235865 makes the training Portuguese profiles' mean static annual probability 10%. Weekly hazard is `1-(1-p_annual)^(1/36)`. This annual-to-week conversion is exact for a constant hazard with no recovery; a changing-state simulator needs its own usual-support trajectory calibration. Test risk is not forced to 10%. The generated probability is not learned from the observed failure label.

Hidden response tendency is Beta(4,2). A hypothetical unobserved financial barrier is Bernoulli(0.35), deliberately independent of observed proxy groups in the base fixture. A static annual dropout draw is supplied solely as an environment test fixture, not as a known future outcome for the policy. Separate the hidden truth from the controller observation. Re-entry, delayed intervention effects and random event streams are specified in the experiment protocol and must be implemented in the sequential environment.

## Practical recommendation

Use the 649 Portuguese profiles as the main population, assess access using transparent component groups, and evaluate retention under several declared response models. Use the 674-profile mixed-subject initializer only as sensitivity analysis. Start with a tutor-only CMDP, then add liaison/referral actions as a separate heterogeneous-resource extension. Keep outcome, access and resource metrics distinct.

The highest priority missing data is dated enrollment/withdrawal, student-level attendance windows with denominators, offered and delivered support with timing/dose, verified socioeconomic eligibility, and tutor capacity. Those fields would support genuine trajectory calibration and later intervention evaluation. This package completes the data preparation, observational analysis and experiment design; it does not run the proposed sequential policy experiments or establish real prevention effects.

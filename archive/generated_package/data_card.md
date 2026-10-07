# Data card

**Name:** Portuguese secondary-school profiles for a semi-synthetic support-allocation simulator, version 1.0, 6 October 2026.

**Purpose:** Initialize contextual and academic characteristics, audit group access, and test constrained allocation under explicit assumed student dynamics. Intended users are researchers implementing the CMDP/partially observed simulator.

**Source:** UCI Student Performance (Cortez, 2008), supplied math and Portuguese CSVs and codebook. Two Portuguese schools, GP and MS; questionnaires and school reports. These are subject-performance records, not a representative national survey. Licence: CC BY 4.0, [DOI 10.24432/C5TG7T](https://doi.org/10.24432/C5TG7T). Changes include variable recoding, conservative subject linkage, deterministic splits and explicitly declared assumptions.

**Units and size:** Primary cohort 649 Portuguese-course rows, with math enrichment on 358 unambiguous cross-subject keys. The initialization CSV adds 25 math-only rows, totaling 674 profiles. Twelve ambiguous math rows are retained only in the full 1,044-row subject reference table. Profiles are not verified unique person identities. Source age range is 15–22, so the cohort includes adults.

**Linkage:** The codebook's 13-field key is checked for multiplicity. Match only one-to-one keys; preserve ambiguous/absent enrichment as missing. The documented merge yields 382 pairs, but 358 safe keys. Group hashes are split clusters, not official student IDs.

**Splits:** Primary Portuguese counts are train 388, validation 125 and test 136. Combined counts are 404, 130 and 140. A stable hash assigns linkage groups, with no group crossing splits. All generated descendants inherit the anchor split. A source-school holdout is a proposed robustness check; the supplied split does not establish generalization to new schools.

**Observed constructs:** Parent education and occupation, home internet, commute category, rural/urban residence, family context, existing supports, past failures, study time, source sex, age, school and grades. Questionnaire collection timestamps are not established. Final grades and full-period absences belong in reference/evaluation outputs, not prospective reset inputs.

**Labels:** `G3 < 10` measures final course failure. The relabelled mirror's `Dropped_Out` is exactly this proxy, not verified withdrawal. `observed_school_dropout` is missing for all primary profiles. The university file is a separate population with dropout/enrolled/graduate outcomes and must not be joined or pooled with school rows.

**Disadvantage:** Educational/digital/commute components are observable proxies. The ≥2 composite is an analyst-defined access-audit group. Household income, income currency, official economic disadvantage and financial eligibility are unknown. Blank never means zero income or ineligible.

**Generated extension:** 2,000 whole-profile bootstrap reset fixtures: 1,200 train, 400 validation and 400 test. Attendance, engagement, enrollment at reset, hazard, response tendency and financial barriers are assumed/generated. This does not increase the number of independently observed students. Source identity remains in `source_anchor_student_id` and `linkage_group_id` for provenance and split control.

**Observation separation:** `student_outcomes_reference.csv` and `subject_records_reference.csv` contain late outcomes. `simulator_hidden_truth.csv` contains hidden scenario probabilities and a static future draw. The controller must not load these. Only the environment or a clearly labelled parameter diagnostic can access hidden parameters; future draws must remain unavailable to all decision policies.

**Intervention evidence:** None of the input tables supplies randomized tutoring assignment, session timing/dose, verified action response or behavior-policy probabilities. Source support flags are observational, not a treatment log. All action costs, uptake, eligibility thresholds, delays and effects in this package are scenario assumptions.

**Known limitations:** Two schools; no weights; overlapping subject populations; ambiguous linkage; retrospective timing; coarse self-reported context; no observed dropout or weekly dynamics; no verified household poverty. Real financial eligibility, causal dropout prevention and applicability to Indian children require target-domain records and validation that this package does not provide.

**Integrity and reproducibility:** Every original input is hashed in `analysis/source_manifest.csv`. `analysis/validation.json` confirms unchanged inputs, unique output IDs, valid hazards and split isolation. The builder uses seed 20261006, Python 3.12.14, NumPy 2.3.5 and pandas 2.2.3. Source decisions, variable profiles, coefficients, predictions and validation-selected regularization are included. No sequential policy trial has been run.

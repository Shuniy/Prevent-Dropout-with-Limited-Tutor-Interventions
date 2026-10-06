# Student data and CMDP experiment package

Prepared on 6 October 2026 from the supplied school-dropout files and the project research plan.

Start with [the findings and preprocessing report](report.md), then [the experiment protocol](experiment_plan.md) and [data card](data_card.md). The dataset is a population initializer for a semi-synthetic simulator. It does not contain measured school dropout or measured tutor effects.

## Main files

| File | Contents and intended use |
| --- | --- |
| `data/student_dataset.csv` | 674 conservative initialization profiles. Default to its 649 Portuguese-course profiles. Includes 358 unambiguous math enrichments and 25 math-only profiles for sensitivity analysis. |
| `data/synthetic_student_population.csv` | 2,000 bootstrap reset fixtures with explicitly assumed attendance and engagement, split into 1,200 training, 400 validation and 400 test rows. Resample within the appropriate split for an episode of a different size. |
| `data/variable_dictionary.csv` | Definitions, transformations, missingness, source and provenance of every column in the primary student table. |
| `data/student_outcomes_reference.csv` | Historical final grades, failure proxies and total absences. Reference/evaluation only; exclude from the controller's reset observations. |
| `data/simulator_hidden_truth.csv` | Generated hazards, response tendency and financial barriers. Environment/oracle only; never controller input. |
| `data/subject_records_reference.csv` | All 1,044 original subject records with metadata, preserved separately from the initialization table. |
| `data/higher_ed_enrollment_features.csv` | 4,424 separate university records. Do not pool with the school population. Financial-status measurement time needs verification. |
| `data/higher_ed_outcomes_reference.csv` | Three-class university outcomes and semester performance, kept separate from early features. |
| `data/split_manifest.csv` | Immutable student/profile cluster assignments for reproducible evaluation. |
| `configs/simulator_config.json` | Hypothetical horizon, resource accounting, actions, hazards, uncertainty scenarios and seed sets. |
| `configs/experiment_grid.csv` | 144 primary policy/scenario cells, with 30 evaluation seeds each; planned, not executed. |
| `analysis/` | Source audits, archive inventory, descriptive associations, held-out logistic baselines, intervals and validation evidence. |

The analysis workbook summarizes findings for browsing. The CSVs are the simulator inputs. All original files remain unchanged; the validation file confirms their hashes before and after preparation.

## Loading rules

1. For the main experiment, select `anchor_subject == "portuguese"` and the required `split` from the student table, or the matching split from the synthetic table. Keep every bootstrap descendant of an anchor inside its original split.
2. `income_amount`, `income_currency`, `verified_economic_disadvantage` and `observed_school_dropout` are unknown. Blank is not zero or false.
3. Do not train a school-dropout predictor on the reference failure proxy. Models fitted here predict course failure; simulated dropout uses a separately declared hazard model.
4. Do not load the reference-outcome or hidden-truth files into the policy observation pipeline. A true-parameter diagnostic can use hidden parameters, but cannot see future random draws.
5. New weeks, interventions and dropout events must come from the simulator. No action-dependent weekly trajectory is observed in these files.

## Reproduction

`build_study.py` rebuilds the audits, CSVs, synthetic fixtures and numerical baselines using NumPy and pandas. It uses source-path defaults that can be changed at the top of the file. The reported versions are Python 3.12.14, NumPy 2.3.5 and pandas 2.2.3. `support/build_workbook.mjs` rebuilds the summary workbook using the supplied artifact runtime.

The supported scope is an empirically grounded Portuguese secondary-school computational benchmark. It cannot establish effects in Indian schools, verify poverty, or demonstrate real dropout prevention. A target-domain study requires child-level records with defined withdrawal outcomes and intervention timing.

## Attribution

Primary school data: Cortez, P. (2008), *Student Performance*, UCI Machine Learning Repository, [DOI 10.24432/C5TG7T](https://doi.org/10.24432/C5TG7T), CC BY 4.0. This package recodes fields, uses conservative cross-subject linkage and adds analyst-defined proxies and generated simulator assumptions.

Separate university data: Realinho, V. et al. (2021), *Predict Students' Dropout and Academic Success*, UCI Machine Learning Repository, [DOI 10.24432/C5MC89](https://doi.org/10.24432/C5MC89), CC BY 4.0. See the official dataset card for full authorship. The undocumented mirrors and all-level bundle are audited but are not redistributed as primary data in this package.

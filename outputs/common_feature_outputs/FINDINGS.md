# Common features and PCA/neural-network analysis — result summary

**Outcome warning:** school target = course failure, university target = enrollment status or resolved dropout vs graduation.
PCA variance relevance is not predictive/causal importance; weak partial indicators are not equivalent fields.

## Validation-selected model per task
| task                       | feature_set             | representation   |   positive_pr_auc |   positive_roc_auc |   macro_f1 |   positive_brier |
|:---------------------------|:------------------------|:-----------------|------------------:|-------------------:|-----------:|-----------------:|
| university_three_class     | full_eligible           | original_encoded |          0.626909 |           0.767949 |   0.442094 |        0.172521  |
| university_resolved_binary | full_eligible           | original_encoded |          0.69605  |           0.774397 |   0.69915  |        0.185205  |
| portuguese_course_failure  | common_plus_exploratory | original_encoded |          0.635583 |           0.930223 |   0.7341   |        0.0809021 |

## Feature category inventory
| dataset    | category         |   n_columns | columns                                                                                                                                                                                                                                                                                           |
|:-----------|:-----------------|------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| school     | unique           |          15 | school_id, rural_residence, family_size_gt3, parents_apart, guardian, travel_time_category, study_time_category, family_support_existing, paid_classes_existing, extracurricular, nursery_attended, higher_education_aspiration, internet_at_home, family_relationship_rating, health_self_rating |
| school     | common           |           6 | age_years, sex_source, mother_education_code, father_education_code, mother_job, father_job                                                                                                                                                                                                       |
| school     | partial_cautious |           2 | past_failures_count, anchor_grade1_0_20                                                                                                                                                                                                                                                           |
| school     | partial_weak     |           2 | school_support_existing, no_home_internet                                                                                                                                                                                                                                                         |
| university | common           |           6 | Age at enrollment, Mother's qualification, Father's qualification, Mother's occupation, Father's occupation, Gender                                                                                                                                                                               |
| university | unique           |          12 | Application order, Unemployment rate, Inflation rate, GDP, Marital status, Application mode, Course, Daytime/evening attendance, Previous qualification, Nacionality, Displaced, International                                                                                                    |
| university | partial_cautious |           2 | Previous qualification (grade), Admission grade                                                                                                                                                                                                                                                   |
| university | partial_weak     |           2 | Educational special needs, Scholarship holder                                                                                                                                                                                                                                                     |

This notebook used original archive splits, imputation/encoding/PCA fit only on training data, and identical NN architecture.
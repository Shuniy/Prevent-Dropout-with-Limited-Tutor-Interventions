# Data interfaces

`src/data/contracts.py` defines immutable typed records. They reject unsupported
fields, invalid categories, non-finite numbers and inconsistent identities/times.
Existing interfaces for later risk, allocation and feedback work are retained;
they do not imply those services are implemented.

`src/data/dataset.py` reads generated CSVs into pandas DataFrames and converts
values in memory. `read_table` preserves strings and blanks; `population_table`
filters splits/cohorts. These raw research interfaces are not policy feature
allowlists. Record adapters preserve the validated consumer interfaces below.
It checks record IDs, category/range constraints and within-population split
consistency. It does not rebuild the dataset or authenticate deleted raw sources.

| Interface | Input and result |
| --- | --- |
| `PolicyStore.load_reset(split, cohort="fixture")` | Reads only the selected population CSV; returns allowlisted observations |
| `ContextStore.load(split, cohort="fixture")` | Returns context, lineage, audit groups and explicit unknowns |
| `EnvironmentStore.load_fixture(split)` | Joins synthetic population with hidden parameters to return reset states |
| `EvaluatorStore` | Reads retained subject references, outcomes and static diagnostics unchanged |

Each store accepts an optional dataset directory and defaults to `data/` (organized subdirectories; legacy flat CSV directories also work).
Supported cohorts are `fixture`, `primary` and `sensitivity`; splits are `train`,
`validation` and `test`. `model_features()` excludes IDs, audit groups, hidden
parameters and outcomes. The underlying population CSV contains assumed dynamic
fields, but the policy projection withholds those values.

Missing income, verified disadvantage and observed school dropout remain null.
Source categories retain their supplied meanings. Dataset files are never modified;
existing blanks in evaluator references remain blank. In particular, no automatic
repair of math-only historical outcome blanks takes place.

These interfaces separate normal application data flows. They are not an operating
system sandbox against Python code that independently reads local files.

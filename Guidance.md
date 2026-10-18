# Implementation guidance

Read this file and the README before changing the project. This is the shared
reference for the user and Codex. Update both documents whenever a stage or public
function changes. The README is the current project specification and status;
this file explains how to implement it simply.

## Coding approach

- Read CSV data with pandas. Keep working tables as DataFrames; export analysis
  tables with `to_csv`. Do not route ordinary data work through JSON or nested
  dictionaries. Existing typed consumer records remain useful at API boundaries.
- Use Jupyter notebooks to explain and explore data step by step. Put reusable
  loading and validation in `src/`; import it from notebooks.
- Prefer named intermediate variables, ordinary loops, column selection, `.loc`,
  `groupby`, `merge`, `value_counts`, `describe` and `pd.to_numeric`.
- Use NumPy only where it makes the calculation clearer: simple arrays, ranges,
  averages, and seeded random sampling. Avoid clever broadcasting, complicated
  indexing, `einsum`, and unexplained vectorized expressions.
- Plot with pandas and Matplotlib. Label axes, units, population and assumptions.
- Add dependencies only when a stage needs them. Do not build frameworks for future
  stages. Keep business rules in plain functions with meaningful names.
- Notebooks must run from a fresh kernel in order, without hidden cell state.
  Never use exploratory test-set results to tune a model.

## Loader and conversion functions

All dataset loaders default to `data/` (organized subdirectories; legacy flat CSV directories also work). A `directory` argument allows a
separate local copy. They never write input files.

| Function in `src/data/dataset.py` | Purpose and result |
| --- | --- |
| `read_table(table, directory=DATA_DIR)` | Read an allowlisted CSV into a pandas DataFrame; preserve strings/blanks; reject malformed rows, missing/duplicate headers and missing/duplicate IDs |
| `population_table(split, cohort='fixture', directory=DATA_DIR)` | Check split labels and linkage-group separation, filter the requested population and return an independent DataFrame copy |
| `read_rows(table, directory=DATA_DIR)` | Convert a DataFrame to a list of dictionaries for existing record interfaces; no JSON encoding |
| `population_rows(split, cohort='fixture', directory=DATA_DIR)` | The same compatibility conversion for a selected population |
| `binary(value)` | Convert exactly `'0'`/`'1'` to Python booleans; reject other values |
| `integer(value)` | Convert an integral numeric string to a Python integer; reject fractional values |
| `_record(record_type, row)` | Internal conversion of source strings to the fields expected by a dataclass |
| `context_record(row)` | Build validated context, lineage, audit and unknown-field records |
| `environment_record(row, hidden)` | Build reset state from initial assumptions and hidden parameters; omit the static future draw |

The small `csv.reader` pass in `read_table` only checks structural errors that
pandas would otherwise normalize. Pandas does the actual table loading.
`read_table` is a raw research interface, not complete domain validation or a
policy feature interface. Typed context/environment records additionally validate
field categories, types and ranges. `population_table` also checks split separation.

Supported splits: `train`, `validation`, `test`. Cohorts: `fixture` (2,000 synthetic
rows across splits), `primary` (649 Portuguese anchors), `sensitivity` (674 anchors).

```python
import pandas as pd
from src.data.dataset import population_table

students = population_table('train', cohort='primary')
students['anchor_grade1_0_20'] = pd.to_numeric(
    students['anchor_grade1_0_20'].replace('', pd.NA)
)
mean_grade = students.groupby('school_id')['anchor_grade1_0_20'].mean()
```

Convert only columns needed for the analysis. Blank means unknown; use `pd.NA`
in an analysis copy. Do not fill unknown income, disadvantage or dropout with zero.
For joins, declare the expected cardinality using `merge(..., validate='many_to_one')`
or `validate='one_to_one'` as appropriate and check unmatched IDs.

## Consumer interfaces

| Function/class in `src/data/access.py` | Responsibility |
| --- | --- |
| `ContextStore.load(split, cohort)` | Validated source context, lineage, audit groups and explicit unknowns |
| `PolicyStore.load_reset(split, cohort)` | Read only population data and expose allowed reset observations |
| `reset_observations(context, selected)` | Project selected allowed context fields; withhold generated dynamics |
| `model_features(record, selected)` | Extract allowed observed features; exclude IDs, audit groups, outcomes and hidden fields |
| `authorized_measurement(...)` | Validate an explicitly supplied dynamic measurement; does not implement the future observation mechanism |
| `EnvironmentStore.load_fixture(split)` | Match population and hidden IDs and return validated environment reset records |
| `EvaluatorStore.load_subject_references()` | Historical subject records for reference/evaluation |
| `EvaluatorStore.load_historical_outcomes()` | Historical outcomes, including supplied blanks |
| `EvaluatorStore.load_static_fixture_diagnostics()` | Hidden static diagnostics for evaluator use only |

`src/data/contracts.py` defines immutable dataclasses, field constraints and
cross-field checks. `to_dict`/`from_dict`, optional JSON serialization and
`json_schemas` are compatibility utilities, not the analysis workflow. Retain their
existing checks; do not require beginners to use them to explore data. Contracts
for risk, interventions and episodes describe interfaces for future stages, not
working implementations of those services. See `docs/contracts.md`.

## Notebook and command entry points

- `notebooks/01_data_exploration.ipynb`: load, inspect, count, select, convert,
  summarize missingness, plot grades, build allowed features, export a summary.
- `src/experiments/runner.py: population_summary(directory=DATA_DIR)`: return a
  pandas table of split sizes and distinct source-anchor counts.
- `run_simulation(config_path=DEFAULT_CONFIG, dry_run=False)`: validate shared TOML
  config and reset inputs. `dry_run=True` returns a readiness DataFrame with zero
  executed steps; a full run raises `NotImplementedError` until the engine exists.
- `main.py`, `src/__main__.py`, and the installed `school-dropout` command delegate
  to `src/cli.py: main(argv=None)`. Notebooks call the runner directly.
- `notebooks/04_simulator_analysis.ipynb`: executable reset readiness check, clearly
  labeled as preparation for the future simulator.
- `tests/data/test_data.py`: data integrity, split inheritance and consumer separation.
- `tests/data/test_contracts.py`: record validation and future interface constraints.

## Stage completion workflow

1. Implement one useful increment from `docs/roadmap.md` in a responsibility-named module.
2. Add meaningful checks for new behavior, especially leakage, missingness,
   resource limits and reproducibility. Run the existing checks affected by changes.
3. Restart and run affected notebooks from top to bottom; inspect their tables/plots.
4. Update README status, commands, dependencies, specification and diagrams to match
   what actually works. Record the check performed and the next bounded stage.
5. Update this function guide and `docs/roadmap.md`; label assumptions, planned work
   and executed results separately. Store generated outputs under `results/`.

Do not change source data, merge split groups, treat bootstrap descendants as
independent observations, or rename historical course failure as school dropout.
Policy code uses the consumer interfaces, never raw hidden/evaluator tables.

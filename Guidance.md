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

Supported splits: `train`, `validation`, `test`. Cohorts: `fixture` (2,000 synthetic
rows across splits), `primary` (649 Portuguese anchors), `sensitivity` (674 anchors).

Convert only columns needed for the analysis. Blank means unknown; use `pd.NA`
in an analysis copy. Do not fill unknown income, disadvantage or dropout with zero.
For joins, declare the expected cardinality using `merge(..., validate='many_to_one')`
or `validate='one_to_one'` as appropriate and check unmatched IDs.

`src.models.student` contains plain `Student` and `SyntheticStudent` dataclasses
whose parameters match the two population CSV schemas. Data loading and conversion
remain the responsibility of the pandas data layer.

`src.models.school.School` provides the basic agent allocation increment. It can
load `StudentSimulation` agents from the synthetic population CSV or accept
existing `Student` objects, and it can create configurable mentors or accept
existing `Mentor` objects. `step(month)` returns detailed assignment records for one
month; `run_simulation()` runs the configured 12-month default schedule and returns
`month -> {student_id: mentor_id}` mappings. Mentor student capacity and session
availability renew monthly. The baseline assigns five sessions per student and does
not model session duration. Students are shuffled reproducibly each month without
replacement within that month; prior assignments do not make a student ineligible
later. Per-session mentor costs accumulate against one simulation budget.
CSV conversion, configuration/ID validation, default mentor construction and
assignment-feasibility checks live in `src.utils.school` so the model class stays
focused on monthly simulation state and orchestration.

## Notebook and command entry points

- `notebooks/data_exploration.ipynb`: load, inspect, count, select, convert,
  summarize missingness, plot grades, build allowed features, export a summary.
- `notebooks/simulator_analysis.ipynb`: executable reset readiness check, clearly
  labeled as preparation for the future simulator.
- `notebooks/school_university_common_features.ipynb`: checks for similar features between School and University datasets for feature modelling.

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

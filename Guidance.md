# Implementation guidance

Read this file and the README before changing the project. This is the shared
reference for the user and Codex. Update both documents whenever a stage or public
function changes. The README is the current project specification and status;
this file explains how to implement it simply.

## Coding approach

- Use the standard-library CSV loader for the active agent simulation. Use pandas
  for notebook analysis and future table-oriented experiment outputs.
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

## Student loading and conversion

The active simulation loader defaults to
`data/synthetic/populations/synthetic_student_population.csv` and accepts an
overridable path. It reads the first configured number of records and never writes
the source CSV. Blank nullable values remain `None`; do not turn unknown financial
need or dropout into `False`.

`src.models.student` contains `Student` and `StudentSimulation` dataclasses.
Conversion remains in `src.utils.school`, outside the model records.

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

## Entry points

- `src/main.py`: run the default 12-month allocation baseline.
- `tests/test_school.py`: focused executable checks for the implemented simulation.
- `notebooks/exploratory_analysis.ipynb`: existing exploratory analysis.
- `notebooks/dropout_baseline_analysis.ipynb`: existing baseline-analysis work.
- `notebooks/school_university_common_features.ipynb`: feature comparison work.

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

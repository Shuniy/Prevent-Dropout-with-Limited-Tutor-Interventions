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

## Dialogue and problem references

`src.intervention.dialogues.DialogueIndex` reads the canonical synthetic dialogue
manifest. Use its category, problem, support-type and session queries instead of
duplicating those labels in simulation code. `School` exposes this catalogue through
`problem_categories`, `problem_references`, `support_type_references` and
`problem_reference(problem_id)`.

The dialogue problems are samples, not current student attributes. Do not infer or
randomly assign them to student profiles, and do not interpret dialogue support
statuses as simulated offers, delivery or effects. A future increment may attach an
explicitly supplied problem to a student. Until then, the catalogue is available for
school/student-facing reference and its support types define valid mentor skills.

## Entry points

- `src/main.py`: run the default 12-month allocation baseline.
- `tests/test_school.py`: focused executable checks for the implemented simulation.
- `notebooks/exploratory_analysis.ipynb`: existing exploratory analysis.
- `notebooks/dropout_baseline_analysis.ipynb`: existing baseline-analysis work.
- `notebooks/school_university_common_features.ipynb`: feature comparison work.
- `notebooks/intervention_rag.ipynb`: inspect retrieval and run longitudinal JSON extraction.
- `python -m src.intervention.rag`: analyse one history with local Ollama.

## Longitudinal intervention RAG

`src.intervention.rag.load_sessions(root)` loads only spoken Mentor/Student turns
from session Markdown. Full relative parent paths identify histories; never join
by the repeated student folder name alone. Do not use CSV labels or header support
types as extraction inputs. `SessionIndex.build(sessions)` atomically replaces
SQLite FTS5 passages and refreshes the in-memory source catalogue; call it on every
new index instance and after source changes. `retrieve(student_id, query,
before_session)` filters by history and strictly earlier session before BM25
ranking, retrieving up to two passages from each earlier session. Closing passages
fill missing matches. Call `close()` when done.

`InterventionRAG.analyse(student_id, through_session, question)` replays attended
sessions in chronological order, supplying the current transcript, retrieved raw
passages and all prior validated findings. It returns the final as-of conclusion
plus the JSON memory timeline, spoken-text hashes and retrieved passages. It recomputes
memory after edits rather than silently reusing stale output. A cutoff must name
an existing attended session. Prompt overflow fails explicitly; model context and
the character budget must be increased together for longer histories.

`OllamaClient.generate(messages, schema)` uses local `/api/chat` structured output
with the reference notebook's default model, `qwen3.5:latest`. `validate_conclusion`
checks the full JSON schema, exact quotes against visible spoken evidence, delivery
evidence and evidence prerequisites for outcome/helpfulness claims. These checks
do not establish semantic entailment or causal effectiveness. Keep unresolved
reported barriers distinct from unknown intervention effects; do not force all
reported outcomes to unknown just because external delivery is unverified.
Invalid generations receive at most two validation repair attempts. Never add
rejected responses to memory; retain failure messages in the audit timeline and
raise on exhaustion. Network/service failures propagate without model repair.

The RAG prototype does not update School, risk scores or simulator effects. Use
`tests/test_intervention_rag.py` for isolation, chronology, replay and provenance
regressions. `jsonschema` is the only added dependency; retrieval uses standard
library SQLite FTS5, with no embedding model download.

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

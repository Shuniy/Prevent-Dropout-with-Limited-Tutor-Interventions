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

## Feature-matched intervention simulation

`School.run_interventions(root=..., output_dir=..., client=...)` starts a fresh,
seeded intervention run using `src.intervention.simulation.run_interventions`.
`School.run_simulation()` keeps the original repeated monthly allocation baseline.
The new mode excludes a student after their first programme, keeps one mentor and
plans five appointments **total**, configurable by `sessions_per_student`.

`Student.need_profile`, `need_score`, `primary_support_type` and `initial_scores`
calculate current needs and scores as properties in `src.models.student`.
Keep rules in the model, not duplicated in allocation or reporting. The maximum
severity sets need priority; ties between concerns use their names.
`create_profile(student)` copies these into a separate `StudentInterventionProfile` with the
source fields, initial scores and ranked hypothetical concerns. See the README's threshold table for the rules and severity formulas.
The highest-priority concern chooses the support type. Keep unknown financial need
and dropout risk unknown; do not turn proxies into verified need or diagnoses.
Dataset scores remain fixed when RAG reports qualitative changes.

The simulator selects a seeded history within the matching support folder and
replays its existing spoken turns. It never rewrites source data or fabricates
additional appointments to reach the planned dose. Corpus histories have one to five
recorded appointments; missing appointments have unknown reasons, not school-dropout
labels. Generated mentors are assumed generalists; custom skills and initially
supplied mentor assignments remain constraints. Full programme doses are reserved
at admission, actual recorded appointments are charged afterward, and unused
reservations become available for later allocation windows. A programme is replayed
inside one window; duration and weekly state transitions are not modeled.

`School.step` accepts per-student support types, exclusions and preferred mentors.
`prioritize_by_need=True` sorts descending by student need score after a seeded
shuffle, which breaks score ties, and derives each support type unless explicitly
overridden. Intervention runs enable this mode and report
`allocation_policy="need_priority_seeded_ties"`. The allocation-only baseline keeps
random shared-support allocation. Skill, full-dose session capacity, caseload and
budget checks apply to both. This priority heuristic does not optimize a CMDP.
`reset()` clears school-owned run state. `record_intervention_attendance` replaces
a planned assignment with its recorded count and actual cost, releasing unused
reservations. Do not equate `MentorAssignment.sessions` (planned) with
`completed_sessions` (recorded). The allocation-only baseline still charges the
planned dose and leaves completion unknown.

`Intervention(rag, profile, output_dir, allocation_month=1, progress=None)` in
`src/intervention/intervention.py` owns one assigned programme.
`start_intervention(student, mentor)` verifies the assigned pair and fresh profile,
runs initial/follow-up sessions once, persists validated session JSON and returns
the final student report. The profile must already contain mentor/history IDs and
the mentor must have the student in its caseload. Do not start the same profile
again. `simulation.py` keeps profile snapshots, seeded history selection, school
attendance/budget reconciliation and final student/cohort persistence. Its
`write_report` import remains available, with the shared atomic JSON writer now
implemented in `intervention.py`. The initial session needs no separate LLM call:
it is the first callback of the chronological RAG pass, with empty prior memory.

`InterventionRAG.analyse(..., on_session=callback)` calls the callback immediately
after each successful validation. The `Intervention` controller uses it to write `session_NN.json`
with the source profile, scores, concerns, mentor, spoken turns, findings, hashes,
retrieval provenance and repair audit. One RAG pass carries prior validated memory
forward; do not invoke full replay again for each session. Final reports are written
per student and for the cohort, including incomplete, unassigned and failed cases.
Use a new/empty output directory so older session files cannot survive a shorter run.
Extraction failure preserves earlier validated reports and saves no unvalidated
conclusion. The CLI exits nonzero for failed extraction.

`SchoolCMDPEnvironment.run_interventions()` reports recorded appointments divided
by the cohort's planned appointments as a participation score, including unassigned
students in the denominator. It does not optimize a CMDP or estimate treatment benefit.

## Entry points

- `src/main.py`: run the default 10-student/2-mentor Ollama intervention simulation.
- `python src/main.py --allocation-only`: run the language-free monthly baseline.
- `tests/test_intervention_simulation.py`: matching, participation, resources and reports.
- `tests/test_school.py`: focused executable checks for the implemented simulation.
- `notebooks/exploratory_analysis.ipynb`: existing exploratory analysis.
- `notebooks/dropout_baseline_analysis.ipynb`: existing baseline-analysis work.
- `notebooks/school_university_common_features.ipynb`: feature comparison work.
- `notebooks/intervention_rag.ipynb`: inspect retrieval and run longitudinal JSON extraction.
- `python -m src.intervention.rag`: analyse one history with local Ollama.

## Longitudinal intervention RAG

`src.intervention.rag.load_sessions(root)` loads only spoken Mentor/Student turns
from session Markdown. Prompts represent each spoken turn as a separate
speaker/utterance object so quote boundaries stay explicit. Full relative parent
paths identify histories; never join
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
with the reference notebook's default model, `qwen3.5:latest`.
`GENERATION_SCHEMA` asks the model to select prompt-scoped evidence IDs.
Python resolves IDs to exact single-utterance quotes and original session numbers;
unknown IDs are rejected. Earlier memory is copied when adding IDs, never mutated.
`CONCLUSION_SCHEMA` and saved report fields remain unchanged. `validate_conclusion`
checks the full JSON schema, exact quotes against visible spoken evidence, delivery
evidence and evidence prerequisites for outcome/helpfulness claims. These checks
do not establish semantic entailment or causal effectiveness. Keep unresolved
reported barriers distinct from unknown intervention effects; do not force all
reported outcomes to unknown just because external delivery is unverified.
Invalid generations receive at most two validation repair attempts. Never add
rejected responses to memory; retain failure messages in the audit timeline and
raise on exhaustion. Network/service failures propagate without model repair.

The intervention simulator records RAG findings alongside fixed input profiles;
it does not turn qualitative statements into numeric risk or treatment effects. Use
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

## Shared definitions

Define constants in `src/utils/constants.py` and categorical types in
`src/utils/enums.py`; import them into their consumers. Keep mutable runtime
state, such as a generator's random stream, in the module that owns it.

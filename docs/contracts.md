# Current interfaces

These contracts describe the active application. Historical notebooks and archived
results can use older imports and schemas; they have not been migrated.

## School

Public exports from `src.school` are `School`, `Student`, `StudentSimulation`,
`StudentPerformance`, `Mentor`, `MentorAvailability` and `MentorAssignment`. Each
class also has its matching snake-case module. There is no `src.models` alias.

- `school.loading.load_students(path, count)` reads typed source records without
  changing source files. Optional unknown fields stay `None`.
- `Student.need_profile`, `need_score` and `primary_support_type` evaluate baseline
  source inputs. `school.performance[student_id]` contains runtime measures;
  `src.school.performance.current_needs(student, performance)` applies the same rules
  to current metrics. Severity is scenario priority, not dropout probability.
- `School(...)` accepts counts/defaults or supplied students/mentors. `num_months`
  defaults to 12 and must be positive.
- `school.allocate_programmes(support_type=None)` starts a fresh allocation-only
  run and returns `month -> {student_id: mentor_id}`. It reserves planned costs;
  completion remains unknown. No model or output directory is required.
- `school.run_simulation(intervention, output_dir=None, support_type=None)` starts
  a fresh full monthly run and returns/saves the final school report. `intervention`
  is explicit and must provide `simulate(request)`. There is no separate
  `run_interventions()` stage. Supplied output directories must be new or empty.
- `school.step(month, ...)` allocates once per student, with optional support maps,
  exclusions, preferred mentors and need priority. Skills, caseload, session limits
  and total budget constrain admission. The full simulation owns month advancement.
- `school.make_intervention_request(assignment)` checks a current unprocessed
  assignment and active pair, then copies minimal scalar inputs. Duplicate requests
  for a programme are rejected.
- `school.apply_intervention_result(result)` checks type, all request identity
  fields, month, planned/completed counts and exactly-once application before any
  school mutation. Attendance reconciliation is internal to school.
- `school.reset()` restores baseline performance, complete initial mentor caseloads
  (including external students), accounting, results, evaluations, RNG and clock.
  A fresh run ID prevents reuse of old results. Repeated full runs with the same
  input order/seed and deterministic client reproduce assignments, history choices
  and outcomes; identity and output paths change.

`assignments` contains all admitted pairs; `monthly_assignments` contains only each
month's admissions. `assignment_history` retains planned dose, completed count and
actual cost. `intervention_results` contains public results keyed by programme ID;
`monthly_evaluations` contains immutable before/after records for every student,
including students who were never assigned. `monthly_reports` and
`simulation_report` contain school reports. No private intervention profiles or
index objects are stored on school.

## Confidential programme boundary

The public exports from `src.intervention` are `Intervention`,
`InterventionRequest` and `InterventionResult`.

```python
from src.school import School
from src.intervention import Intervention
from src.intervention.ollama_client import OllamaClient
from src.intervention.transcripts import load_sessions

programme = Intervention(load_sessions(), OllamaClient(), seed=42)
report = School(num_students=2, num_mentors=1).run_simulation(programme)
```

`Intervention(index, client, seed=42, method="simple", private_output_dir=None)` validates the source
catalogue and owns programme state. The first argument accepts a list of `Session`
records or an existing `SessionIndex` for compatibility. Simple mode uses its raw
sessions only. `method="rag"` requires a built `SessionIndex` and retains the original
session-by-session analysis. The CLI defaults to simple and creates an index only
for `--method rag`. A client provides `generate(messages, schema)`;
no default model client is created inside intervention. Private persistence is off
by default. A private output directory must be new or empty at construction and
must be separate from public school output; the CLI checks that neither contains
the other. Python composition code chooses these separate destinations explicitly.

`Intervention.simulate(request) -> InterventionResult` runs one programme without
school imports, school objects or school callbacks. Reusing a run/programme ID,
even with a different pair, raises `ValueError`. A new programme or run starts fresh
memory. School separately enforces one programme per student per run.

The frozen request has only immutable scalar fields:
`run_id`, `programme_id`, `month`, `student_id`, `mentor_id`, `support_type`,
`planned_sessions`. No personal attributes are needed by the current replay.
Callers cannot choose the assigned private history through this API.

The frozen result contains the same request fields plus:

| Field | Allowed values/meaning |
| --- | --- |
| `sessions_completed` | Integer recorded appointments, from 0 to the planned limit |
| `status` | `completed`, `incomplete` (short history), or `unavailable` (no compatible history) |
| `analysis_status` | `completed`, `failed`, or `unavailable` |
| `attendance_improved` | `yes`, `no`, `partial`, `unknown`, `conflicting`; reported school attendance change |
| `primary_barrier_resolved` | `yes`, `no`, `partial`, `unknown`, `conflicting` |
| `intervention_helpful` | `yes`, `no`, `mixed`, `unknown`, `conflicting` |

These indicators are explicitly allowlisted from validated findings, never arbitrary
free text. Failed/unavailable analysis returns unknown indicators. A fully attended
programme can have failed analysis. Recorded attendance and charges remain intact
when generation fails. No exception/model text leaves through the public result.

History selection is a seeded NumPy choice with replacement within the requested support.
School and intervention streams are created by `utils.constants.create_rng(seed)`;
they remain independent of the shared `DEFAULT_RNG` used by teaching examples.
A coherent consecutive history starts at session 1 and is used up to the planned
limit; no appointments are fabricated. Missing compatible history produces zero
attendance and zero actual cost, retaining the admission and preventing a second
programme. Malformed histories fail before generation. Refunds can fund later
months but never refill the same month's plan.

## Extraction and private artifacts

- `load_sessions(root)` reads spoken Mentor/Student turns and allowlisted descriptive
  headers: intervention type, date and stage. `Session` has `history_id`, `number`,
  `turns`, optional `intervention_type`/`date`/`stage`, a `metadata` dictionary property
  and a joined spoken-only `text` property. Prewritten outcome notes are excluded. Corpus history ID
  and school student ID are separate concepts.
- `SimpleLLM(sessions, client, max_prompt_chars=60000).analyse(history_id,
  through_session=None, question=..., on_session=None)` sends all selected sessions
  in one generation with no retrieval or prior generated memory. Each session carries
  a one-based conversation position, a readable chronology label, earlier source
  session numbers, metadata and speaker-labeled utterances. The prompt requires
  cumulative evaluation using only the current and earlier conversations. Its response must
  contain exactly one findings entry per selected session in source order. The
  entire response validates before callbacks or persistence. It returns the same
  `history_id`, `as_of_session`, `timeline`, `conclusion` structure as RAG, deriving
  the conclusion from the final entry. Oversize prompts fail before generation;
  there is no truncation, retry or repair. Earlier timeline entries are retrospective
  reconstructions and may be influenced by later selected sessions; only RAG enforces
  strict temporal isolation. Sessions beyond the selected cutoff enter neither mode.
- `SessionIndex().build(sessions)` builds SQLite FTS5 retrieval. An optional path
  persists a new index; callers close it after use. Old SQLite schemas are not
  migrated. Rebuilding replaces indexed passages.
- `history(history_id, through_session=None)` returns ordered source sessions;
  a cutoff must refer to a recorded session.
- `retrieve(history_id, query, before_session, per_session=2)` returns passages
  only from earlier sessions of that history, with matching and closing passages.
- `InterventionRAG(index, client, max_prompt_chars=60000).analyse(history_id,
  through_session=None, question=..., on_session=None)` processes one generation
  per session with fresh invocation memory. Returns `history_id`, `as_of_session`,
  `timeline`, and full `conclusion`. This is a private/developer interface.
- `OllamaClient(model=..., base_url=..., timeout=300, num_ctx=32768)` performs
  structured `/api/chat` generation. Invalid JSON/schema output raises `ValueError`;
  service failures raise `RuntimeError`. There are no retries/repair loops.
- In RAG mode, valid findings are immediately retained and optionally saved before
  the next session. A failed session is excluded from memory. In simple mode, any
  invalid timeline fails the complete extraction with no partial session files.
  Detailed errors stay private.
  `FINDINGS_SCHEMA` checks structure, not factual accuracy or causal claims.

Optional private files are `programme_NNNNN/session_NN.json` (request identity,
source history ID and detailed findings) and `private_report.json` (private history,
error, public result and unrestricted final conclusion). The file fields and names
are shared by both methods. Earlier valid RAG sessions survive failure; simple mode
saves session findings only after the single response validates. Recorded attendance
and costs remain available if either extraction fails. School exports contain no path
or link to these files.

## School output and failures

| File | Contents |
| --- | --- |
| `month_NN.json` | Run/month, costs, this month's assignments/public results and all student evaluations |
| `student_NNNNN/final_report.json` | Actual student ID, limited `result` or null, unassigned reason and monthly evaluations |
| `final_report.json` | Run ID, months, status, output directory, costs, assignments and student reports |

The student `result` is null with reason `no_feasible_mentor_capacity_or_budget` when
no programme was admitted. An unavailable history is an admitted public result with
`status=unavailable`, not an unassigned student.

The final run status is `failed` if any analysis failed, otherwise `finished`.
Short/unavailable histories alone are not extraction failures. Model/schema failure
stops only that programme's analysis; school continues other programmes and months.
File I/O/configuration failures propagate. The CLI exits nonzero for either kind of
failure and preserves already saved output. Existing nonempty school output is
rejected before reset. Old output formats are not migrated.

Runtime support participation and known reported outcomes update on valid result
application. Unknown or conflicting outcomes leave existing reported state unchanged. Numeric
metrics stay unchanged, and each evaluation records the reason. There is no score,
categorical-to-numeric mapping, automatic grade gain or model retraining.

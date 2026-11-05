# Current interfaces

## School CMDP interfaces

- `ScenarioConfig.load(path)` loads the versioned `[cmdp]` TOML table.
- `School.create_cmdp_environment(config=None)` constructs a synthetic environment
  from its student and mentor records. With no configuration supplied, it derives
  settings from the school; conflicting horizon/budget/seed/programme settings fail.
- `School.run_cmdp(policy, config=None)` returns a completed `CMDPSimulation`.
  Its environment owns simulated conditions and resource history; the school's
  recorded-intervention performance is not overwritten by synthetic results.
- `AllocationPolicy` is a structural protocol with only `plan(state)`; baseline,
  retention and fairness policies satisfy the same contract. The monthly coordinator
  receives the policy explicitly and knows nothing about its optimizer.
- `CMDPEnvironment(students, mentors, config)` copies source inputs. `observe()`
  returns a fully observed benchmark; `observe(fully_observed=False, estimates=...)`
  omits hidden conditions except explicit current-month `ConditionEstimate` values.
- Every policy implements `plan(DecisionState) -> AllocationResult`. Only current
  immutable observations/resources enter that method. No environment/future draw
  reference is supplied.
- `validate_allocation(state, assignments)` independently checks every resource,
  identity, support and episode-eligibility rule. `environment.step(result)` repeats
  validation against current true eligibility before charging and transitioning.
- `environment.records` is immutable historical output. `terminal_reward()` and
  `completed_resource_totals()` are available after the final transition.
  Each `MonthRecord` also freezes that month's mentor capacities and mean waiting
  among enrolled, unsupported students. Waiting increments only after a survived,
  unsupported month; admission and withdrawal stop it without counting that month.
- `episode_metrics(...)` includes `monthly_summaries` from month zero through the
  horizon, with condition counts, retention/dropout rates, new withdrawals, enrolled
  and eligible counts, programme/appointment usage, spending, cumulative spending,
  remaining budget, per-mentor capacities/utilization and mean eligible waiting.
  An empty eligible set has mean waiting zero; an empty cohort has undefined
  retention/dropout rates (`null`). `monthly_conditions` retains its existing
  months 1–T schema, and enrolled student-months exclude month zero.
- `observation_from_result(InterventionResult, current_month)` returns reported
  evidence only, available after the admission month. It cannot mutate truth or
  choose intervention effects. The future state estimator remains external.
- `main.py` runs school policy comparisons; `--suite full` adds the effect
  and budget sweep. Explicit CLI arguments override the versioned CMDP config.
  `--print-monthly` prints monthly and terminal summaries for the first development
  seed of every selected policy/scenario. Summaries are saved for every episode
  whether or not printing is enabled.
  CMDP is the only main CLI workflow; recorded interventions and allocation-only
  runs remain available through Python APIs.

See [CMDP implementation and assumptions](cmdp-implementation.md) for exact
formulae, audit denominator definitions, numerical tolerances and runnable commands.

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
session-by-session analysis. Python callers construct the index explicitly for
`method="rag"`. A client provides `generate(messages, schema)`;
no default model client is created inside intervention. Private persistence is off
by default. A private output directory must be new or empty at construction and
must be separate from public school output. Python composition code chooses
these separate destinations explicitly.

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
  session numbers, metadata and speaker-labeled utterances with absolute one-based turn numbers. The prompt requires
  cumulative evaluation using only the current and earlier conversations. Its response must
  contain exactly one findings entry per selected session in source order. The
  entire response passes JSON, source and per-entry semantic validation before callbacks
  or persistence. Each entry adds one separate model review call using an as-of
  source prefix. It returns the same
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
  `Passage.first_turn_number` and `turns` preserve absolute citation offsets.
- `InterventionRAG(index, client, max_prompt_chars=60000).analyse(history_id,
  through_session=None, question=..., on_session=None)` processes one generation
  per session plus one semantic review, with fresh invocation memory. Context includes
  `source_backed_actions` independently of retrieval: original wording/owner/timing,
  original source turn/date and a `status_history` of accepted reported statuses and
  source turns. This history is built from accepted findings and original source turns,
  never reconstructed from generated narrative summaries. Returns `history_id`, `as_of_session`,
  `timeline`, and full `conclusion`. This is a private/developer interface.
- `OllamaClient(model=..., base_url=..., timeout=300, num_ctx=32768)` performs
  structured `/api/chat` generation. Invalid JSON/schema output raises `ValueError`;
  service failures raise `RuntimeError`. There are no retries/repair loops.
- In RAG mode, valid findings are immediately retained and optionally saved before
  the next session. A failed session is excluded from memory. In simple mode, any
  invalid timeline fails the complete extraction with no partial session files.
  Detailed errors stay private.
  `FINDINGS_SCHEMA` and `validate_findings` check JSON structure. Both evaluators then
  require `validate_semantics`: deterministic provenance/identity checks and a separate
  model review of source entailment, action scope, components and narrative consistency.
  Nonempty review issues, invalid review JSON, unavailable review or budget overflow
  reject the session; there is no retry/repair. Model review remains fallible.

### Findings version 2

- `schema_version=2` is required; historical version 1 findings are not migrated.
- Every `actions` entry has `action_id`, `original_action`, `responsible_person`,
  `agreed_on`, `due_date`, `original_evidence`, `status` and `status_evidence`.
  IDs are `<history_id>:s<original session number>:a<positive ordinal>` and are reused
  across snapshots. Original fields are immutable. All actions, including completed
  ones, carry forward. Changes need current-session evidence. Quotes retain original
  wording; agreement dates match source metadata (null when absent), and due dates
  preserve literal original timing (null when unspecified).
- `not_started`: explicit no work begun without a missed checkpoint;
  `attempted`: effort without a completed required part; `partially_completed`: some
  required work done, full scope outstanding; `completed`: all agreed work explicitly
  done; `not_completed`: explicit failure, abandonment or not done at a checkpoint;
  `unknown`: missing, ambiguous or conflicting progress. Partial work stays partial;
  review/rehearsal/discussion cannot complete the task reviewed. A review agreed as
  its own action can complete independently. Agreement alone gives unknown.
- `intervention.intended_intervention` contains `type`, `status`, `component_ids`
  and `evidence`. The referenced IDs define the intended support scope.
  `direct_activities` have separate IDs/descriptions/evidence and statuses `proposed`,
  `delivered`, `not_delivered`, `unknown`, `conflicting`. `external_support` components
  have statuses `requested`, `pending`, `received`, `not_received`, `declined`,
  `unknown`, `conflicting`. There is no aggregate `service_delivered` boolean.
  Completing the intended intervention requires delivery of all intended components;
  known intervention helpfulness additionally requires subsequent explicit feedback.
- Evidence references contain `history_id`, `session_number`, `turn_number` and
  `quote`, a verbatim substring of the cited utterance. Quotes are checked against
  original sources within the current prefix, never generated memory or future sources.
  Known action/component/detail statuses need evidence. `outcome_evidence` mirrors
  `outcome`; known outcomes and session helpfulness require their cited evidence.
  Source quotes alone are insufficient: semantic review checks that they entail each
  claim, preserve unresolved conflicts and agree with the narrative.

Optional private files are `programme_NNNNN/session_NN.json` (request identity,
source history ID and detailed findings) and `private_report.json` (private history,
error, public result and unrestricted final conclusion). The file fields and names
are shared by both methods. Earlier valid RAG sessions survive failure; simple mode
saves session findings only after the response and every semantic review pass.
Recorded attendance and costs remain available if either extraction fails. School exports contain no path
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
File I/O/configuration failures propagate to Python callers; analysis failures are
recorded in the report, preserving already saved output. Existing nonempty school output is
rejected before reset. Old output formats are not migrated.

Runtime support participation and known reported outcomes update on valid result
application. Unknown or conflicting outcomes leave existing reported state unchanged. Numeric
metrics stay unchanged, and each evaluation records the reason. There is no score,
categorical-to-numeric mapping, automatic grade gain or model retraining.

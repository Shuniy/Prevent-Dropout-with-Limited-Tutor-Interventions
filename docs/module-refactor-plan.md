# School and intervention module refactor plan

Status: implemented. Current behavior and public interfaces are documented in
`architecture.md` and `contracts.md`; the original findings and proposed design below
are retained as implementation context. The allocation-only operation is named
`School.allocate_programmes()`. Full runs use
`School.run_simulation(intervention, output_dir=...)` with explicitly constructed
index/model dependencies. School-specific utilities now live in `school/loading.py`.
Numeric transitions remain deliberately unspecified and are not implemented.

## Intended ownership

School owns students, mentors, assignments, availability, budget, the simulation
clock, performance evaluation, and the generation and saving of school reports.
Intervention owns the confidential programme: source-history assignment, session
progress, LLM/RAG processing, private findings, and the public intervention result.
Intervention never receives the School object or mutable school domain records.

The dependency direction is `main -> school -> intervention`. Intervention may
use independent shared types, but must not import from `src.school` or call back
into school services. Keep the implementation as ordinary classes and functions;
no service framework or dependency container is needed.

## Findings from the current code

- The source directory is now `src/school`, but `src/main.py`,
  `src/utils/school.py`, intervention controllers, and several tests still import
  `src.models`. README and active architecture/contracts documentation also use
  the old package name.
- `src/intervention/simulation.py::run_interventions` receives the entire School,
  assigns `school.intervention_profiles`, calls
  `school.record_intervention_attendance`, assigns `school.intervention_report`,
  and writes cohort, budget, assignment, and student reports.
- `StudentInterventionProfile` is school-located programme state that includes
  history IDs and detailed session findings. This state belongs to intervention.
- `Intervention.start_intervention` depends on School's Student, Mentor, and
  MentorAssignment classes and checks the mentor's current caseload. School
  should enforce assignment validity before making an intervention request.
- `School.run_simulation` plans every month's admissions before any intervention
  runs. It does not implement monthly performance evaluation or feedback.
- `Student.need_profile` uses original grades and initial assumed attendance and
  engagement. Changing these initial fields would overwrite the baseline rather
  than represent longitudinal progress.
- Existing RAG already limits retrieval to earlier sessions of one source history
  and uses fresh analysis memory per invocation. Preserve these properties while
  making each run/programme/student/mentor context explicit.
- Current findings are categorical and narrative. There is no calibrated numeric
  intervention score or student-performance transition rule.

Baseline verification: `.venv/bin/python -m unittest discover -s tests` ran six RAG
tests successfully; four other test modules failed to import because of stale
`src.models` references. The local virtual environment is Python 3.14.8, outside
the declared Python 3.12/3.13 support range. Use a supported environment for final
implementation validation.

## Proposed file changes

| File or group | Planned responsibility/change |
| --- | --- |
| `src/school/school.py` | School facade; own state, assignment validation, attendance/cost reconciliation, and result application. |
| `src/school/simulation.py` | Move cohort orchestration from intervention here; implement the monthly clock and feedback loop. |
| `src/school/reports.py` | Generate and save school student, monthly, and final reports. |
| `src/school/performance.py` | Plain functions that evaluate performance and apply permitted result-derived updates. |
| `src/school/student_performance.py` | Current school-owned performance state and monthly snapshots, separate from source inputs. |
| `src/school/student.py`, `student_simulation.py` | Preserve source/baseline data; reuse need calculations when evaluating current performance. |
| Existing mentor and assignment files | Remain in school; preserve resource checks and school-only mutations. |
| `src/utils/school.py` | Move school-specific loading, validation, and allocation helpers into school, separating files by responsibility where useful. |
| `src/intervention/intervention.py` | Run one programme from a request, maintain private session state, and return an intervention result. |
| `src/intervention/intervention_request.py` | Frozen request dataclass with copied student/mentor inputs and programme identity. |
| `src/intervention/intervention_result.py` | Frozen, limited result dataclass for other modules. |
| `src/school/student_intervention_profile.py` | Move to intervention; make it private programme state rather than a School field. |
| `src/intervention/history_assignment.py` | Validate/catalogue histories and select a coherent recorded programme using a local seeded RNG. |
| `rag.py`, `session_index.py`, `transcripts.py`, `findings.py`, `ollama_client.py` | Remain intervention internals; retain chronology, isolation, schema validation, and explicit model injection. |
| `src/intervention/reports.py` | Limit to private intervention artifacts if persisted; school exports use school reporting. |
| `src/main.py` | Load CMDP configuration and invoke school policy experiments; CMDP is the only CLI workflow. |

Keep each production class/dataclass in its own file. Add explicit package
initializers/exports for the two module boundaries. Keep source datasets and their
generators where they are; no dataset relocation is required.

## Public interaction

The proposed programme API is `Intervention.simulate(request) -> InterventionResult`.
The intervention instance receives its corpus/index and model client explicitly.
School constructs requests and consumes returned values; there are no mutation
callbacks into school.

The request contains run/programme identity, month, student and mentor IDs,
selected support, planned session limit, and the minimal copied student/mentor
attributes actually used by the simulation. Existing controllers currently use
mostly IDs and support information. Do not send entire Student/Mentor objects or
unneeded personal attributes. Nested request values must also be immutable;
`frozen=True` alone does not make a nested list or dictionary immutable.

The result contains matching run/programme/pair identity, support type, programme
status, recorded attendance, analysis status, and approved structured outcome
indicators, such as reported attendance change and barrier resolution. Unknown
remains explicit. Keep recorded attendance independent of generation success.
Separate programme completion from extraction failure and missing source history.

Build the school-facing outcome from an explicit field allowlist. Do not expose
transcripts, retrieved passages, history paths, detailed session memory, or the
current unrestricted narrative conclusion. A narrative summary should be added
only with a defined sharing policy; copying free text into an otherwise limited
report does not provide confidentiality. School reports contain the limited
result and school evaluations only. Private intervention persistence, when used,
has a separate destination and is not linked from exported school reports.

School validates result identity, planned/completed counts, and duplicate result
application before changing any school property. Programme identity prevents
attendance, budget, and performance changes from being applied twice. School
retains only public results, not private intervention profiles or index objects.

## History assignment and confidential RAG

Interpret a random set of intervention history as one coherent chronological
history assigned to a programme for a student/mentor pair. Follow-up transcripts
refer to preceding sessions, so independently sampling unrelated session files
would break continuity.

- Preserve the current default: seeded random choice within the requested
  support type. Reuse with replacement is acceptable for this synthetic corpus;
  each assigned programme still has separate private memory.
- Store the selected history and session progress inside intervention, keyed by
  run/programme/pair identity. Do not redraw on each monthly school evaluation.
- Use at most the planned number of recorded sessions, in order. Never fabricate
  appointments to fill short histories. Missing compatible history returns a
  structured unavailable result with zero attendance.
- Treat source history IDs separately from school student IDs; clarify the
  currently overloaded `student_id` naming in Session/SessionIndex/RAG APIs.
- Retrieval and memory use only the assigned history and sessions available by
  the current cutoff. Pair identity is bound to the assigned history internally;
  callers cannot select a different pair's private history through the public API.
- Continue excluding transcript headers, source profiles, retrospective labels,
  and future sessions from model prompts.
- A later programme or mentor reassignment creates a fresh context; transferring
  private history is not implicit.

## Monthly school simulation

Default to 12 months, retaining a configurable positive month count. Use this
order for each month:

1. Read current school performance, retain the previous snapshot, and determine
   needs and eligibility using one shared set of need rules.
2. Allocate eligible students using mentor skills, monthly capacity/session
   limits, need priority, and remaining budget. Reserve the planned dose.
3. Build immutable requests and simulate the newly admitted programmes.
4. School validates results, records attendance, charges recorded sessions, and
   releases unused reservations.
5. School applies its evaluation rules, records before/after performance, and
   recomputes current needs.
6. Generate/save the monthly school report, then advance the clock. Generate
   student summaries and the final school report after the last month.

Recommended initial scheduling policy: preserve one mentor and one programme per
student per run; each admitted programme is processed inside its allocation month,
as in the current simulation. Continue tracking all students through the remaining
months. Do not reinterpret five planned appointments as five appointments every
month. These are simulation allocation windows, not a claim about source-calendar
dates. Programmes spanning months need an explicit session schedule and retained
caseloads before that behavior is added.

With sequential monthly processing, refunds become available for later months.
This intentionally differs from the current precomputed plan, where refunds never
affect admissions. Do not refill the same month's plan after a refund in the first
implementation. Update the existing test asserting that refunds never admit later
students, and preserve the no-second-programme rule. Repeated programmes or
reassignment should be a separate school policy if later required.

Split the old allocation-only behavior into a clearly named allocation operation
used by the CLI's allocation-only mode. Update callers/tests that currently call
`run_simulation()` followed by `run_interventions()`; the new full simulation runs
the complete school cycle. Reset restores baseline performance, initial caseloads,
accounting, results, snapshots, and seeded selection under a fresh run context.

## Student performance and model updates

Interpret changing the student's model as updating the school's runtime student
state and needs. Automatically retraining a predictive model is outside this
refactor; there is no trained risk model in the active application.

Initialize StudentPerformance from the source record. Keep original grades,
demographics, and `initial_*` assumptions intact. Track current performance,
school-owned support participation, reported outcome indicators, and monthly
evaluations separately. Use one shared need calculation over baseline/current
inputs, so allocation and reporting do not duplicate or disagree on the rules.

Initially, applying a valid intervention result updates participation and reported
outcome state. It does not turn “attendance improved: yes” into a made-up percentage
or automatically increase grades. Unknown, conflicting, or failed extraction
leaves the relevant performance measure unchanged and records the reason.
Reported improvement remains distinct from an independently observed metric.

If numeric changes or an intervention score are required, specify the permitted
fields, score scale, categorical-to-score mapping, transition parameters, bounds,
and unknown/failure behavior in school configuration before implementation. School
owns the mapping from any intervention score to student-state changes. Mark those
transitions as simulation assumptions, and keep actual school attendance separate
from mentoring attendance. Evaluation can change a current need only when its
underlying input has supported new information or an explicit simulation rule.

## Implementation sequence and acceptance checks

1. **Repair the package rename.** Update active source/test imports and current
   documentation to `src.school`; move school-specific utilities. Establish a
   passing baseline in Python 3.12/3.13. Preserve historical notebooks and archives.
2. **Enforce the intervention boundary.** Introduce request/result records, move
   private profiles, and refactor Intervention to operate without school imports.
   Check copied/immutable inputs, assigned-history isolation, chronology, duplicate
   programme protection, and valid partial findings on model failure.
3. **Move cohort and reporting ownership.** Move school orchestration out of
   `intervention/simulation.py`; reconcile attendance/budget only in school.
   Check that running intervention alone cannot change student fields, mentor
   caseloads, assignments, accounting, school reports, or school output files.
4. **Add monthly evaluation.** Introduce current performance and snapshots, then
   run allocation/intervention/evaluation/reporting in monthly order. Check that
   month two sees month one's supported updates and refunded budget; no future
   result influences an earlier allocation. Verify 1-month, 12-month, zero-agent,
   missing-history, short-programme, unknown-result, and failed-model cases.
5. **Update interfaces and documentation.** Adjust CLI help and output schema;
   update README, architecture, contracts, roadmap, and stale Guidance.md claims
   about immutable numeric needs/precomputed plans to match the selected policy.
   Retain the standalone RAG command as a private analysis/developer tool.

Final validation uses the offline unittest suite with the shared fake client,
script/module allocation CLI smoke checks, a full fake-client school run, and
affected teaching examples. Add observable checks for no private-data exports,
result application exactly once, baseline preservation, deterministic history
selection with a fake model, and clean reset/repeat behavior. A live model run is
optional and is separate from deterministic tests.

## Assumptions to keep explicit during implementation

- A programme initially fits within one school month; longitudinal tracking lasts
  the configured simulation period.
- A random history is support-matched and coherent, with reuse permitted.
- Each student gets at most one programme per run until school eligibility policy
  is explicitly extended.
- Confidentiality is enforced at the module API and report boundary. Python
  packages in one process are not an operating-system access-control boundary.
- Numeric transition rules and any calibrated score need their own specification;
  they cannot be inferred from the existing categorical LLM findings.

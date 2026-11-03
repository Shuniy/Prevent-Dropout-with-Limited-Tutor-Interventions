# Current interfaces

These interfaces describe the working Python application. Historical notebooks
and research specifications may use older imports or result fields.

## Records and allocation

Import each production class from its matching module under `src.models`:
`student`, `student_simulation`, `student_intervention_profile`, `mentor`,
`mentor_availability`, `mentor_assignment`, and `school`.

- `load_students(path, count)` in `src.utils.school` reads typed simulation records
  from the supplied CSV without changing it. Nullable values remain `None`.
- `Student.need_profile` returns a fresh severity-ranked list of hypothetical
  concerns; `need_score` is the highest severity and `primary_support_type` its
  support. These are allocation inputs, not analytics or dropout predictions.
- `School(...)` accepts counts/defaults or explicit student and mentor objects.
- `School.step(month, ...)` returns `MentorAssignment` records and enforces skills,
  monthly caseload/session limits, and total budget. Optional support requests,
  excluded students, preferred mentors, and need priority control allocation.
- `School.run_simulation()` returns `month -> {student_id: mentor_id}`. Students
  are prioritized by need and allocated at most once per run; mentors can be reused
  in later months. `assignments` contains all allocated pairs, while monthly maps
  contain only that month's admissions. Scheduled sessions are reserved; completion
  is unknown. Calling this method explicitly starts a new run.
- `School.reset()` restores school-owned run state and its initial caseloads.
- `School.record_intervention_attendance(assignment, count)` replaces the reserved
  assignment with recorded sessions and actual cost, releasing unused resources.

## Intervention workflow

`School.run_interventions(root=..., output_dir=..., client=...)` returns and saves
one run report. The model client is optional at this composition boundary and
defaults to Ollama. Output directories must be new or empty. Call
`school.run_simulation()` first. Intervention consumes `assignment_history` without
resetting the school or allocating students. A second replay of the same run raises
`ValueError`; explicitly create a new allocation run to repeat the experiment.

`create_profile(student, planned_sessions=5)` creates a programme record containing
student ID, selected support, planned count, assignment/history IDs and runtime
status. It does not copy the dataset or score snapshots.

`Intervention(rag, profile, output_dir).start_intervention(student, mentor)` requires
an assigned pair, a matching history and a fresh profile. It runs once, saves each
valid session before processing the next, and returns the student final result.
The cohort supplies `assignment=...` to validate the recorded plan even when a
mentor's active caseload has since moved to another month.
The cohort runner adds the reconciled assignment and saves the final student file.

The highest-priority support selects a corpus folder. A seeded draw chooses a
history within it. The programme uses at most the planned count and never invents
appointments. A missing matching history or insufficient resources yields an
unassigned result. Full-dose reservations happen before admission; only recorded
appointments are charged afterward. Refunds do not change the saved plan. Each
student enters at most once per run.

## RAG and generation

- `load_sessions(root)` in `transcripts` reads spoken turns and full relative history
  IDs. A `Session` has `student_id`, `number`, and `turns`; `text` joins the turns.
- `SessionIndex().build(sessions)` builds an in-memory SQLite FTS5 index. An optional
  path can store a new index. Rebuilding replaces indexed passages.
- `history(history_id, through_session=None)` returns ordered sessions. A cutoff
  must name an existing recorded session.
- `retrieve(history_id, query, before_session, per_session=2)` returns `Passage`
  objects containing a session number and text from earlier sessions of that history.
  Matching passages are supplemented by closing passages when needed. Close the
  index after use.
- `OllamaClient(model=..., base_url=..., timeout=300, num_ctx=32768).generate(messages,
  schema)` returns parsed JSON from `/api/chat`. Service failures raise `RuntimeError`;
  invalid or truncated JSON raises `ValueError`.
- `InterventionRAG(index, client, max_prompt_chars=60000).analyse(history_id,
  through_session=None, question=..., on_session=None)` makes one call per session.
  The optional callback receives valid findings immediately for persistence; it is
  not a logging hook. Returns `student_id`, `as_of_session`, `timeline`, and `conclusion`.
- Timeline entries contain `session_number` and `findings`. Context contains current
  spoken turns, earlier retrieved text, and earlier validated findings only.
- `FINDINGS_SCHEMA` and `validate_findings` in `findings` define/check the same output
  structure used for generation. There are no citation fields or repair attempts.

## Saved results and failures

| File | Fields |
| --- | --- |
| `session_NN.json` | `student_id`, `mentor_id`, `session_number`, `findings` |
| Student `final_report.json` | `student_id`, `mentor_id`, `support_type`, `planned_sessions`, `sessions_completed`, `status`, `error`, `conclusion`, `assignment` |
| Unassigned student | Same fields plus `unassigned_reason`; an allocated student with no matching history retains its mentor/assignment with zero attendance and cost |
| Run `final_report.json` | `status`, `output_dir`, `spent_budget`, `remaining_budget`, `assignments`, `students` |

A student is `completed`, `incomplete`, `unassigned`, or `report_failed` in final
results. Run status is `failed` if any student's extraction fails, otherwise
`finished`. Unassigned reasons are `no_matching_history` or
`no_feasible_mentor_capacity_or_budget`. Recorded attendance remains independent of
model success. A failed student has no final conclusion; earlier session files remain.

Malformed source histories and invalid configuration fail before generation.
Model/schema failures stop only that student's extraction; the cohort saves failure
results and continues. File I/O failures propagate. The CLI exits nonzero on failure.
Old results and old persisted SQLite schemas are not migrated.

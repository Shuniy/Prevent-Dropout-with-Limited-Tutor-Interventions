# Current interfaces

## Source records and resources

`load_students(path, num_students)` converts a deterministic CSV prefix to
`StudentSimulation` records. Blank nullable values remain `None`; the source is
never modified. `Student` also works when assumed attendance/engagement are absent.
`School` rejects duplicate student/mentor IDs and invalid resource configurations.

A `Mentor` declares its ID, support skills, active-student limit, monthly availability,
current student IDs and session cost. Generated mentors are assumed generalists over
all 13 support types. Explicit mentor skills and existing caseloads are honored.

## Original allocation mode

`School.run_simulation()` returns `dict[int, dict[str, str]]`, mapping allocation
month to student IDs and mentor IDs. Students can be selected again in later months.
`School.step(month)` returns new `MentorAssignment` records. Optional
`student_support_types`, `excluded_student_ids` and `preferred_mentor_ids` support
programme matching without replacing feasibility checks.

A `MentorAssignment` contains student, mentor, support type, month, planned `sessions`,
`cost_units`, and nullable `completed_sessions`. In allocation-only mode costs apply
to all scheduled sessions and completion is unknown. `spent_budget` and
`remaining_budget` expose the episode totals.

## Intervention mode

`create_profile(student, planned_sessions=5)` returns a separate
`StudentInterventionProfile` with the source record, initial numeric scores and
ranked hypothetical feature-derived concerns. It does not mutate the source model.
Scores include learning gap, nullable assumed attendance/engagement, explicit support
priority, and `school_dropout_risk=None`. Severity rules are `feature_rules_v1`.

`School.run_interventions(root=HISTORIES, output_dir=None, client=None, progress=None)`:

1. Starts a fresh seeded run and calculates profiles.
2. Assigns each student at most one mentor/programme, using its primary concern.
3. Selects one seeded source history within the matching support type.
4. Creates an `Intervention` controller per assigned student; replays up to
   `sessions_per_student` attended source appointments, default five total, through
   the existing chronological RAG.
5. Immediately writes every validated session, then student and cohort final JSON.

An initial caller-supplied mentor is retained when feasible. Whole doses reserve
capacity/budget at admission. `record_intervention_attendance(assignment, count)`
sets actual completion/cost and releases unused reservations. The programme stays
inside its admission month; unused resources are available in later windows.
Students without matching histories, eligible mentors, capacity or budget receive
explicit unassigned reports. No second programme is started in later months.

The returned JSON dictionary is also available through `school.intervention_report`;
`school.intervention_profiles` maps dataset student IDs to profile objects.
After intervention replay, `school.assignments` includes all assigned programme
students, while `monthly_assignments` retains their admission windows.
`reset()` clears school-owned allocations, accounting and intervention run state.

`Intervention(rag, profile, output_dir, allocation_month=1, progress=None)` organizes
one programme. `start_intervention(student, mentor)` requires matching profile IDs,
a selected history, a positive planned dose, an active mentor caseload assignment
and a fresh profile. It rejects repeated starts. It writes validated session files
and returns the final student dictionary (without resource accounting).
The simulator calls `School.record_intervention_attendance`, attaches `assignment`,
and writes the final student JSON. Thus the public school/cohort report schema is
unchanged. The empty `first_session` stub is replaced by the first iteration of the
single chronological RAG pass; later sessions retain its validated memory.

## Report artifacts

A new timestamped output directory is the default; a supplied directory must be
empty. Sequence-numbered student folders avoid interpreting student IDs as paths.

- `student_NNNNN/session_NN.json`: student/mentor/history IDs, allocation month,
  source profile, initial scores, assigned concerns, spoken turns, validated findings,
  evidence, source hash, retrieved passages and validation repair failures.
- `student_NNNNN/final_report.json`: profile, assignment, planned/recorded counts,
  unrecorded appointment numbers, accumulated session reports and final conclusion.
- `final_report.json`: configuration, seed, rule version, assumptions, assignment
  records, all student reports, participation counts and budget totals.

Student statuses are `completed`, `incomplete`, `unassigned` or `report_failed`.
Completion means the appointment dose was recorded, never barrier resolution.
School dropout remains unknown. The model sees no retrospective attendance labels
or future conversations. Profile concerns are simulation assumptions; transcript
findings are separate reported evidence. No qualitative finding changes numeric
scores or supplies a treatment-effect estimate.

Extraction errors preserve validated session files, save a failed student report
with no unvalidated final conclusion, and mark the cohort run failed. The CLI exits
nonzero. Recorded source attendance and its cost are retained even if extraction
fails. RAG generation/repair remains bounded by the existing validation contract.

`InterventionRAG.analyse(..., on_session=callback)` invokes the callback exactly once
per validated session. Prior session generation is not repeated to save the next
session report. The model returns prompt-scoped evidence IDs using `GENERATION_SCHEMA`. Python
resolves them to exact source words/session numbers, rejects unknown IDs, and
validates the unchanged public `CONCLUSION_SCHEMA`. Existing callers without a
callback keep the same report structure.

`SchoolCMDPEnvironment.run_interventions()` adds `participation_completion_score`,
recorded appointments divided by cohort-planned appointments, including unassigned
students. This is an operational participation score, not retention or effectiveness.

## Not implemented

The current interfaces do not implement numeric attendance/engagement transitions,
withdrawal/re-entry dynamics, learned risk, causal support effects, optimized CMDP
policies or semantic accuracy guarantees for LLM conclusions.

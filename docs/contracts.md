# Current interfaces

This document describes interfaces that exist in the active code. More elaborate
policy, environment, evaluator and language contracts remain planned.

## Student input

`src.utils.school.load_students(path, num_students)` reads a deterministic prefix
of the synthetic population CSV and returns `StudentSimulation` records. It converts
required integer, float, boolean and nullable fields without modifying the source
file. Duplicate student IDs are rejected when a `School` is created.

The supplied synthetic rows inherit source profiles and are not independent
observations. Blank financial need and observed dropout values remain unknown.

## Mentor input

A `Mentor` declares:

- `mentor_id`;
- supported intervention types;
- maximum active students;
- availability and maximum sessions by month;
- current student IDs;
- per-session mentoring cost.

Custom mentors may be supplied to `School`. Otherwise helpers create default
tutoring mentors for every configured month.

## School configuration

`School(...)` accepts configurable students, mentors, CSV path, number of months,
budget, per-session mentor cost, sessions per student, students per mentor, support
type and random seed. Invalid negative resources and duplicate IDs are rejected.

## Simulation result

`School.run_simulation()` returns:

```python
dict[int, dict[str, str]]  # month -> student_id -> mentor_id
```

`School.assignment_history` contains detailed `MentorAssignment` records with the
student, mentor, support type, month, sessions and cost. `spent_budget` and
`remaining_budget` expose episode-level accounting.

The same student cannot be assigned twice within one month. Students are shuffled
without replacement each month and may be selected again in later months. Mentor
skill, monthly caseload, monthly session capacity and remaining episode budget are
hard constraints.

## Not implemented yet

The current contracts do not represent support acceptance, cancellation, actual
delivery, attendance or engagement transitions, simulated withdrawal, re-entry,
risk scores, policy observations, teacher notes or LLM extraction. Those interfaces
should be introduced with the corresponding executable stage, not as empty APIs.

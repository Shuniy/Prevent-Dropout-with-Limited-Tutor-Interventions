# Student–Mentor Longitudinal Intervention Histories

**Fully synthetic** study material; generated reproducibly with seed `20261102`.

## Contents

- **13** original intervention/support types.
- **130** fictional student histories (**10** per support type).
- **390** attended mentoring sessions (Markdown files), one file for each attended session.
- Each intervention student folder has **1–5** files. Exactly two students per type have each attendance count 1, 2, 3, 4 and 5.
- Every conversation is **30–60 minutes**, with a minute-by-minute timestamp and a Mentor/Student exchange at each minute.
- The top heading of every transcript is exactly `# Student`; no student names are used.
- The follow-up session explicitly references the preceding appointment's *exact agreed action*, with a report that it was tried, partly tried, not tried or uncertain. Follow-up activities build on earlier planning.
- A session file indicates **attended**, not simply scheduled. Missing/discontinued sessions have no Markdown file.

## Folder example

```text
02_tutoring/
  intervention_student_001/
    session_01_initial.md
    session_02_followup.md
  intervention_student_002/
    session_01_initial.md
    session_02_followup.md
    session_03_followup.md
    session_04_followup.md
    session_05_followup.md
```

The exact IDs and lengths vary; see `student_profiles.csv` rather than assuming the example lengths apply.

## Files

- `student_profiles.csv`: one row per student history, intervention type, attended count, session dates and retrospective series-end metadata.
- `session_manifest.csv`: one row per attended session, dates, duration, concern, linked prior-action status, proposed next step and relative path, plus SHA-256.
- `intervention_summary.csv`: counts by intervention type and number of attended sessions.
- `validation_report.json`: automated checks and exact counts.
- `generate_intervention_sequences.py`: generator, included for reproducibility.

## Research validity and responsible use

The dialogues, school activities and reported changes are **fictional and template-generated**. They are *not* records of real children, real mentors or measured treatment effects; even a completed five-session block does not establish that a support barrier was resolved or that dropout was prevented. Every transcript distinguishes in-session mentoring activity from unverified external support referrals. Attendance at a mentoring appointment is separate from overall school attendance. A student history ending after one session means **only one attendance is recorded**; it must not automatically be interpreted as school dropout or refusal. `series_end_status` is synthetic administrative metadata recorded separately from what was known at the time of each meeting.

This collection is useful for early *longitudinal continuity*, *information extraction*, *negation / uncertainty*, and *provenance* testing. However, it has intentionally repeated generator language, and category tags/CSV metadata are known labels: **do not give these indexes to an extraction model at evaluation time**. The same student history must never be split between training and testing. For robust scientific claims, independently author or review a held-out test set and validate the dialogue style against practitioner advice. Synthetic session progress must not be used as calibrated causal intervention effects.

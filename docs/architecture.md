# Current architecture

Two modes share typed CSV profiles, mentor resources and seeded allocation:

- `School.run_simulation()` is the original language-free monthly baseline. Students
  may be selected again in later months and all scheduled sessions are charged.
- `School.run_interventions()` gives each student one feature-matched programme,
  with five planned appointments total by default, and replays recorded conversations
  through the existing local Ollama RAG pipeline.

```text
synthetic student CSV → utils/school.py → StudentSimulation source records
                                              │
                              intervention/simulation.py
                           feature rules and initial profiles
                                              │
                               models/school.py allocation
                            skill, capacity and budget checks
                                              │
                       one student → one mentor → one history
                                              │
                            intervention/intervention.py
                         student–mentor programme controller
                                              │
                                    intervention/rag.py
                        spoken turns, earlier retrieval and memory
                                              │
                             validated session JSON immediately
                                              │
                       student final reports → cohort final report
```

## Active responsibilities

- `models/student.py`: source records and derived access/learning properties, plus a
  separate `StudentInterventionProfile`. The CSV record stays unchanged during replay.
- `models/mentor.py`: support skills, monthly session limits, caseload and session cost.
  Generated mentors are assumed generalists; caller-supplied skills stay enforced.
- `models/school.py`: seeded allocation, run reset, programme reservation, recorded
  attendance reconciliation, baseline and intervention entry points.
- `utils/school.py`: CSV conversion, configuration/ID validation, mentor creation and
  feasibility checks.
- `intervention/simulation.py`: versioned feature rules, initial scores, seeded history
  selection, attendance accounting and student/cohort final JSON writing.
- `intervention/intervention.py`: assigned-pair validation, one programme lifecycle,
  chronological RAG orchestration, immediate session persistence and final student
  report construction; also provides the shared atomic JSON writer.
- `intervention/rag.py`: student-history-scoped SQLite FTS5 retrieval, chronological
  validated memory, local structured Ollama output, quote/schema checks and bounded
  repair. The model selects evidence IDs; Python copies exact source quotes into
  the unchanged report schema. Its optional callback persists each validated result immediately.
- `main.py`: CLI and `SchoolCMDPEnvironment`, retaining monthly baseline progress and
  exposing intervention participation as recorded/cohort-planned appointments.
- `tests/`: source schema, baseline feasibility, RAG provenance and intervention checks.

## Intervention semantics

The primary concern is chosen by the highest severity among explicit hypothetical
feature rules. Initial scores include learning gap, assumed attendance/engagement,
support priority and an unavailable school-dropout risk. These are not trained risk
estimates. Rules select one corpus support type; a seeded draw selects a complete
history within that type. Secondary concerns stay in the profile. No concern means
a routine learning check-in. Missing matching histories or resources produce explicit
unassigned reports, rather than unrelated support.

One programme runs within its allocation month. Each student retains its mentor
and never starts another programme during the same run. Full doses reserve monthly
session capacity and budget before replay. Only source-recorded appointments are
charged; unused reservations become available in subsequent allocation windows.
A history may be reused for multiple simulated students, each with fresh RAG memory.

The corpus supplies one to five appointments. Fewer recorded appointments means an
incomplete programme with unknown reasons, not school dropout or refusal. Extraction
uses spoken turns, earlier passages and earlier validated findings only. Profiles,
retrospective CSV outcomes and later conversations are excluded from extraction
prompts. Findings may describe reported changes but never modify numeric scores or
create treatment effects.

Every validated session is saved before the next generation. Source hashes,
retrieval passages and validation failures remain auditable. Failed extraction
preserves earlier reports and makes the CLI exit nonzero. Final JSON contains both
administrative programme participation and evidence-backed qualitative conclusions.

## Remaining work

Dated state updates, numeric dynamics, simulated withdrawal, learned risk, causal
intervention effects, policy comparisons and optimized CMDP planning remain planned.
The current CMDP wrapper coordinates a constrained run and reports participation.

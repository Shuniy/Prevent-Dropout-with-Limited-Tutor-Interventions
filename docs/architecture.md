# Current architecture

The active application runs a monthly allocation baseline or a feature-matched
intervention workflow. Both use the same students, mentors, and resource checks.

```text
main → School → allocation helpers
          │
          └→ simulation → Intervention → InterventionRAG
                              │                 │
                           reports       SessionIndex + model client
                                                │
                                     transcripts + findings schema
```

## Responsibilities

| Component | Responsibility |
| --- | --- |
| Student | Source record and computed support needs |
| StudentSimulation | Additional assumed simulation inputs; inherits Student behavior |
| StudentInterventionProfile | Mutable state for one programme, separate from source records |
| Mentor | Skills and active caseload |
| MentorAvailability | Monthly resource limits |
| MentorAssignment | Planned allocation and recorded sessions/cost |
| School | Allocation, reset, reservations, attendance and budget reconciliation |
| Cohort simulation function | Match histories, coordinate programmes, save final results |
| Intervention | Verify the assigned pair, process one programme, save valid sessions |
| InterventionRAG | Process sessions chronologically with retrieved text and prior findings |
| SessionIndex | SQLite FTS5 retrieval restricted to one history and earlier sessions |
| Session / Passage | Small transcript and retrieved-text records |
| OllamaClient | HTTP structured generation |

Each production class lives in its own snake-case file under `src/models/` or
`src/intervention/`. Related enums and independent teaching examples stay grouped.
CSV loading, transcript parsing, schema validation, and JSON writing are functions.

## Dependencies and state

The CLI constructs the school and calls `run_simulation()` to allocate students
before calling `run_interventions()`. The cohort runner constructs the index and supplies
an explicit model client to RAG. Tests supply a fake client with the same `generate`
method. Domain records do not make network requests. There are no abstract base
classes, factories, dependency containers, or scoring wrappers.

Student needs determine support and admission priority. The cohort runner chooses a
matching history; one student retains one mentor for one programme. The school
reserves a full dose, then reconciles recorded attendance and actual cost. Capacity
renews monthly during planning. Intervention replays the saved assignments and
refunds unused reservations without changing admissions.

RAG reads the current conversation, earlier retrieved passages and earlier validated
findings. One schema validates each generated result before it is saved or enters
memory. Invalid generations are not retried. Earlier saved sessions survive failure.
Model findings do not modify source inputs or numeric need severity.

## Results and limits

Session files contain findings and functional IDs. Student reports contain support,
assignment, attendance, status, conclusion and errors. Run results contain students,
assignments and budget balances. There are no scores, audit trails, quote citations,
retrieval dumps, or progress logs. JSON is serialized before replacing a file.

School allocates each student at most once per run in both modes. Mentors can
serve different students in successive months. Intervention charges recorded
appointments, including when model processing fails. Neither mode estimates causal effectiveness or observed dropout.
The separate CMDP teaching example remains independent of production allocation.

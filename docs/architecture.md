# Current architecture

The dependency direction is `main → school → intervention`. School owns students,
mentors, allocation, the simulation clock, performance evaluation and school
reports. Intervention owns the confidential recorded programme and model analysis.
It does not import school or receive school domain objects or mutation callbacks.

```text
main ── constructs index + client + Intervention
  │
  └─ School.run_simulation(intervention)
       ├─ monthly allocation and programme requests
       ├─ Intervention.simulate(immutable request)
       │    ├─ private history assignment and programme memory
       │    └─ RAG → source index + explicit model client
       ├─ validate limited immutable result
       ├─ attendance, budget and runtime performance
       └─ monthly / student / final school reports
```

## Ownership and files

| Component | Responsibility |
| --- | --- |
| `school/student.py`, `student_simulation.py` | Source records and baseline inputs |
| `school/student_performance.py` | Current grades, school attendance/engagement, participation and reported outcomes |
| `school/needs.py`, `performance.py` | Shared need rules and conservative school evaluation |
| `school/performance_snapshot.py`, `monthly_evaluation.py` | Immutable before/after monthly records |
| `school/mentor*.py` | Mentor skills, caseloads, availability and assignment records |
| `school/loading.py` | CSV loading, validation, mentor creation and feasibility helpers |
| `school/school.py` | Facade, school state, requests, exactly-once result application and accounting |
| `school/simulation.py`, `reports.py` | Monthly orchestration and school exports |
| `intervention/intervention_request.py`, `intervention_result.py` | Explicit immutable module boundary |
| `intervention/history_assignment.py` | Validate/catalogue histories and seeded selection |
| `intervention/student_intervention_profile.py` | Private request/history binding, session progress, validated findings and errors |
| `intervention/intervention.py` | Execute one programme and return an allowlisted result |
| `intervention/rag.py`, `session_index.py` | Chronological analysis and earlier-session retrieval |
| `intervention/session.py`, `passage.py` | Source-history session and retrieved passage records |
| `intervention/ollama_client.py` | Structured HTTP generation |
| `intervention/transcripts.py`, `findings.py`, `reports.py` | Transcript parsing, findings validation and private persistence |

Each production class/dataclass has its own file. Both module packages export their
public records and facade explicitly. Shared enums/constants have no school service
dependency. No service framework or dependency container is used.

## Monthly state and resource policy

A fresh run restores source-derived runtime performance, initial mentor caseloads,
accounting, snapshots and seeded choices under a fresh run ID. Every month:

1. Read current performance and save the before snapshot.
2. Allocate by current need, skills, capacity, session limits and remaining budget;
   reserve the full planned dose for the entire month's plan.
3. Build requests and simulate newly admitted programmes.
4. Validate result identity/counts and reject duplicates before school mutation.
   Charge recorded appointments and release unused reservations.
5. Apply public outcomes, recompute needs and save after snapshots for all students.
6. Save the monthly report, then advance the clock.

The default is twelve months; any positive count is supported. Each student gets
one mentor and at most one programme per run. A programme fits within its admission
month; five planned sessions means five total, never five each month. Mentors can
serve new students in later months. Refunds may fund later admissions, but never
refill the current month's plan. `allocate_programmes()` separately produces an
allocation-only plan, reserving planned costs without claiming attendance.

## Performance and confidentiality

Source grades, demographics and initial assumptions are preserved. School keeps
current metrics and support participation separately. Reported categorical outcomes
are retained as reports; they do not establish observed school attendance, increase
grades or automatically change a numeric need. Unknown/conflicting/failed extraction leaves
relevant measures unchanged and records why. Source and runtime needs use the same
rules. Numeric transitions or a calibrated intervention score need an explicit
school policy before implementation; predictive-model retraining is outside scope.

Intervention binds a coherent support-matched history to run/programme/pair identity
and processes recorded sessions in order, up to the planned limit. Selection uses
local seeded RNGs, reset for each fresh run; corpus reuse is permitted. Every
programme gets fresh memory, including after mentor reassignment. Retrieval sees
only earlier sessions of that source history. Prompts exclude headers, profiles,
retrospective labels and future sessions. Invalid generation never enters memory.
Valid earlier findings survive failure privately; recorded attendance is independent
of extraction success. Missing compatible history returns an unavailable result.

School receives only identity, counts, programme/analysis status and three enumerated
outcome indicators. No transcripts, source paths, history IDs, private errors,
detailed findings or free-text conclusions enter school state or reports. Private
persistence is optional and uses a separate destination; school exports never link
to it. The CLI rejects equal or nested public/private directories; Python composition
code must choose separate directories too. School uses only `simulate(request)` on
the injected intervention and never inspects its private state.

This is a module/report confidentiality boundary, not an OS access-control boundary.
The standalone RAG command remains a private analysis/developer tool. Neither mode
estimates causal effectiveness or observed dropout.

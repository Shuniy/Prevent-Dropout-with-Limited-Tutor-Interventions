# Current architecture

The default CMDP workflow uses the `main → school` entry point:
`python -m src.main` loads a scenario and calls school experiment execution.
Each world constructs the existing `School` and calls `School.run_cmdp(policy)`.
`CMDPSimulation` coordinates the monthly cycle through the small `AllocationPolicy`
interface; `CMDPEnvironment` owns simulated condition, copied resources and budget.
`school.cmdp_reports` handles summary/plot export independently of execution.
The environment freezes monthly mentor capacities and eligible waiting in its
records. `cmdp_metrics` combines those records with the initial snapshot to export
month-zero and monthly summaries; `--print-monthly` optionally prints representative
development worlds. Waiting counts survived, unsupported months only, consistently
in environment snapshots and group audits.
Policies receive immutable decision snapshots, never the environment or future draws.
The five baseline policies separate student ranking from one shared greedy matcher
(`baseline_policy` → `greedy_matching` → `constraints`). Random ordering is over
students, independent of compatible mentor edges. One source school is built per
world and copied into each policy's environment. `baseline_validation` checks
resource ledgers and complete experiment grids before held-out runs, while
`baseline_exports` writes portable tables and eight baseline figures. Existing
optimizer/fairness policies are opt-ins, outside the Step 2 default. See
[baseline experiment contract](cmdp_baselines_v1.md).
The Step 4 fairness policy reuses the retention planner's candidate, resource and
validation functions in a time-indexed remaining-window MILP. The decision snapshot
adds the preannounced mentor calendar, with no future student truth.
`fairness_window` freezes one audit axis and broad condition cohorts;
`CMDPSimulation` records independent admission ledgers for every policy.
`fairness_audit` evaluates actual recorded access separately from the solver, and
`fairness_experiments` runs the frozen paired target/budget/effect grid. See
[the Step 4 formulation](cmdp_fairness_v1.md).
`school.observation_adapter` imports only the existing immutable InterventionResult
contract and does not invoke the extraction pipeline. There is no separate CMDP
package. See [CMDP implementation](cmdp-implementation.md) for the module map.

The feedback path, `School.run_cmdp_feedback` → `ClosedLoopCMDPController`,
routes routine monitoring through the deterministic synthetic-grammar extractor.
Only programme notes from committed interventions reach the injected LLM extractor.
Both channels preserve source availability and the mode's note quality; initial
and later monitoring still update every student's beliefs and risk without model
calls. The optional monthly note cap selects programme events only, with the same
selection for matched-note controls. Programme extraction failures remain failures,
without substituting deterministic facts. Older saved results used population-wide LLM
extraction and, when capped, population-wide note selection.

Recorded-intervention Python APIs use the dependency direction `school → intervention`. School owns students,
mentors, allocation, the simulation clock, performance evaluation and school
reports. Intervention owns the confidential recorded programme and model analysis.
It does not import school or receive school domain objects or mutation callbacks.

```text
Python caller ── loads sessions + constructs client + Intervention
  │
  └─ School.run_simulation(intervention)
       ├─ monthly allocation and programme requests
       ├─ Intervention.simulate(immutable request)
       │    ├─ private history assignment and programme memory
       │    └─ SimpleLLM → all selected sessions + explicit model client
       │         (optional RAG → source index + per-session model calls)
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
| `intervention/simple_llm.py` | One structured extraction of all selected spoken sessions, with no retrieval |
| `intervention/rag.py`, `session_index.py` | Chronological analysis and earlier-session retrieval |
| `intervention/session.py`, `passage.py` | Source-history session and retrieved passage records |
| `intervention/semantic_validation.py` | Source/identity checks, pinned action evidence and separate model semantic review |
| `intervention/ollama_client.py` | Structured HTTP generation |
| `intervention/transcripts.py`, `findings.py`, `reports.py` | Transcript parsing, JSON validation and private persistence |

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
local NumPy generators from `utils.constants.create_rng`, reset for each fresh
run; corpus reuse is permitted. Teaching examples create a seeded generator per
school or main invocation and pass it to their students. Every
programme gets a fresh extraction, including after mentor reassignment. The default
passes all selected sessions in one call without creating a retrieval index. It
validates the complete timeline and each entry's semantics before persisting private session files.
The final timeline entry is the final conclusion. Timeline entries are retrospective
reconstructions, with all selected sessions visible; the prompt requests findings as
of each session but cannot enforce temporal isolation. Optional RAG retains its
per-session calls, earlier-only retrieval/memory and partial valid findings on failure.
Each entry adds an independent review call after JSON and deterministic source checks.
Review uses only an as-of source prefix and rejects unsupported/contradictory findings;
it remains a fallible model judgment. RAG pins original action evidence with source dates
and reported status history separately from retrieved excerpts and generated summaries.
Findings track immutable action IDs/original wording, evidence-backed progress,
intended component IDs, direct activity and external service status independently.
A completed review cannot complete its underlying action; requested support is not receipt.
Both receive allowlisted descriptive headers (intervention type, date, stage) alongside
spoken turns. Profiles, retrospective outcome labels and sessions beyond the planned
limit are excluded. Simple session records explicitly identify conversation positions
and earlier source session numbers; prompts live in `intervention/prompts.py`. Recorded attendance is independent of extraction success. Missing compatible
history returns an unavailable result.

School receives only identity, counts, programme/analysis status and three enumerated
outcome indicators. No transcripts, source paths, history IDs, private errors,
detailed findings or free-text conclusions enter school state or reports. Private
persistence is optional and uses a separate destination; school exports never link
to it. Python composition code must choose separate public/private directories. School uses only `simulate(request)` on
the injected intervention and never inspects its private state.

This is a module/report confidentiality boundary, not an OS access-control boundary.
Standalone simple and RAG commands remain private analysis/developer tools. Neither mode
estimates causal effectiveness or observed dropout.

## Research evaluation (Step 6)

`src/evaluation/research_experiments.py` stages frozen-protocol experiments over
`ClosedLoopCMDPController`; it does not implement a second environment. The
controller accepts an optional explicit student-to-NoteQuality map for synthetic
group-dependent note channels. It passes only observable events to the renderer,
never hidden states or audit attributes to the LLM. Every policy generates future
notes from its own committed trajectory under shared keyed exogenous streams.

`FairRobustPlanner` reuses the fairness window, candidate/resource construction,
rollout model and validators. A continuous eta bounds total benefit under each
scenario; fairness shortfall, cost and deterministic tie priorities remain shared.
Finite belief scenarios use only estimated decision inputs and documented
missingness/freshness. Evaluator-only scorecards join truth after execution.
Risk scoring uses the conditional WAIT reference, not treated terminal labels.

Configuration/source hashes gate execution. Explicit amendments replace the single
input manifest and require a fresh pilot. CSV summaries, compressed complete episode traces,
configuration-complete inference caches and generated scientific figures make
results inspectable. See [the protocol](research_evaluation_protocol.md).

# Implementation status and next work

## CMDP v1

CMDP now lives directly in the school module, with `School.run_cmdp(policy)` and
the shared `main.py` entry point. Policy interfaces, monthly coordination,
environment dynamics and reporting have separate responsibilities.

Implemented and tested: finite-horizon synthetic environment, hard realized
budget/mentor/appointment constraints, five baselines, terminal-value monthly MILP,
exact tiny Bellman reference, paired effect/budget sweeps, frozen group audits,
rolling-window lexicographic fairness MILP, and isolated observation contracts.
Waiting-time accounting excludes the withdrawal month in both student snapshots
and group audits. Complete month-zero and monthly episode summaries are exported,
with optional `--print-monthly` output for representative development worlds.
See [execution results](cmdp-results-v1.md) and [usage](cmdp-implementation.md).

Step 2 baseline completion adds student-only random ordering, shared greedy
matching, full baseline tests, a development validation gate, complete CSV/figure
exports and episode-level SD/percentage-point comparisons. The default now runs
only the five baselines. Step 2 retained optimization/fairness as optional research
code; Step 4 now extends fairness while keeping that default comparison. See
[Step 2 verification and acceptance checklist](cmdp_baselines_v1.md).

Step 4 implements integer minimum coverage, one configured authorized audit axis,
frozen condition cohorts, strict/soft modes, tentative remaining-window schedules,
independent admission audits and paired target/budget/effect experiments. See
[the formulation](cmdp_fairness_v1.md) and [execution report](cmdp_fairness_v1_results.md).

Deferred: globally optimal stochastic fairness scheduling, repeated programmes,
and causal calibration. The
rolling-window policy uses an optimistic enrollment projection and WAIT-based
future values. Step 5 adds observable records, note-supported extraction, estimated
beliefs and WAIT-continuation risk to the shared closed-loop controller; its real
Qwen executions are documented in [the Step 5 report](cmdp_llm_feedback_v1_results.md).

Step 6 adds finite-scenario robust fairness allocation, independent extraction
scoring, evaluator-only belief/risk metrics, paired held-out experiments and
bounded sensitivities. The [versioned protocol](research_evaluation_protocol.md)
separates D-matched uncertainty comparisons from actual sparse LLM diagnostics.
Consult [the executed research report](../results/research_evaluation_v1/research_results.md)
for results, scientific limitations and remaining acceptance gaps.

## Working now

- Separate `school` and confidential `intervention` modules, with explicit exports
  and dependency direction `school → intervention` for recorded-intervention APIs.
- Typed source loading and shared need rules for baseline/current performance.
- School-owned monthly allocation/intervention/evaluation/reporting, twelve months
  by default, one mentor/programme per student and reusable monthly mentor capacity.
- Planned-dose reservations, recorded-session charges and refunds available to
  later months without refilling the current month.
- Immutable request/result records, identity/count validation and exactly-once
  school result application.
- Coherent support-matched history assignment with local seeded selection,
  chronological SQLite retrieval, fresh programme memory and explicit model clients.
- Independent seeded teaching-example streams, shared with each example's students,
  using the same default seed convention as school and intervention runs.
- Default all-sessions LLM extraction with one generation per intervention, no
  retrieval index and the existing timeline/conclusion and private output shapes.
- Version 2 findings with stable action identity, six explicit completion statuses,
  original source wording/dates and cited progress reports. Intended support, direct
  activity and requested external support are separate components.
- Deterministic evidence/identity checks after JSON validation, plus one separate
  model semantic review per entry before acceptance. Review remains fallible.
- RAG pins source-backed actions and historical status reports independently of
  retrieval; generated summaries remain provisional.
- Preserved optional session-by-session RAG (`method="rag"` in the Python API),
  partial private findings for RAG and separate programme/analysis statuses.
- Executable one-intervention comparison notebook with saved live reports, call
  counts, timings, outcome agreement and transcript-based reference checks.
- School runtime performance and immutable monthly before/after evaluations;
  reported categorical outcomes remain separate from observed numeric metrics.
- Monthly/student/final school JSON with an explicit result allowlist; optional
  private session/conclusion persistence to a separate destination.
- Fresh run identities and reset of baseline performance, initial caseloads,
  accounting, results, snapshots and seeded selection.
- Allocation-only Python API, private standalone simple/RAG commands and offline fake-client tests.
- Independent agent, Markov, MDP and CMDP examples without import side effects.

## Current checks

Use Python 3.12 or 3.13 and run `python -m unittest discover -s tests`. Tests cover
source/current needs, resource limits, monthly feedback/refunds, no repeat admission,
immutability, identity/count rejection, duplicate application, baseline preservation,
confidential exports, history isolation/chronology, short/missing histories,
unknown/failed analysis, reset/repeat, zero-agent runs, CMDP CLI and teaching examples.
Evidence regressions cover immutable actions, source/cutoff errors, partial work,
review-versus-task rejection, scoped delivery/helpfulness, missing citations, malformed
reviews, rejection before persistence and action evidence retained without retrieval.
The shared fake client requires no live model. A live Ollama run is optional.

## Future work

Numeric state transitions and a calibrated intervention score need a separate
specification: permitted fields, categorical mapping, scale, parameters, bounds,
and unknown/failure behavior. School would own such transitions as explicit
simulation assumptions. No numeric improvement is inferred from current findings.

Programmes spanning school months require explicit session schedules and retained
caseloads. Repeated programmes or reassignment require a separate eligibility policy
and must not implicitly transfer private memory. Predictive-model training, simulated
withdrawal in the recorded-intervention workflow, causal effect estimation and
LLM-driven closed-loop fairness evaluation remain separate future work. The
CMDP policy comparisons, estimated-state feedback and Step 6 research evaluation are implemented;
the recorded-intervention allocator remains a priority heuristic.

## Preserved research material

Source datasets, corpus generators, notebooks and archives have not moved. Historical
imports/results may need updating before reuse. Research specifications describe
possible future work, not the active interface. Missing appointments do not prove
dropout; synthetic dialogue does not measure real-world intervention effects.

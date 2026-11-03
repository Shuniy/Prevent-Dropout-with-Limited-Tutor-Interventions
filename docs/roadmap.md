# Implementation status and next work

## Working now

- Typed CSV student loading, computed support needs, and separate mentor resources.
- Monthly allocation baseline with repeat eligibility and resource limits.
- Need-priority intervention allocation: one mentor and one programme per student.
- Matching synthetic histories, up to the configured total appointment count.
- SQLite retrieval from earlier sessions of the same history and chronological
  structured findings through local Ollama.
- One generation attempt per session, schema validation, immediate session saving,
  partial-result preservation, and explicit failure status.
- Planned-dose reservations, recorded-session costs, and unused-resource release.
- Minimal session/student/run JSON, direct CLI entry points, and offline feature tests.
- One production class per file; explicit dependencies and small helper functions.
- Separate agent, Markov, MDP, and CMDP examples without import-time execution.

The active workflow has no analytics, scores beyond allocation need severity,
traceability metadata, citation validation, repair loops, or progress logging.
The production allocator is a priority heuristic; optimization exists only in the
independent teaching examples.

## Current checks

Run `python -m unittest discover -s tests` for source records, needs, resource limits,
priority, history isolation, chronology, findings, failures, entry points and examples.
The suite uses a shared fake model and does not need Ollama. A live one-session CLI
run checks the local model separately. The README contains setup and run commands.

## Future work — not implemented

Numeric student-state transitions, simulated withdrawal, trained risk models,
causal intervention effects, policy comparison, fairness constraints and research
experiments remain separate future decisions. Do not introduce scaffolding for
these into the current working workflow.

## Research references

Notebooks, datasets, corpus generators, archived outputs, and older research
specifications remain preserved reference material. Their imports and result
expectations may predate the current interfaces. They are not verification of the
current code. See the README and `contracts.md` for active commands and behavior.

Missing appointments do not prove school dropout, and historical course failure
is not observed dropout. Synthetic dialogue progress does not measure real-world
intervention effectiveness.

# Development roadmap

Stages describe the order of implementation, not Python files or classes. Finish
and verify one useful increment before adding the next. Keep the detailed research
requirements in `CODEX_IMPLEMENTATION_PROMPT_v2.md` as reference; its old paths and
raw-source workflow no longer describe the current setup.

| Stage | Deliverable | Status / completion check |
| --- | --- | --- |
| 1. Data foundation | Load retained CSVs; expose typed records; explore in Jupyter | Partial; synthetic student loading and typed records work, while the earlier data-service layer is not active in this tree |
| 2. Baselines and population sampling | Reproduce course-failure baselines; sample whole anchor profiles within a split | Planned; check held-out metrics and lineage inheritance |
| 3. Simulation | Small structured environment with observations, support delivery, resources and event logs | In progress; seeded 12-month mentor allocation enforces support type, monthly caseload, session limits and total cost; feature-based scenario concerns now select one RAG history per student with five appointments total, actual-session costs and JSON reports; numeric transitions remain planned |
| 4. Allocation and evaluation | Simple usual-support, random and rule-based policies; compare outcomes and resource use | In progress; random feasible allocation works, while comparison policies and outcome evaluation remain planned |
| 5. Feedback and risk | Update estimated state from dated observations; fit and validate simulated-withdrawal risk | Planned; prevent future/hidden information leakage |
| 6. Extended experiments | Fairness constraints, alternative simulated worlds, sensitivity analysis and optional language input | Planned; add complexity only after simpler comparisons work |

The first simulation increment should use structured observations and non-risk
policies. Any unavailable risk score must remain explicitly unavailable. Later
stages must continue to distinguish historical course failure, assumed simulation
withdrawal and real school dropout.

The data foundation includes `Student` and `StudentSimulation` schema models.
The first Stage 3 increment loads student agents from the synthetic population,
adds configurable mentor agents and runs deterministic monthly assignments for a
12-month default schedule. Each assigned student receives five sessions per month;
students are randomly shuffled each month with repeat eligibility across months,
and per-session mentoring costs consume a total budget. Session duration is not
modeled. Data validation remains in the data layer, while mutable episode
transitions and support outcomes remain part of Stage 3.

The next Stage 3 increment now connects CSV-derived hypothetical concerns to
synthetic longitudinal intervention histories. `School.run_interventions()` assigns
one mentor and one programme per student, defaults to five appointments total, and
uses the recorded source length for participation. It writes each validated session
immediately plus student and cohort final JSON. Generated mentors are assumed
generalists; custom skills, monthly capacity and budget are enforced. The existing
monthly allocation-only baseline remains available separately.

Feature rules, initial scores and concerns are declared simulation assumptions.
No numeric treatment effects or school-dropout labels are inferred. The CMDP wrapper
reports appointment participation only. Dated structured observations, numeric
state transitions and meaningful outcome-policy comparisons remain the next bounded
simulation work.

## Organization rules

The longitudinal pipeline in `src/intervention/rag.py` and
`notebooks/intervention_rag.ipynb` supplies history-scoped SQLite BM25 retrieval,
chronological validated JSON memory and local Ollama extraction. It is now invoked
by `src/intervention/simulation.py` for feature-matched replay. Dataset scores,
retrospective CSV labels and future sessions do not enter extraction prompts.
This does not complete Stage 5 or 6: state feedback, learned risk and held-out
semantic extraction evaluation remain planned. Independently authored histories
are still needed before making research accuracy claims.

Verification: all 33 source-model, baseline, RAG and intervention tests pass under
full unittest discovery. These cover five-total-session scheduling, partial source
participation, actual costs, mentor continuity, no second programme, deterministic
replay, shortfalls, immediate persistence, extraction failures and participation
scoring. The local Ollama two-student seed-7 smoke run also completed with six
validated session reports (five plus one), no citation repairs and actual cost six.
Synthetic replay is not evidence of real intervention effectiveness.

- Put input data in `data/`, settings in `configs/`, implementation in `src/`,
  checks in `tests/`, documentation in `docs/`, and run artifacts in `results/`.
- Name modules after their responsibility; avoid stage runners, stage base classes
  and empty folders for future work.
- Prefer functions and small records. Add classes only for meaningful state or a
  useful shared interface. Keep existing data validation where it prevents mistakes.
- Keep a single current run guide in the root README. Historical completion logs
  belong in `archive/` and do not prove that the current code passed.

The removed raw downloads are not restored. The current foundation validates the
retained generated package internally. Repeating the original raw-data audit would
require those original inputs separately.

Use [Guidance.md](../Guidance.md) for readable pandas/NumPy conventions and function
documentation. Update it and the README, including workflow diagrams, with every
implemented stage. Notebooks explain analysis; reusable functions belong in `src/`.

## Notebook-first organization

The supplied layout is adapted in [architecture.md](architecture.md). Data now
lives in processed, synthetic and external subdirectories; tests mirror source
responsibilities. `src/main.py` runs the small RAG intervention example by default; `--allocation-only`
runs the monthly baseline. Numeric state/outcome transitions remain planned.

The assigned student–mentor session lifecycle now lives in
`src/intervention/intervention.py`. The cohort simulator delegates each programme
to this controller and retains allocation, resource reconciliation and aggregation.

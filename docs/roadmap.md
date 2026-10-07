# Development roadmap

Stages describe the order of implementation, not Python files or classes. Finish
and verify one useful increment before adding the next. Keep the detailed research
requirements in `CODEX_IMPLEMENTATION_PROMPT_v2.md` as reference; its old paths and
raw-source workflow no longer describe the current setup.

| Stage | Deliverable | Status / completion check |
| --- | --- | --- |
| 1. Data foundation | Read the existing generated CSVs directly; expose separate consumer records | Implemented; run the population summary and data tests |
| 2. Baselines and population sampling | Reproduce course-failure baselines; sample whole anchor profiles within a split | Next; check held-out metrics and lineage inheritance |
| 3. Simulation | Small structured environment with observations, support delivery, resources and event logs | Planned; verify event order, reproducibility and capacity limits |
| 4. Allocation and evaluation | Simple usual-support, random and rule-based policies; compare outcomes and resource use | Planned; evaluate on frozen held-out settings |
| 5. Feedback and risk | Update estimated state from dated observations; fit and validate simulated-withdrawal risk | Planned; prevent future/hidden information leakage |
| 6. Extended experiments | Fairness constraints, alternative simulated worlds, sensitivity analysis and optional language input | Planned; add complexity only after simpler comparisons work |

The first simulation increment should use structured observations and non-risk
policies. Any unavailable risk score must remain explicitly unavailable. Later
stages must continue to distinguish historical course failure, assumed simulation
withdrawal and real school dropout.

## Organization rules

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

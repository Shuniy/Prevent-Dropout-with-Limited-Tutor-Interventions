# Project organization

Notebooks are the main research workspace. They explain steps, display pandas
DataFrames and plots, and call reusable functions in `src/`. Console commands
call those same functions; avoid copying analysis or simulation rules into scripts.

```text
notebooks ───────┐
                ├── src/experiments/runner.py ── src/data/ ── data/
main.py → CLI ───┘              ↑
                         configs/default.toml
```

## Existing responsibilities

- `data/processed/students/` holds the retained source-anchor table;
  `data/processed/splits/` holds its fixed split assignments.
- `data/synthetic/populations/` holds the supplied fixture;
  `data/synthetic/simulator_states/` holds environment-only hidden parameters.
- `data/external/` holds historical outcome/reference tables and the dictionary.
  Directory separation does not itself authorize policy access.
- `src/data/dataset.py` resolves table names to paths. An explicitly supplied
  directory can be either the organized data root or a legacy flat CSV folder.
- `src/data/access.py` preserves consumer boundaries. Policies receive allowlisted
  observations, not raw reference outcomes or hidden environment parameters.
- `src/experiments/runner.py` returns tables for both notebooks and the CLI.
  The simulation function currently validates reset only with `dry_run=True`.
- `tests/` mirrors active source responsibilities. Run discovery from `tests/`.
- `configs/` holds shared TOML configuration; relative data paths resolve against
  the config file. Notebooks can pass an absolute config path from any directory.
- `results/` holds generated artifacts and is ignored by Git. Use `runs/`, `tables/`,
  `figures/`, `metrics/` and `logs/` as each workflow needs them. The existing
  exploration notebook retains its `results/exploration/` output location.

The project is installed in editable mode from this checkout. Data remains outside
Python packages, and imports remain `src.data...` for existing notebook compatibility.
The nine CSV inputs were moved without modifying their contents.

## Growth from the supplied sample

Add modules when their stage becomes executable, rather than empty implementations:

| Planned responsibility | Source location | Notebook |
| --- | --- | --- |
| Course-failure baseline | `src/models/` | `02_baseline_analysis.ipynb` |
| Whole-profile sampling | `src/population/` | `03_population_validation.ipynb` |
| State, transitions, support and resources | `src/environment/` | `04_simulator_analysis.ipynb` |
| Policies, fairness, estimated state | `src/policies/`, `src/fairness/`, `src/state_estimation/` | Focused analysis notebooks as needed |
| Metrics and paired comparisons | `src/evaluation/` | `05_results_analysis.ipynb` |
| Optional notes and extraction | `src/language/` | Added after structured feedback works |

Scenario, policy and experiment settings can grow under `configs/` when their
consumers exist. Keep research designs in `docs/` and run outputs under `results/`;
add a separate `experiments/` directory only for substantial experiment protocols.
Add `data/raw/`, note data and `corpus/` when those inputs are actually introduced.
Historical references in `archive/` and `docs/history/` retain their original paths.

# Notebook workflow

Start Jupyter from the project root with the project environment activated:

```sh
python -m pip install -e .
python -m notebook
```

Choose that environment as the kernel. Restart and run all cells in order before
saving. Keep exploration, explanation and plots here; put reusable loading,
simulation and evaluation functions in `src/`. Never depend on another notebook's
kernel state. Input CSVs remain read-only; write derived artifacts to `results/`.

| Notebook | Current scope |
| --- | --- |
| `01_data_exploration.ipynb` | Working data exploration and policy-safe feature table |
| `04_simulator_analysis.ipynb` | Working reset readiness check; no simulated episodes yet |

Numbers 02, 03 and 05 are reserved for baseline analysis, population validation
and results analysis as those stages are implemented. Notebooks may be launched
from the project or notebooks folder; editable installation also makes reusable
functions importable from other working directories.

Use `from src.experiments.runner import run_simulation` and
`run_simulation(dry_run=True)` for readiness. The console equivalent is
`python main.py simulate --dry-run`. Full simulation currently reports that
transitions have not been implemented.

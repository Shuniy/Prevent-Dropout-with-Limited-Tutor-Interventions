# Student support research

The project uses the existing generated dataset directly. There is no dataset
builder, preprocessing command or intermediate prepared copy.

Implementation progresses in stages documented in [the roadmap](docs/roadmap.md).
Files and classes are named by responsibility, not by stage number. The current
foundation loads student context, policy observations and environment reset state.
Simulation transitions, allocation policies and experiments are not implemented yet.

## Structure

```text
data/generated/       Existing dataset CSVs, unchanged
src/
  __main__.py         Read-only population summary
  data/
    dataset.py        Read CSVs and convert values into typed records
    access.py         Policy, context, environment and evaluator interfaces
    contracts.py      Records and validation rules
tests/                Dataset and contract tests
docs/                 Roadmap, contract guide and research references
results/              Historical/local run outputs; not project inputs
archive/              Historical study reports, analyses and workbook
```

New code belongs under `src/` by responsibility. Add configuration files only when
runtime settings are needed. Avoid empty modules for future work and stage runners.

## Run

From this folder, with Python 3.12 or newer:

```sh
python3 -B -m src
python3 -B -m unittest discover -s tests -v
```

The current implementation uses only the Python standard library. No data
preparation or dependency installation is required.

```python
from src.data.access import PolicyStore, EnvironmentStore, model_features

students = PolicyStore().load_reset("train")
features = model_features(students[0])
initial_states = EnvironmentStore().load_fixture("train")
```

Loaders default to `data/generated/`; an optional directory argument supports a
copy elsewhere. The default population is the fixed synthetic fixture. Choose
`cohort="primary"` for Portuguese source anchors or `cohort="sensitivity"` for all
retained anchors. Policy features are limited to allowed context fields. Hidden
state and historical outcomes have separate interfaces.

## Dataset

The files originally in `student_cmdp_study/data/` now live in `data/generated/`.
Their contents are unchanged.

| File | Use |
| --- | --- |
| `synthetic_student_population.csv` | Default population: 2,000 generated students, split 1,200/400/400 |
| `student_dataset.csv` | 674 anchor profiles, including 649 primary Portuguese profiles |
| `simulator_hidden_truth.csv` | Environment reset parameters; static future draws excluded from reset state |
| `student_outcomes_reference.csv` | Evaluator-only historical outcomes |
| `subject_records_reference.csv` | 1,044 subject reference rows |
| `split_manifest.csv` | Retained anchor split assignments |

Higher-education tables and the variable dictionary remain available as references.
The application does not need deleted raw sources, historical reports, or previous
run outputs. Loaders do not repair, regenerate or write dataset values.

The generated population contains repeated source profiles, not 2,000 independent
observed students. Observed school dropout and verified income remain unknown.
Historical course failure is not a school-dropout label. Generated attendance and
engagement remain withheld from policy inputs until an observation mechanism exists.

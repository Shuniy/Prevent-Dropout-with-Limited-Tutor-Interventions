# Student support research — Stage 1

Stage 1 implements school-data ingestion, lineage validation, immutable typed
contracts, and separate policy, environment and evaluator data interfaces. All
current Stage 1 tables are together under `results/stage1-v1/data/`, with role
subfolders to prevent accidental outcome/truth leakage. Original downloads,
`student_cmdp_study/`, and completed Stage 0 outputs are preserved.

```sh
python -B -m src.data.stage1 --source-root . \
  --manifest configs/stage1_inputs.v1.json --output results/stage1-v2
python -B -m src.data.stage1 --output results/stage1-v1 --verify
python -B -m unittest discover -s tests -v
```

Build into a new version name; existing outputs cannot be overwritten. Stage 1 uses
only the Python standard library, tested on the existing pinned Python 3.12.14
environment. It adds no dependencies. The source manifest records ten explicit
inputs and their hashes; it never scans a mixed data/output folder for inputs.

The default cohort is 649 Portuguese anchors; 674 profiles are available only as an
explicit sensitivity cohort. The 2,000 bootstrap rows are retained as fixed
fixtures, not new independent students. All 1,044 subject references and split
lineage are checked against raw data. The known 25 math-only evaluator blanks are
repaired in the new result only.

Policy reset features default to first-period grade, prior failures and study-time
category. Generated attendance/engagement remain withheld until the later
observation mechanism supplies authorized measurements. Unknown income,
disadvantage and observed school dropout stay null. Sex is audit-only; math G1,
late grades, absences, hidden response/hazard and future draws cannot enter the
policy interface. Source questionnaire dates are unknown; reset availability is
an explicit hypothetical first-period assumption.

```python
from src.data.access import PolicyStore, model_features

students = PolicyStore("results/stage1-v1").load_reset("train")
features = model_features(students[0])  # explicit allowlist; excludes IDs/audit groups
```

Use `ContextStore` only for initialization/auditing, `EnvironmentStore` for hidden
reset state, and `EvaluatorStore` for historical outcomes/reference diagnostics.
The loaders and immutable records enforce application data-flow boundaries;
they do not sandbox malicious Python code with filesystem access.

See [Stage 1 completion](docs/STAGE1_COMPLETION.md),
[contract guide](docs/STAGE1_CONTRACTS.md), and
[dataset organization](docs/DATASET_ORGANIZATION.md).
Schemas for later extraction, updating, risk prediction, events and allocation are
implemented; those services and the sequential simulator are not yet implemented.
No real school-dropout predictor or causal intervention effect is claimed.

## Retained Stage 0 workflow

Stage 0 repairs reproducible data preparation. The original downloaded sources and
`student_cmdp_study/` remain the immutable baseline. The repaired scripts live in
`src/data/`; do not run the original builder in its baseline folder.

This stage reproduces course-failure descriptive models and synthetic reset
fixtures. It does **not** implement a sequential simulator or establish a real
school-dropout predictor or intervention effect.

## Run

Use Python 3.12.14 with the pinned dependencies in `requirements.txt` (NumPy 2.3.5,
pandas 2.2.3). Run from this project folder. No network, model credentials, Node,
Excel, workbook renderer, or workbook library is required for data validation.

```sh
python -B src/data/build_study.py \
  --source-root . \
  --research-plan docs/references/school_dropout_research_plan.md \
  --source-manifest configs/raw_sources.v1.json \
  --output-root results/stage0-v2

python -B src/data/verify_and_package.py \
  --source-root . \
  --research-plan docs/references/school_dropout_research_plan.md \
  --output-root results/stage0-v2 \
  --archive results/stage0-v2.zip
```

`results/stage0-v1/` is the first completed repaired result. Each subsequent build
requires a new output name. Existing outputs and archives are never overwritten.
All 22 raw inputs, the separate research reference, their hashes, and destination
paths are checked before creating output. The builder works in a temporary sibling
directory and publishes only after data validation and final input-hash checks.
Failures remove the temporary result. `COMPLETED.json` identifies the exact completed
artifacts and their hashes. Packaging includes only those bounded, direct artifacts;
it ignores unrelated files, nested copies, old archives and caches.

The manifest uses paths relative to `--source-root`, with SHA-256 identities. Copy
the source layout to another folder and change that argument to relocate it; the
research reference can be supplied separately. The v1 source set and seed are
intentionally fixed to reproduce the audited baseline; changed sources require a
new manifest version and review. CSVs in mirror/quarantine folders are audited only,
not pooled into the school cohort. See `docs/DATASET_ORGANIZATION.md`.

Optional saved workbook XML inspection is separate:

```sh
python -B src/data/verify_and_package.py \
  --source-root . \
  --research-plan docs/references/school_dropout_research_plan.md \
  --output-root results/stage0-v1 \
  --workbook student_cmdp_study/student_analysis.xlsx
```

This checks saved sheet/formula structure, not recalculation or visual rendering.
The baseline's earlier claims of visual review are preserved only as historical
artifacts, never copied into new verification evidence.

## Verify the Stage 0 gate

```sh
python -B -m unittest discover -s tests -v
python -B tests/reproduce_stage0.py \
  --source-root . \
  --baseline student_cmdp_study \
  --report results/stage0-recheck.json
```

The integration check copies the allowlisted inputs to a temporary root, builds
twice with generated junk and a prior archive present inside that root, compares
both full results and package hashes, and compares 26 numerical/reference CSV tables
with the baseline (rtol 1e-8, atol 1e-9). It checks original-file preservation.
Temporary verification copies are automatically deleted.

See `docs/STAGE0_COMPLETION.md` and `docs/stage0_gate_evidence.json` for execution
evidence, known limitations and the next bounded stage. GPT Work audit schemas
under `docs/references/audit_v1/` are historical proposals, not implemented contracts.

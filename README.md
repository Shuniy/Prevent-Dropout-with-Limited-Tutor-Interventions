# Student support research — Stage 0

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

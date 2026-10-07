# Stage 1 completion — 7 October 2026

Stage 1 is implemented and executed in this repository. Its ingestion, lineage,
canonical-contract and information-boundary gate passed. This result is a
versioned data/interface foundation, not an executed simulator or policy study.

## Implemented

- Read-only ingestion through `src/data/stage1.py`, using ten explicitly hashed
  inputs in `configs/stage1_inputs.v1.json`. The raw source map is portable through
  `--source-root`; output versions are staged and cannot overwrite completed results.
- Independent reconstruction of raw subject identity, conservative linkage, split
  assignment, contextual recodes, proxy definitions and every descendant's inheritance.
- Frozen validated contracts for all fourteen requested interface families, plus
  nested supporting records and JSON Schema v2 export. Historical audit proposals
  remain preserved separately. No additional runtime dependency was introduced.
- Separate context/audit, policy, environment and evaluator loading interfaces.
  Default score features are only historical G1, prior failures and study-time code.
  Full metadata, sex, math enrichment, G2/G3, final absences, hazards, latent response
  and future outcomes are excluded from the policy feature path.
- Withheld generated reset dynamics, explicit unknowns and dated structured
  measurement contracts. Evidence-linked extraction batches, estimated-state/risk
  version matching and immutable decision contracts are ready for later services.
- The 25 math-only outcome enrichment rows are repaired from their source anchors
  in the new evaluator table. No original data or existing baseline is changed.
- Source mappings and 475 provenance rows covering all retained input columns,
  canonical contract fields, configuration and fixed-fixture generation parameters.
- All new datasets are under `results/stage1-v1/data/`, separated into role folders.
  Four disposable macOS metadata files and two task-created temporary copies were
  removed; no original dataset or completed baseline was removed or relocated.

## Executed evidence

The detailed evidence is in `stage1_gate_evidence.json`, `stage1_test_results.txt`,
`stage1_cleanup_manifest.json`, and `results/stage1-v1/validation.json`.

| Check | Result |
| --- | --- |
| Test suite | 41 passed: 28 Stage 1 tests plus 13 Stage 0 regression tests |
| Original subject references | All 1,044 rows; every raw cell and its lineage checked |
| Primary cohort | 649 Portuguese anchors; train/validation/test = 388/125/136 |
| Sensitivity cohort | 674 profiles, including 25 math-only anchors |
| Conservative links | 358 safe cross-subject links; eight ambiguous keys; 12 ambiguous math rows retained as references |
| Fixed reset fixtures | 2,000 descendants; splits = 1,200/400/400 |
| Independent source representation | 615 anchors and 604 linkage groups represented in the fixture |
| Inherited-field mismatches / split crossings | 0 / 0 |
| Unknown fields / missing math enrichment | Preserved; no zero-filling or fabricated enrichment |
| Forbidden policy access | Unsupported fields, outcome loading, path traversal and symlink redirection rejected |
| Hidden-data invariance | Changing latent state and replacing evaluator/environment files leaves serialized policy observations unchanged |
| Replay / relocation | A second build from relocated inputs has identical full artifact hashes, even with unrelated generated files present |
| Current code identity | Matches the code hashes saved with the completed result |
| Input and baseline preservation | All 22 Stage 0 raw-source hashes, 46 original baseline files and 41 Stage 0 result/archive files verified unchanged |
| Tested environment | Python 3.12.14; Stage 1 uses only the standard library |

The completed result manifest SHA-256 is
`212346e311d40822d903dc0abfb99ca74f0afd7b6e46da523b7b32203eebd414`.
All artifacts were read back and verified after publication. Test fixtures and
relocation copies are temporary and removed automatically.

## Assumptions and next bounded step

Source questionnaire dates are unknown; selected contextual fields are assumed
available at a hypothetical first-period reset. Source category codes/units are
retained. The source codebook's failures wording is ambiguous; actual codes 0–3
are preserved without reinterpretation. Generated attendance, engagement, response,
financial barriers and static hazards remain simulation assumptions. The legacy
static future draw is evaluator-only and cannot determine a sequential outcome.
The application interfaces prevent accidental leakage; they are not an OS sandbox
against hostile code with direct filesystem access.

No dynamic risk model, state updater, extractor, transition process, intervention
scheduler, allocation policy or episode has been implemented or executed here.
Their typed contracts do not establish their scientific validity. There are no
observed school-dropout labels, and no real mentoring effect is claimed.

Next is Stage 2: reproduce the held-out observational course-failure baselines and
training-prevalence baseline, then implement split-aware whole-profile population
generation and recompute its distribution diagnostics. Keep university prediction
separate and keep the fixed 2,000-row fixture distinct from newly sampled episodes.

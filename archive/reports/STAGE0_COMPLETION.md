# Stage 0 completion — 7 October 2026

Stage 0 implementation and its reproducibility gate passed. This is data-preparation
work; no sequential simulator, allocation policy experiment or language pipeline
has been implemented or executed.

## What was already present

The project contained downloaded datasets, nested source repositories, and the
generated `student_cmdp_study/` baseline: preparation scripts, 674 school profiles,
2,000 synthetic reset rows, lineage/splits, hidden diagnostics, separate university
tables, descriptive models, a workbook and draft experiment specifications. The
project root itself was not a Git repository and contained no active `AGENTS.md`.

The GPT Work audit and research plan were available outside the project. Their
relevant evidence is now copied under `docs/references/`, with the implementation
prompt under `docs/`. Prior source manifests and readback claims are retained under
`docs/history/`; they remain historical records, not fresh verification results.

## Implemented

- Repaired builder in `src/data/build_study.py`, separate from the baseline.
- Explicit source-root, research-reference, source-manifest and output arguments.
- Frozen 22-file source manifest: 16 CSVs, four source ZIPs, codebook and merge script.
  Source identities are relative paths, SHA-256 hashes and byte counts.
- Input existence, identity, archive integrity and output-path preflight before
  creating outputs; changed/missing inputs fail rather than silently rebuilding.
- Staging directory, independent data readback, final source-hash verification and
  completed-result publication. Existing versions cannot be overwritten.
- Configuration, seed, code hashes and tested environment recorded per result.
- Bounded, deterministic packaging from the completed artifact ledger, with no
  recursive inclusion of archives, old packages, unlisted scripts or nested copies.
- Data checks independent of optional workbook XML inspection. New evidence does
  not claim spreadsheet recalculation, dependency restoration or visual review.
- Dataset catalog and a narrowly scoped cleanup manifest. Original data and the
  generated baseline remain in place.

## Executed evidence

`stage0_gate_evidence.json` and `stage0_test_results.txt` contain the detailed results.

| Check | Result |
| --- | --- |
| Safety regression suite | 13 tests passed |
| Repaired output data checks | 23 checks passed |
| Raw source inventory | 22 files; exactly 16 CSVs; plus one separate research reference |
| Original source and baseline preservation | Passed; unchanged hashes |
| Source/reference relocation | Passed using temporary independent copies |
| Two builds with generated junk and an old archive inside the source tree | Identical full result hashes |
| Baseline comparison | 26 tables matched at rtol 1e-8, atol 1e-9 |
| Repeated archive creation | Identical hashes, file count and size |
| Completed result | 39 listed artifacts plus `COMPLETED.json` |
| Distribution package | 40 entries, 457,293 bytes |
| Optional baseline workbook inspection | Saved XML only; 15 formulas, no saved formula-error cells |

The package SHA-256 is
`dc57f094797cc0220f2b5d559ac1d613a4673b3a36b91a2d04fa2fe67e040dfc`.
The pinned and tested environment is Python 3.12.14, NumPy 2.3.5 and pandas 2.2.3.
No dependency installation was needed.

## Deliberate limits and next step

The numerical/scientific transformations remain unchanged to establish the repair
baseline. In particular, the known math-only outcome-enrichment blanks and incomplete
provenance/schema proposals are documented Stage 1 work; the correct original values
remain available in the anchor/reference records. The prior four-week tutoring
configuration remains a draft legacy specification, not an executed intervention.
School G3 failure remains course failure, unknown income/disadvantage/dropout fields
remain null, and university records remain a separate population.

Next: Stage 1 ingestion adapters, typed contracts, source-field/provenance repairs
and enforceable policy-input boundaries, retaining the verified split lineage. No
later stage is claimed complete.

## Application verification

Applied to `/Users/shuniy/Documents/projects/school-dropout/` and revalidated there: 23 data checks passed. All 167 original files outside the three explicitly removed `.DS_Store` files retain their original hashes, including the complete baseline. No original datasets were deleted or relocated.

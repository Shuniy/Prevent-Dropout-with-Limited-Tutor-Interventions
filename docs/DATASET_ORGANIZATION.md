# Dataset organization and cleanup decisions

The project folder already contains all Stage 0 inputs. A second consolidated raw
folder would duplicate them and invalidate historical paths without improving the
build. `configs/raw_sources.v1.json` is the single authoritative dataset catalog:
22 files, including 16 CSVs, four source ZIPs, the original codebook and merge script.
The research plan is a separately hashed reference, not a dataset.

| Existing location | Use in Stage 0 |
| --- | --- |
| `student+performance/student/` | Authentic school profiles, original codebook and linkage reference. |
| `Student_Dropout_rate.csv` and its UCI ZIP | Separate higher-education dataset; never pooled with school profiles. |
| `student-dropout-prediction/` | Audit duplicate subject copies and processed X/y tables; no new independent students. |
| `abdullah0a_student-dropout-analysis-and-prediction-dataset/` | Audit the relabelled course-failure mirror; excluded from primary data. |
| `Student-Dropout-Success-All-Academic-Levels/` | Undocumented material, quarantined logically as audit-only input. |
| `student_cmdp_study/` | Preserved generated baseline, excluded completely from raw-source inventory. |
| `results/stage0-v1/data/` | All newly generated data tables together in one versioned folder. |

The duplicate datasets are still required to reproduce the old audit comparisons.
Their source archives and repository metadata are retained for provenance. The
hidden `.student.zip_old` is excluded from the new manifest but retained as an
original download, as required by the implementation prompt. No original dataset,
source repository, or baseline artifact is deleted or moved.

Cleanup is limited to three macOS `.DS_Store` metadata files outside the baseline:
the project root, `student+performance/`, and
`Student-Dropout-Success-All-Academic-Levels/`. Their hashes and sizes are recorded
in `cleanup_manifest.json`. Download folders and unrelated files are outside scope.

Only the implementation prompt, research plan, relevant audit evidence, and two
historical verification/manifest files are copied from the GPT Work package.
The research plan's synced `sources/` directory is read-only and unchanged.
No stale workbook renderer, duplicate workbook, audit-generation scripts, original
prompt revision, or unrelated GPT Work output is added to the implementation.

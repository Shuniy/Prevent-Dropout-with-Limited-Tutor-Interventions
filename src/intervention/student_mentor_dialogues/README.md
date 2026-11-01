# Synthetic Student–Mentor Conversations — Organized by Concern

**770** fictional mentoring sessions (**400 unchanged originals + 370 additions**).

- One Markdown transcript per session, titled `# Student` with `Mentor` and `Student` speaker labels.
- Simulated session durations of **30–60 minutes**, one timestamped dialogue exchange per minute.
- **6 broad concern categories**, **22 specific primary concerns**, and **13 primary support types**.
- At least **35 sessions per specific concern** and at least **20 sessions per support type**.
- Sessions are grouped by their **single authored primary concern**; secondary concerns and supports are discoverable through `manifest.csv` and indexes.

## Browse by concern

| Broad category | Specific concerns | Sessions |
|---|---:|---:|
| `01_academic_performance_and_learning` (Academic performance and learning) | 8 | 280 |
| `02_attendance_transport_and_safety` (Attendance, transport and safety) | 5 | 175 |
| `03_family_finances_and_basic_needs` (Family, finances and basic needs) | 5 | 175 |
| `04_social_relationships_and_wellbeing` (Social relationships and wellbeing) | 2 | 70 |
| `05_digital_and_device_access` (Digital and device access) | 1 | 35 |
| `06_school_changes_and_transition` (School changes and transition) | 1 | 35 |

Each category has one subfolder per specific concern, e.g.:

`concerns/01_academic_performance_and_learning/math_gap/session_0042.md`

All 22 concerns are detailed in `concern_summary.csv`.

## Metadata and indexes

- `manifest.csv`: session ID, relative path, category, primary/secondary concerns, support, support status, stage, dates and checksums.
- `category_summary.csv`: broad-category counts, original and newly added.
- `concern_summary.csv`: specific problem counts, original and newly added.
- `support_type_summary.csv`: counts by principal intervention option.
- `support_status_summary.csv`: counts by stated workflow status.
- `indexes/by_support_type/*.csv`: filtered indexes with relative paths to the actual Markdown file (no copied transcripts).
- `stats.json`: machine-readable totals.
- `tools/dialogue_banks_and_generator.py`: reproducible generator functions used for added sessions. This is based on the original authored dialogue banks, with targeted primary concern and support selection. Sessions 1–400 were not regenerated.

## Interpretation and research restrictions

**Every case is synthetic.** No students, mentors, school records, real interview minutes, causal effects, approved services, or actual dropout outcomes are represented. These are not linked to any UNICEF or UCI survey records. Times are simulated, not actual transcription times; one exchange per minute is a formatting convention.

The category and support tags are **authoring metadata, not independently verified annotations**. Status values mean only what the conversation explicitly records (including declined, pending assessment, information only, planned follow-up or inquiry pending). Neither a referral nor a request proves delivered support; no session supplies a known post-intervention effect.

These sessions reuse a common template bank. Many phrases and structures recur, so the corpus is appropriate for software testing and preliminary structured extraction, **not** a rigorous independent test of LLM generalization. For model evaluation, obtain independently authored/checked test transcripts and split by scenario and generator/template family so near-duplicates do not leak between train and test.

Keep metadata out of the LLM input when measuring extraction accuracy; the model should read the transcript only. Don't infer poverty, diagnosis, motives, eligibility or protected traits from ambiguous student statements. Preserve provenance, unknowns, contradictory evidence, and time.

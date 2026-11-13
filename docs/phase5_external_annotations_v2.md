# External language annotations v2

Pass a JSON list through `phase5_followup --corpus FILE --stage language`.
The exact corpus is copied and hashed before the first model request. A runnable
example is the new run's `language/frozen_corpus.json`; replace its synthetic
notes and annotations without reusing held-out scenarios for development.

Each record must contain:

| Fields | Contract |
| --- | --- |
| `case_id`, `split` | Unique ID; `development`, `validation` or `test` |
| `scenario_id`, `paraphrase_group`, `template_family`, `style` | Authored grouping identifiers; scenario, paraphrase and template groups must not cross splits |
| `source_anchor` | Evaluator-only source identity, or null; never sent to the model |
| `weekly_note` | `note_id`, `student_id`, `source_week`, `available_week`, `text`, one `source_event_ids` entry, and `evidence_contract: development_sentence_entailment/v2`; optional weekly mentor/programme provenance follows `WeeklyNote` |
| `note` | Matching `note_id`, `student_id`, `text`, and `event_month` equal to the source week; this is the scoring adapter |
| `as_of_month`, `eligible` | Decision week and availability flag; source week must precede cutoff and availability must be no later than cutoff |
| `gold` | Exact supported fact payload; null for unavailable notes |
| `structured_observations` | Separately supplied structured available reference payload, or null; do not invent missing structured observations |
| `annotation` | Metadata below; synthetic authorship must remain explicitly unreviewed |

Annotation metadata requires `source`, `author_id`, `reviewer_id`,
`reviewer_status`, `exact_evidence_spans`, `unknown_assertions`,
`conflicting_assertions`, `unsupported_claims`, `disagreements`, and
`adjudication`. Reviewer status is `unreviewed_synthetic`, `unreviewed_external`,
`reviewed_external`, or `adjudicated_external`. Reviewed external entries require
a reviewer distinct from the author. Adjudicated disagreements require an
adjudication record. Supplied review metadata is self-reported, not attested.
Calendar source/availability timestamps may also be retained as annotation
metadata; the execution contract explicitly uses authored weekly indices.

Gold follows `EXTRACTION_SCHEMA`: student/note identities and an `observations`
list. Each fact has all seven separate concepts (`field`, `assertion_status`,
`trend`, `condition_status`, `value`, `barrier_status`, `workflow_status`), null
`numeric_value`/`unit`, an exact `evidence` quote, zero-based Python character
`start_offset`/`end_offset`, and `source_month` equal to the source week. Every
gold quote needs a matching `{start, end, quote}` annotation span. Unknown,
conflicting and unsupported assertions remain distinct. Gold annotations never
expand the inference validator, even when they contain valid unfamiliar prose.

The bundled follow-up uses designed synthetic note identities and surface
styles with a shared development grammar. It does not establish independent
template, real mentor, or human annotation generalization. The original frozen
zero-recall language benchmark is a separate retained result.

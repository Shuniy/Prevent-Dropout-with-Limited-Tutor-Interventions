# Implementation guidance

The README describes the complete runnable workflow. The architecture and interface
files under `docs/` describe current responsibilities and public behavior. Keep
these documents aligned whenever behavior or interfaces change.

## Simple implementation

- Put each production class, including dataclasses, in its own snake-case file.
  Keep related enums together and teaching examples self-contained.
- Give each class one responsibility. Student/mentor records hold domain state,
  School allocates resources and owns the monthly cycle and reports, Intervention
  manages one programme, SimpleLLM extracts all selected sessions in one call, and
  optional RAG processes chronological findings session by session.
- Pass dependencies explicitly. RAG receives its index and model client; tests
  replace the client with a small fake. Keep HTTP calls out of domain models.
- Use plain functions for CSV loading, transcript parsing, findings validation,
  and JSON writing. Do not add containers, generic frameworks or abstract layers.
- Use ordinary loops, descriptive local variables and direct imports. Retain
  inheritance only where the child preserves the parent's behavior.
- Add dependencies only for a working feature. Do not add analytics, logging,
  traceability metadata, model repair loops, or wrappers for planned capabilities.

## Working behavior to preserve

The CSV loader reads supplied synthetic records without rewriting them. Optional
unknown values remain `None`. Source and runtime support needs use the shared
school need rules; do not repeat those rules in allocation or reporting. Need severity drives admission,
not a trained risk estimate.

Both allocation-only and full simulation assign one mentor and at most one
programme per student per run. The full simulation allocates, processes results,
evaluates all students and saves reports monthly before advancing the clock.
Reserve the full planned dose at admission, charge recorded appointments, and release unused reservations for
later allocation windows. Keep skills, caseload, session limits and budget checks.

The default SimpleLLM sees all selected spoken sessions together, with no retrieval
index or earlier generated memory. Keep the existing output fields and private
session files, validating the complete response before saving any timeline entries.
Its timeline is a retrospective reconstruction; only RAG enforces temporal isolation.
Neither method may include sessions beyond the planned limit or source labels.

RAG sees spoken turns, earlier passages from the same history, and earlier validated
findings. No header labels, source profiles, future sessions or retrospective
outcomes enter prompts. Use one findings schema, one generation attempt per session,
and save valid sessions immediately. Failed output does not enter memory. Keep
partial results, clear private errors and nonzero CLI failures. School receives an
immutable allowlisted result, never private narrative findings. Known reported
outcomes and participation update runtime state; unknowns/conflicts/failures
retain relevant measures with a reason. Numeric changes need an explicit school
transition policy and never establish causal effects. Keep source data intact.

The dependency direction is main -> school -> intervention. Intervention accepts
immutable scalar requests, owns source history and private memory, and returns
limited immutable results. It must not import school or receive school records or
mutation callbacks. School alone validates identity/counts/duplicates and reconciles
attendance, budget and performance. Keep optional private artifacts in a separate
destination, with no paths or links in school exports.

## Tests and documentation

Use standard-library unittest, small fixtures, temporary output folders, and the
shared fake client in `tests/helpers.py`. Check observable features and useful error
cases. Avoid assertions about private structure, removed metadata, or logging.
The default suite needs no live model. Use a separate small Ollama smoke run when
available; it is not a required dependency of feature tests.

Run `python -m unittest discover -s tests`, an allocation CLI check, and affected
examples after changes. Examples must not execute on import. Update README commands,
workflow/output descriptions, architecture, interfaces, and roadmap status together.

Preserve existing source datasets, corpus generators, notebooks, archived outputs,
and unrelated edits. Historical notebooks may require import/result updates before
reuse. Research plans are references, not requirements to build future complexity.

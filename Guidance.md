# Implementation guidance

The README describes the complete runnable workflow. The architecture and interface
files under `docs/` describe current responsibilities and public behavior. Keep
these documents aligned whenever behavior or interfaces change.

## Simple implementation

- Put each production class, including dataclasses, in its own snake-case file.
  Keep related enums together and teaching examples self-contained.
- Give each class one responsibility. Student/mentor records hold domain state,
  School allocates resources, the simulator coordinates a cohort, Intervention
  manages one programme, and RAG processes chronological findings.
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
unknown values remain `None`. Computed support needs live on Student; do not
repeat their rules in allocation or reporting. Need severity drives admission,
not a trained risk estimate.

The monthly baseline permits repeat allocations across months. Intervention mode
assigns one mentor and one programme per student. Reserve the full planned dose
at admission, charge recorded appointments, and release unused reservations for
later allocation windows. Keep skills, caseload, session limits and budget checks.

RAG sees spoken turns, earlier passages from the same history, and earlier validated
findings. No header labels, source profiles, future sessions or retrospective
outcomes enter prompts. Use one findings schema, one generation attempt per session,
and save valid sessions immediately. Failed output does not enter memory. Keep
partial results, clear errors and nonzero CLI failures. Findings never modify
numeric need inputs or establish causal effects.

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

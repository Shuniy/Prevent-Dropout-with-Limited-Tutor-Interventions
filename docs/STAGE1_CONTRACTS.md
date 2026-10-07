# Canonical contracts v2

`src/data/contracts.py` is the executable contract definition. Frozen dataclasses
reject unsupported keys, mutable containers, wrong categories/types, non-finite
numbers, invalid ranges, future evidence and inconsistent identities/versions.
`to_dict()` returns a detached JSON-compatible copy; `from_dict()` validates it.
`contracts.v2.json` exports closed JSON Schema 2020-12 definitions. Cross-field
semantics (evidence spans, timestamps, ratio arithmetic and version matching) are
enforced by the Python constructors in addition to structural JSON Schema checks.
Historical audit schemas remain unchanged under `docs/references/audit_v1/`.

| Contract | Purpose and boundary |
| --- | --- |
| StudentContext | Verified/recoded source context, lineage metadata, audit groups, explicit unknowns. Initializer/auditor only. |
| EnvironmentState | Assumed enrollment, attendance, engagement, need, latent response/barrier, programme timers and counts. No static future outcome or hazard is exposed to policies. |
| Observation | Allowlisted field/value, units, event/source time, availability, status, source and missingness. No hidden/risk/causal fields. |
| ExtractedObservationBatch | Note identity/text, extractor version, source/receipt times, exact evidence spans, stable assertions, numeric ratios or qualitative categories/trends. Not an implemented extractor. |
| EstimatedStudentState | Immutable revision with field values/intervals, freshness, conflicts, evidence IDs, update rule/version, accepted/rejected evidence, and separate prediction/correction provenance. Not an implemented updater. |
| RiskEstimate | Independent probability or explicit unavailability; exact simulated withdrawal target, horizon, support regime, estimate/model/calibration versions, feature hash, missingness/OOD, and optional justified uncertainty. Not a fitted model. |
| DecisionInput | Immutable estimated states with matching risks, authorized intervention histories, waiting/eligibility evidence, and resource ledger/commitments. No environment state or evaluator Outcome is accepted. |
| SupportOffer / Acceptance / Delivery / Completion | Separate dated records with distinct IDs, student/programme/mentor links, resource amounts and acceptance/delivery/completion fields. A pending offer does not imply delivery. |
| Outcome | Evaluator-only simulated endpoint event. It is not a legal intervention-history record. Historical G3 labels remain separately named course-failure references. |
| ResourceLedger | Per-week staff/admin hours, caseload, money/currency, reservations, cancellations and waste. Scheduling/capacity enforcement remains later-stage work. |
| EpisodeRecord | Initial lineage cohort, one source split, named seed streams, configuration/policy versions and evaluator-only outcomes. No episodes are executed in Stage 1. |

Every supported source and canonical column, and every declared fixed-fixture
generation parameter, is covered by `provenance_register.v2.csv`. The register
records meaning, unit, role, derivation, availability, classification, uncertainty
and generation mechanism. The fixture recipes describe Stage 0's existing draws;
Stage 1 performs no stochastic generation or causal calibration.

## Consumer boundaries

`PolicyStore.load_reset(split, cohort="primary")` opens only a fixed policy filename.
The selectable cohorts are primary, sensitivity and fixture; no arbitrary table
or path parameter is accepted. Symlink redirects and unknown cohort/split names
are rejected. Full metadata, outcomes and environment state have separate loaders.
Context/fixture lineage is used to partition outputs, then stripped from policy
records except the join-only `student_id`. `model_features()` returns only explicitly
selected observed values, never IDs, source rows, splits, sex or math enrichment.

The current configured features are first-period grade, prior failure code and
study-time category. A closed broader reset allowlist includes school, age, parental
education, internet, commute and existing support flags; change the versioned
configuration to select them. These flags describe source context, not treatment
effects. Numeric source categories retain codebook meanings; travel category is
not a measured number of minutes, and university qualification codes never enter
the school adapter. The source failures field contains codes 0–3, despite ambiguous
wording in the original codebook; codes are preserved without reinterpretation.

Reset source collection dates are unknown (`source_time=null`); availability at
simulation week zero is explicitly assumed. Initial generated attendance,
engagement, learning need and enrollment are emitted as withheld null observations.
The structured measurement adapter accepts a dated authorized measurement; the
future simulator must implement its observation selection/noise/missingness process.
Neither latent response nor a static future draw can be passed through that adapter.

Qualitative improvement cannot manufacture a number. Qualitative workflow/barrier
categories and booleans may be retained as reported facts. Evidence spans must match
the note exactly, ratios must match their counts, and unknowns cannot be zero-filled.
Risk is explicitly unavailable until a later model is fitted and checked. A new
estimate revision cannot be paired with an old risk revision/time. The enrolled-risk
target is not applicable to a student currently known to be withdrawn.

These are typed API and data-product boundaries, not operating-system isolation.
Future policies must receive records, not arbitrary filesystem/root capabilities.
Event deduplication across batches, revisions, replay, calibrated updates, dynamic
risk fitting, schedules, resource feasibility and the feedback loop remain the
responsibility of subsequent stages; Stage 1 makes no claim that those algorithms
have been executed.

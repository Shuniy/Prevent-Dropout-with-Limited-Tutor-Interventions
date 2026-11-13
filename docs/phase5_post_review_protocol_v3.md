# Phase 5 post-review follow-up v3

This separate protocol preserves Phase 5 v1/v2, the fixed 48-student/30-world
primary result, its lack of established retention advantage, and the original
language development 10/10, validation 0/8 and test 0/11 result. No old record is
amended. Active execution uses Python 3.13; old exact replay requires the recorded
source and runtime, possibly the archived Python 3.12 environment.

## Prediction

Target: probability of at least one withdrawal event in the next min(4, remaining
weeks), conditional on current enrollment, continuing accepted schedules and no
new offers. Only authorized decision-time beliefs, documentation and commitments
enter features. Four reservation indicators encode target weeks 0–3. Future
attendance, delivery, measurements, draws and hidden conditions are prohibited.
Programme duration, cadence, start-at-offer convention, cancellation before
later-week service, completion semantics, delivery and transition parameters are
part of compatibility. The exact configuration, schema and observed training
schedule pattern must be supported. Unavailable predictions have no fallback.

Train using five-session weekly programmes. Fit preprocessing and coefficients
on source-train only. Alternating source-validation worlds fit calibration and
select hyperparameters respectively. Freeze the selected artifact before
generating test labels. Reject source-group and world overlap. Report event
metrics, calibration, abstentions and OOD; overlapping student landmarks are
descriptive. Uncertainty summaries use worlds. Analytical first-event prediction
is a target-matched comparator; planner analytical benefits remain unchanged.

## Language follow-up v2

Freeze corpus, annotation metadata, prompt, schema, inference settings and
development-only entailment rules before inference. Never change these using
validation/test results. Keep the original language benchmark intact. Compare
structured available observations, exact note-content gold, original deterministic
extraction, genuine prompted Ollama extraction, missing and corrupted notes.
Model responses must pass schema, source identity, time, exact sentence span and
conservative entailment checks before entering the ordinary controller. No gold
or fixture replacement on model failure. Attempts, responses, retries, latency,
raw output and rejection reasons are retained. Zero responses from an unavailable
backend means `unexecuted_model_unavailable`, with accuracy unavailable.
Live inference defaults to the benchmark only. `--llm-downstream boundary` adds
the controlled matched-prefix episode; `--llm-downstream all` additionally runs
all notes of the source-held-out LLM trajectory. Unrequested arms remain explicit.

The bundled corpus is synthetic and unreviewed. External annotations require
case/note/source IDs and times, scenario/paraphrase/template groups, exact spans,
author/reviewer status, unknown/conflicting/unsupported assertions and
disagreement/adjudication metadata. No independent-human claim without external
review, and supplied review metadata is not independently attested.

Matched snapshots hold the authorized prefix, resources and policy fixed. A
controlled actual-session boundary tests actionable continuation and later
allocation. Source-held-out closed loops generate each arm's own future notes
from its own observable events, sharing keyed exogenous mechanisms. Report
belief/risk and decision differences, feasibility, fairness and retention
separately. A difference is not evidence of improvement. Offline and mock software
tests are explicitly distinct from real inference and scientific evaluation.
At the controlled boundary, only the focal actual-session note is routed to the
model. All other notes use the common canonical information control, so backend
failure cannot alter the matched pre-note prefix. A failed focal call has no
fallback. The separate source-held-out LLM arm routes all its own notes through
the model when `--llm-downstream all` is explicitly selected.

## Population robustness pilot

Use all prespecified population seeds and their nested world seeds from
`configs/phase5_followup_v3.toml`; never replace a draw because of its outcomes.
Each source-test draw is paired across FairPoint and FairRobust. Preserve source
lineages outside public inputs. Save cohort identities, unique source anchors and
groups, replacement and repeated ancestry, support compatibility, eligible support
and audited-group counts. Report unexercised cohorts rather than replacing them.

Compute paired policy differences within each world, then means within each
population. Population means are the clusters for descriptive Student-t intervals.
Report within-population world variation separately, and a labelled method-of-
moments variance decomposition for the balanced nested pilot. Finite held-out
anchors may recur across draws; these are independently seeded simulator draws
conditional on a finite pool, not independent observed schools. Retention and
fairness are separate endpoints. Three populations and two worlds are a bounded
exploratory pilot, insufficient for a confirmatory policy conclusion.

## Verification and CI

The acceptance profile uses 16 prediction students, six prediction weeks, all
four training and four validation worlds, one test world, and one paired
48-student/six-week allocation cell. It runs no confirmatory 30-world study and
requires no inference server. Mandatory gates include nonzero source-compatible
offers/extraction, independent resource/fairness checks, incompatible-schedule
abstention, full recorded episode replay, independently recomputed scorecards
and metrics, and complete artifact inventory verification. An engineering
language boundary is non-vacuous but does not prove general language extraction.

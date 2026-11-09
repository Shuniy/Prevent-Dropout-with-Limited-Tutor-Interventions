# Weekly delivery protocol v1 — 2026-11-09

This is a new development protocol, separate from the historical monthly
[research protocol](research_evaluation_protocol.md). Do not rewrite historical
experiments to conform to it. Persist this text and its identity with every
weekly replay episode. Amend by creating a new version and new output paths.

## World and information

Use `scheduled_weekly`, contract v1, with one decision and transition per week.
The default fixture has 12 wholly fictional students, two mentors, a twelve-week
horizon, five one-hour sessions one week apart, two weekly hours/slots and two
concurrent students per mentor, 40 money units, and four-week offer windows.
Group membership alternates as an explicitly generated synthetic audit variable;
it is not inferred from notes or associated with different uptake rates.

Use the explicitly configured `synthetic_weekly_v1` matrices. These are assumed
weekly probabilities, not conversions of monthly rates or educational estimates.
Treatment is applied once in a week with actual delivered tutoring; otherwise
use usual support. Withdrawal is absorbing. Alpha zero interpolates treatment
to usual support exactly. No latent label is overwritten by an outcome note.

Default independent probabilities are acceptance .8, attendance .85, successful
delivery .95 and cancellation .02 in weeks after acceptance. No rescheduling.
First-session delivery can occur in the offer week after acceptance. A failed
attendance/delivery wastes the reserved slot. Session price is one; missed charge
zero; offer administration .1. Cancellation precedes that week's service; a
withdrawal caused by the week's transition cancels only future service.

Use ordinary public snapshots for every policy: registry, static authorized
profiles, validated note-derived posterior, separately computed WAIT endpoint
risk with matching estimate identity, known schedules, observed programme
statuses and obligations. Do not pass hidden conditions, future draws or private
response parameters to a planner or extractor. Event t and condition emissions
from transition t are unavailable until at least cutoff t+1. Delayed observations
are replayed at source time without changing earlier persisted decisions.

The existing extraction/filter schemas use historical period names. A named
weekly adapter passes week indices through those fields and persists that fact;
weekly notes have seven-day dates and snapshots use week field names. The
atomic filter still permits one admission action; the weekly filter permits
multiple distinct observed delivery weeks. Programme status is an authoritative
event, not an inferred eligibility override. Unknown or failed extractions do
not refresh condition evidence or cause a gold fallback.

## Actions, accounting and fairness

Only new tutoring offers, continuation of accepted schedules, and explicit
cancellation are supported. Require the complete schedule to fit the horizon.
Reserve full potential administration and service cost before resolving any
offers. Accepted obligations remain fixed; refusal/cancellation releases only
unused services. Convert reserved service to actual cost at delivery. Release
the difference between reservation and declared missed-session charge on a miss.
Already spent money is not refundable. Every resource and balance is reconstructed
independently from immutable events and preannounced mentor calendars.

Freeze enrollment/eligibility, source group and estimated comparable-need stratum
at each start of weeks 1–4, 5–8, 9–12, etc. Include eligible tutoring students even
when shared resource constraints make coverage impossible; expose that shortfall.
MAP probability at least .6 gives the enrolled condition stratum; otherwise use
uncertain. No later refusal/withdrawal changes the denominator. Empty cells have
undefined rates, explicit zero counts; flag small cells below 30.

Count a unique actual offer in its source window, including refusal. Repeated
offers count once per student/window. Acceptance and completion are separate.
Attribute completion to the original offer cohort even if delivered in a later
window, and report both eventual and within-window completion. Partial terminal
windows are explicitly flagged. Fairness never relaxes resource constraints.

## Planners and demonstration

Compare WAIT, keyed random feasible, risk/wait priority, resource point, fair
point and fair robust. They share snapshots and reservation validation. Point
valuation rolls out declared weekly timing with expected uptake, attendance,
delivery and cancellation; it never uses realized future outcomes. Fair methods
project starts through the current offer window, accounting for all subsequent
session/caseload weeks and the whole reserved budget. Only current starts execute.
Future enrollment and unchanged beliefs are forecast assumptions, not knowledge.

The robust method uses nominal beliefs plus two global enrolled-belief mixtures
toward lower/higher current-start retention gains (radius .25), with one coherent
belief per student/scenario shared across every candidate start. This is an
explicit bounded sensitivity approximation; it does not claim the legacy robust
uncertainty set, full stochastic optimality or empirical calibration. Fair
optimization minimizes equal-cell sum(shortfall/denominator), maximizes point or
worst-scenario aggregate rollout gain, minimizes exact scaled commitment cost,
then fixes canonical sorted start bits. Preserve nonoptimal/time-limit statuses.

Run one development seed (41). Add a deterministic four-student fixture with
identity transitions and explicit overrides guaranteeing refusal, a miss,
cancellation and completion. It is an acceptance fixture, not an estimated world.
Validate a separate hand-computable two-mentor/three-student example in tests.
Save all policies and exact offline replays into new immutable paths. Report
offers, acceptance, starts, delivered/missed sessions, completion/partial states,
obligations, actual spend, workload, frozen offer coverage, completion coverage,
waiting, shortfalls, disparities and terminal synthetic retention separately.
Do not infer policy superiority or real dropout effects from this demonstration.

## Acceptance

Test event lifecycle, hours, slots, caseload, compatibility, horizon, exact money,
release and charging rules, frozen unique-offer fairness, actual-treatment timing,
zero-effect matched draws, source-time evidence, exact estimate/risk identities,
hidden-input separation, independent random streams, replay and immutable outputs.
Run targeted checks and the full available suite on supported Python 3.12/3.13.
Keep monthly behavior/configuration identities and replay contract v3 intact.

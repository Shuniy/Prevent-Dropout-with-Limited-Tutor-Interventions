# First CMDP simulation specification

Status: version 1 implemented in `src/school`, through `School.run_cmdp` and
`main.py`. CMDP is the default CLI workflow; recorded interventions remain available through Python APIs. See [implementation and usage](cmdp-implementation.md)
and [executed results](cmdp-results-v1.md). The original specification below remains
the modelling reference. All numerical transition probabilities are scenario
assumptions, not estimates of real dropout or intervention effects.

## Decision problem

At the start of each month, School chooses which eligible students start a
support programme and assigns suitable mentors. Then every student transitions,
including students who receive no additional programme. Use a finite horizon of
12 monthly decisions and maximize expected enrollment at the end of month 12.
Existing source support is part of usual support, not removed by the wait action.

Preserve the current programme convention: one mentor, five planned appointments,
processed within the admission month, and at most one programme per student per
episode. This is a monthly programme model, not a five-month session model.

## State

Each student has a dynamic simulated condition:

| Condition | Meaning inside the simulation |
| --- | --- |
| Stable | Enrolled, relatively engaged |
| Vulnerable | Enrolled, intermittent participation |
| Disengaged | Enrolled, substantial participation difficulty |
| Withdrawn | Simulated withdrawal during this episode |

These are simulated states, not diagnoses or measured dropout-risk bands.
Withdrawn is absorbing in version 1. Reentry is a separate future experiment;
initially non-enrolled students are outside this retention cohort and must be
reported separately rather than counted as new withdrawals.

The complete decision state is

`S_t = (t, remaining_budget, [(condition_i, programme_used_i, need_type_i)], mentor_resources_t)`.

`programme_used` is necessary because eligibility depends on previous admission.
`need_type` is the initial primary support type from the existing shared need
rules and stays fixed for this first Markov world. It describes programme
eligibility, not a dynamically measured barrier. Mentor skills, availability,
session prices and group audit attributes are fixed episode context. There are
no hidden effect timers or dependence on an omitted intervention history.

Initialize enrolled students using explicit scenario rules, in this order:

1. Disengaged if assumed attendance < 0.70 or assumed engagement < 0.40.
2. Otherwise vulnerable if attendance < 0.85, engagement < 0.60, or the existing
   `Student.learning_gap` is at least 0.30.
3. Otherwise stable.

Version 1 requires known initial enrollment, attendance and engagement. Missing
values fail initialization with a useful error; they do not silently become
stable or withdrawn. Existing values are synthetic assumptions, not observations.
Source grades, attendance and engagement remain unchanged after initialization.
Only the categorical simulation condition evolves; do not recompute monthly
condition from stale source metrics or claim numeric grade/attendance changes.

Start with a structured, fully observed condition to validate the CMDP. This is
an oracle benchmark. When the controller sees imperfect extracted observations,
it needs a belief/history state and an observation model; that experiment is
partially observed and must not silently expose the true condition.

## Actions

For each student choose either:

- `wait`: usual support with no additional scarce programme; zero incremental cost.
- `start_programme(mentor_id, support_type)`: reserve five appointments with a
  mentor qualified for that student's fixed initial need type.

The support vocabulary is the existing 13 `SupportType` values. Programme action
availability requires enrollment, no previous programme, a matching mentor skill,
and sufficient capacity and money. Initially non-enrolled/reentry cases are
excluded as described above. Withdrawn students and previous programme recipients
can only wait. This also prevents an arbitrary second intervention effect.

Version 1 gives all eligible, need-matched types the same assumed effect matrix.
It evaluates who receives scarce support and when, not comparative efficacy of
13 interventions. No basis currently supports distinct causal effects per type.

## Transition model

Rows are the current condition; columns are next month's condition. Each row
sums to one. All students transition once after allocation.

| Current | Action | Stable | Vulnerable | Disengaged | Withdrawn |
| --- | --- | ---: | ---: | ---: | ---: |
| Stable | Wait | 0.88 | 0.10 | 0.015 | 0.005 |
| Vulnerable | Wait | 0.15 | 0.65 | 0.17 | 0.03 |
| Disengaged | Wait | 0.03 | 0.17 | 0.65 | 0.15 |
| Withdrawn | Wait | 0 | 0 | 0 | 1 |
| Stable | Start programme | 0.94 | 0.05 | 0.008 | 0.002 |
| Vulnerable | Start programme | 0.35 | 0.53 | 0.10 | 0.02 |
| Disengaged | Start programme | 0.10 | 0.35 | 0.47 | 0.08 |

The programme matrix applies only in the admission month. Any subsequent benefit
persists through the improved condition, not an unmodeled permanent treatment
multiplier. Transitions are independent across students conditional on current
states and feasible actions; there are no peer or shared-shock effects in v1.

The environment samples transitions using its own seeded random stream. The LLM
does not select probabilities, determine success, or turn a helpfulness report
into a numerical improvement. Existing prerecorded histories can test extraction,
but are not causally synchronized observations of these newly sampled transitions.
Connecting language requires a later explicit observation adapter.

Test a null-effect world where the programme matrix equals the wait matrix,
and intermediate-effect worlds using their convex combinations. These are
sensitivity scenarios, not confidence intervals or empirical calibration.

## Reward

Use zero intermediate reward and terminal reward

`R_T = sum_i 1[condition_i,T != Withdrawn]`.

The objective is `max_pi E_pi[R_T]`, with discount factor 1. This directly values
end-of-horizon retention. Do not reward appointments or subtract monetary cost
again from retention: money and mentor time have their own constraints. Report
enrolled student-months, withdrawal timing and condition distributions as secondary
metrics. They are not additional weighted terms in the initial objective.

## Constraints and budget

Use binary allocation decisions `x[i,m,t]`, with support type implied by the
student's eligible need. Enforce these on every realized monthly allocation:

- At most one mentor/programme per student and at most one admission per episode.
- Only eligible student/mentor/support matches can have `x = 1`.
- Per mentor/month: admitted students <= remaining caseload capacity.
- Per mentor/month: `5 * admissions <= available appointment slots`.
- If hour limits are configured, `5 * session_duration * admissions <= available
  hours`; duration and hours must be supplied together. Existing generated mentors
  have zero hours and no duration-based accounting, so v1 uses appointment limits.
- `sum_(i,m) 5 * mentor_session_price[m] * x[i,m,t] <= remaining_budget_t`.

Update budget by subtracting this month's committed programme costs. Never exceed
the episode budget on a sample path, even if an expected-cost planner recommends
more support. Mentor capacity is released for the next month.

For the first language-free experiment, assume the full five-appointment programme
is delivered and charged. Do not combine that assumption with existing recorded-
session refunds. Adding nonattendance later needs a separate uptake/dose model,
effects by delivered dose, and explicit reservation/refund timing.

Suggested development scenario:

| Parameter | Value |
| --- | ---: |
| Initially enrolled students | 100 |
| Mentors | 2 |
| Horizon | 12 months |
| Programmes per mentor per month | 10 |
| Appointment slots per mentor per month | 50 |
| Appointments per programme | 5 |
| Cost per appointment | 1 synthetic budget unit |
| Total episode budget | 150 synthetic budget units |
| Maximum funded programmes | 30 |
| Initial seed | 42 |

This budget limits coverage to 30% before withdrawal or eligibility restrictions;
capacity limits admissions to 20 per month. Sweep budgets 0, 50, 150, 300 and 500
to examine scarcity. These units are not rupees or an estimated programme price.
The existing CLI defaults of 10 students and budget 10000 allow all 10 five-session
programmes for only 50 units, so they do not create budget competition.

Audit access and retention by the existing disadvantage proxy and source sex;
the proxy is not verified financial disadvantage. No demographic reward penalty
or unsupported numerical fairness quota is built into v1. A later fairness
constraint must specify its eligible denominator, horizon, tolerance and
infeasibility behavior explicitly, then compare outcomes against this baseline.

Step 4 now implements that extension as declared minimum admission coverage with
frozen four-month cohorts, integer targets, strict/soft modes and rolling plans.
The current contract and experiments are in [the Step 4 specification](cmdp_fairness_v1.md);
the preceding paragraph describes the original resource-only v1 design.

## Simulation and planning

Monthly order: observe current conditions/resources; choose and validate joint
actions; reserve/charge programmes; mark admissions used; sample every student's
transition; record results and resources; advance time. Count terminal enrollment
after the twelfth transition. Allow wait for everyone so resource feasibility is
always possible.

The formal CMDP operates on the joint cohort state and feasible joint actions.
The small independent-student occupancy LP in `src/basic_examples/cmdp.py` only
constrains expected resource use and omits programme eligibility and remaining
budget. Reusing it unchanged would not enforce this specification. A practical
controller can replan over the remaining horizon and solve a feasible monthly
assignment, but its performance should be labeled approximate unless global
optimality is established. Hard validation is required regardless of planner.

Implement and evaluate the environment first with wait-only, random feasible,
highest-condition-severity, and existing need-priority baselines. Then add the
CMDP planner. Compare policies across multiple paired seeds with exogenous draws
keyed by episode/student/month so action-dependent draw counts do not shift the
randomness. Report mean terminal retention and uncertainty, total spend,
programmes/appointments delivered, utilization, wait times and group access.
Observed retention differences between policies in this simulator are not
individual causal labels or evidence of real-world efficacy.

Acceptance checks: stochastic rows are valid; withdrawn is absorbing; every
student transitions every month; no repeat programmes; no skill/capacity/budget
violations; zero budget matches wait-only; rewards match terminal counts; identical
seed/configuration/policy reproduces results; null-effect scenarios have no
systematic policy benefit across repeated runs. Preserve existing source data,
private extraction boundaries and unrelated saved evaluation results.

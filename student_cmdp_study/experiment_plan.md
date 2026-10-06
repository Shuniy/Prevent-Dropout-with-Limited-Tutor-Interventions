# Experiment protocol for limited tutor interventions

This is an implementation-ready design for a semi-synthetic simulator, accompanied by prepared initialization data and a machine-readable experiment grid. Sequential environments, allocation policies and policy-performance results have not been implemented or executed in this task.

## Research question and population

Does allocating limited tutor/support capacity with explicit access constraints and uncertainty handling improve simulated retention and disadvantaged students' access when student information is incomplete?

The primary source cohort is 649 Portuguese secondary-school course profiles, including students aged 15–22. The unit in the simulator is a generated student agent descended from an observed profile, not an independently sampled real child. Use only the relevant source split to generate an episode. Primary episode size is 2,000, horizon 36 hypothetical weeks; pilot at 200 agents. A reset after observed `G1` is a hypothetical landmark. Thirty-six weeks is a chosen simulation duration, not the actual remaining duration of the source school year. Add 12- and 24-week horizon sensitivity checks; do not invent calendar dates.

Use the 25 math-only profiles only in a cohort sensitivity experiment. Run university prediction separately. Claims are conditional computational comparisons in this population and assumed dynamics. Neither the observed failure endpoint nor university associations validate school tutoring effects.

## Formal decision process

Use a finite-horizon CMDP for the fully observed structured-information benchmark. State `s_t` includes each student's enrollment, engagement, learning gap, attendance, current barrier state, prior support and waiting time; global state includes tutor availability, budgets, committed future sessions, programme capacity, time and rolling-window eligibility/offers. Adding these counters to state is necessary for Markov resource and coverage accounting.

When engagement, barriers or response tendency are hidden, the controller sees an observation `o_t` and a history or belief over states. This is a partially observed constrained problem. Describe a belief-state or history-based policy explicitly; do not claim a fully observed CMDP while supplying hidden truth only to some policies.

The main objective is expected terminal retention:

`maximize E_pi[ (1/N_initial) * sum_i enrolled_i,36 ]`.

Use zero intermediate reward and terminal retention reward for the primary objective, with discount 1. Record attendance and engagement as secondary outcomes. If reward shaping is used to train a learner, preserve the declared terminal evaluation and report the shaping term separately. Retention is a simulator enrollment state, not a threshold on grades or four weeks of absence. Recovery and re-entry are explicit model transitions. Transfers or completion must not be coded as dropout if later measured data provides them.

For each resource `r`, impose expected cumulative cost limits where required by the CMDP formulation. In addition, the action validator must enforce weekly capacity and budget pathwise for every realization. An expectation constraint or reward penalty does not ensure the actual tutor schedule fits.

Choose at most one new offer per student per week, among eligible, enrolled students. Respect ongoing commitments; do not start another incompatible tutoring block until the existing one ends. Each planned action specifies offer, acceptance, delivery, dose and delay separately. The policy chooses offers, not guaranteed successes.

## State initialization and observation contract

Load verified/recoded source fields from the primary student table. Initialize hypothetical learning gap, attendance and engagement from the supplied reset fixture or the documented equations. Income and economic eligibility remain unknown. Source sex is an audit field, not a default action-selection feature. The proxy disadvantage group can be used by a declared access constraint; it does not establish financial eligibility.

Do not expose final grades, full-period absences, hidden hazard, response tendency, latent finances or future dropout draws. Model risk learned from `G3<10` is a course-failure score; if used for the highest-risk baseline, name that baseline explicitly and separately compare a simulator-estimated dropout score trained on training-world trajectories.

Generate observations from the policy's actual evolving state, with timestamps. Missing is unknown, not false. For partial information, use structured noisy inputs before introducing notes. Group-dependent missingness masks mutable observations at 40% for the proxy group and 10% for the comparison group, with the process logged and held constant across matched policies. Preserve authorized group labels for fairness accounting rather than inferring them from text.

## Two transition families

The two families must differ structurally, not just in random seeds. All numerical parameters below are proposed assumptions to challenge the policy. Use training-only usual-support simulation to check their realized retention, attendance and recovery; tune nuisance intercepts before freezing validation/test configuration. Do not use test trajectories to choose a response model.

### Family A: continuous need and hazard

For enrolled student i, retain learning gap `g` in [0,1], attendance `A` in [0,1] and engagement `e` in [0,1]. A proposed weekly update is:

`g_next = clip(g + 0.01*(1-A) + Normal(0,0.015) - tutoring_effect, 0,1)`

`e_next = clip(e + 0.02*(A-0.85) + Normal(0,0.025) + liaison_effect, 0,1)`

`A_next = clip(0.85 + 0.15*(e_next-0.5) - 0.10*g_next - 0.06*active_travel_barrier + Normal(0,0.03) + support_effect, 0,1)`.

Use school-week shocks shared by agents plus individual shocks in a separate robustness scenario. The attendance equation's mean reversion is a modelling choice; compare a persistent AR(1) attendance alternative with coefficient 0.8. Preserve ranges after adverse action effects as well as positive effects.

Base annual-equivalent logit score follows the reset hazard configuration, replacing initial gap and barrier with current states. A dynamic extension adds `1.0*(0.85-A) + 0.5*(0.7-e)` before annual-to-week conversion. Baseline annual targets 5%, 10% and 20% are assumptions. A static 10% calibration does not imply dynamic annual dropout is 10%; calibrate usual-support trajectories and report the realized rate.

For dropout events, draw a Bernoulli weekly hazard after state updates and apply it only to enrolled students. No transfer occurs in the base world because it is not modelled; say so. Add a separate re-entry probability 0.005 per withdrawn student per week in the base family and test 0 and 0.02. Withdrawn students have zero tutoring eligibility until re-entry. Track endpoint enrollment and first-withdrawal incidence separately so re-entry does not conceal previous events.

### Family B: four-state Markov model

Use states E engaged, I intermittent, D disengaged, W withdrawn. Base one-week transition matrix in E/I/D/W order:

| From | E | I | D | W |
| --- | ---: | ---: | ---: | ---: |
| E | 0.970 | 0.025 | 0.004 | 0.001 |
| I | 0.120 | 0.835 | 0.040 | 0.005 |
| D | 0.020 | 0.130 | 0.825 | 0.025 |
| W | 0.000 | 0.005 | 0.000 | 0.995 |

Initialize E/I/D from the generated attendance and engagement, using fixed thresholds A≥0.9 and e≥0.7 for E, A<0.75 or e<0.4 for D, otherwise I. These states are simulated, not observed dropout labels. For delivered tutoring, move probability mass 0.02 from I→I to I→E and 0.03 from D→D to D→I, scaled by response tendency and effect multiplier. Liaison shifts 0.01 from I→W to I→E only up to available mass, then 0.02 from I→I to I→E. Referral shifts 0.02 from D→D to D→I after its delay for long-commute agents. For negative multipliers reverse these moves only within available probability mass. Project into a valid probability simplex if necessary and log the projection; never allow negative probabilities.

Vary transitions by risk/barrier strata through a declared, capped shift from self-transition to W, then renormalize. Test both a scalar hazard-uncertainty family and this transition-topology mismatch. For the tutor-only reduced world, binary actions and independent students give an RMAB comparison setting. Shared staff budgets still couple allocation. Adding peer effects would invalidate independent-arm assumptions and is not part of the base study.

## Action catalogue and resources

Run the tutor-only version first: action 0 usual support and action 1 offer a four-week tutoring block. Keep the same underlying usual-support process in every policy. Existing `schoolsup` or `paid` observations do not identify an untreated history; action 0 means no extra simulated intervention.

The heterogeneous extension adds attendance/family liaison and transport assessment/referral. Programme availability and verification requirements are scenario facts. A long commute alone is not proof of economic eligibility. If programme eligibility requires finances, keep it unknown and offer assessment rather than silently approve financial aid.

| Action | Duration | Tutor hours per delivered week | Liaison hours | Money units | Acceptance | Delay |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Usual support | 0 | 0 | 0 | 0 | 1 | 0 |
| Tutoring block | 4 weeks | 2 | 0 | 4 per week | 0.70 | 1 week |
| Attendance/family contact | 1 week | 0 | 0.5 | 1 total | 0.75 | 1 week |
| Transport assessment/referral | 1 week | 0 | 1 | 2 total | 0.60 | 2 weeks |

Each new offer consumes 0.1 administration hours even if refused. All amounts are normalized hypothetical resources, with no currency interpretation. Tutor acceptance/delivery and response variation are assumed, not estimated from source support fields. Tutoring's proposed per-session effect is a 0.05 learning-gap reduction times hidden response tendency; liaison adds 0.04 attendance and 0.03 engagement times response tendency; successful referral removes an assumed 0.03 attendance penalty for four weeks. Diminishing returns multiply an additional block's effect by `1/(1+completed_blocks)`. Apply stress multipliers −0.5, 0, 0.5, 1 and 2.

At capacity fraction f in {0.05,0.10,0.20}, define `K=floor(f*N_initial)`, weekly ceilings of 2K tutor-hours, 0.5K liaison-hours, 4K money units, 0.1K administration hours and at most K new offers. Multi-action capacity is a resource envelope, not a promise that every student can receive each action. Budgets use N_initial throughout an episode so dropout cannot shrink the denominator and change resources. Cap actual service counts, reserve all four future tutoring weeks before offering a block, and subtract ongoing reservations before allocating new blocks. This means steady-state new tutoring starts may be near K/4, not K per week; report active recipients and starts separately.

Check affordability over every future reserved week and the total episode budget. No block starts if its last session would occur after week 36. Release unused future reservations when refused, withdrawn or cancelled. Delivered-session cost is charged on delivery; offer administration is charged on offer. Use a missed-session reservation/wasted-capacity measure rather than silently refunding all opportunity cost. Interventions cannot overdraw a budget merely because the CMDP constrains expected cost.

## Access constraints

At each four-week window start, freeze an eligible cohort within low/moderate/high need strata using current simulated need and available eligibility information, under the same rule for every policy. Proposed high need is learning gap ≥0.3 or A<0.75; moderate is gap≥0.1 or A<0.85; remaining eligible profiles are low need. Do not call every student eligible for all actions. Calculate action-specific eligibility and the union for overall coverage. Keep an audit of unknown eligibility and expose differential exclusion.

Coverage for group g and stratum k is the fraction of this fixed cohort offered an appropriate action at least once during the window. Count unique students, not contacts. Withdrawal after the window begins does not remove the student from that denominator. Offers, acceptance and completed service each have separate metrics.

For the main fair policy, target coverage q=0.10 in every nonempty audited group/need stratum. Test q=0,0.10,0.20. Report small groups, with n<30 marked imprecise rather than suppressed from the optimization by default. At low capacity, simultaneous targets may be infeasible. Hard resource and eligibility constraints stay hard; first minimize explicit nonnegative access slack, then maximize retention benefit at that minimal slack. Report group/window shortfalls. A soft penalty is not a guaranteed quota.

Compare component-level groups (education, internet, commute) and the ≥2 composite. Also report age and source-sex audits with cell counts. Do not claim outcome parity from access constraints. Low access can reflect unknown information or uptake barriers, so evaluate offers and delivery separately. No inequality target should be optimized by changing who the controller calls needy.

## Policies and optimization

1. Usual support only.
2. Random feasible offers, with identical action and capacity availability.
3. Longest-waiting eligible student, with deterministic ties or a logged independent tie stream.
4. Highest risk: explicitly distinguish source failure-proxy risk from simulator dropout risk fitted on training-world trajectories.
5. Expected incremental retention benefit per resource unit, followed by common feasibility validation.
6. Rolling-horizon assignment using expected transition estimates, horizon four weeks. Reserve commitments, execute the first action and replan.
7. The same planner with frozen-cohort access constraints.
8. The same fair planner maximizing downside benefit over declared transition/observation uncertainty sets. Tune the downside level on validation worlds only.

For heterogeneous costs, normalized cost must match the fixed scarce-resource envelope; a single monetary ratio is not a full solution when staff skills bind. Include a one-step mixed-integer baseline to isolate the value of planning. Record solver status, time limit, incumbent, gap and runtime; a feasible incumbent is not necessarily optimal. On tiny instances (5–10 students, two weeks), enumerate feasible assignments and verify the result against exact terminal expected value. A true-parameter policy is a diagnostic, not automatically an upper bound; an exact tiny-instance optimum is a distinct result.

Add a constrained learner such as a Lagrangian actor-critic only after the simulator and optimizer validation gates pass. Give it the same observation and resource validator, and log raw as well as repaired violations. Its study is optional; the primary contribution can be uncertainty-aware rolling-horizon allocation. A Whittle-style baseline requires a binary independent-arm reduction and an indexability check or an explicit heuristic label.

Fair resource allocation has established methods. [Herlihy, Prins, Srinivasan and Dickerson's ProbFair](https://arxiv.org/abs/2106.07677) constrains intervention probabilities in a restless-bandit setting. [Li and Varakantham](https://proceedings.mlr.press/v180/li22e.html) provide fairness-constrained RMAB planning/learning methods. They inform baselines; their results do not establish education effects or guarantee the properties of this heterogeneous, delayed-action simulator. Any novelty claim needs a fuller comparison of the exact uncertainty and information setting.

## Staged experiment matrix

| Stage | Settings | Purpose |
| --- | --- | --- |
| A: implementation pilot | N=200, H=12, 10 development seeds; tiny exact cases | State transitions, actions, costs, split isolation and optimizer correctness. |
| B: primary computational comparison | N=2,000, H=36; 2 transition families × 3 budgets × 3 observation settings × 8 policies × 30 held-out seeds | 4,320 planned episodes. The CSV grid contains the 144 policy/scenario cells. |
| C: effect and base-risk robustness | Retain the best fixed validation policies plus random/risk/usual controls; multipliers −0.5/0/0.5/1/2 and annual-equivalent target 5/10/20% | Sensitivity to benefit assumptions, including zero and harmful tutoring. Avoid an unnecessary full cross-product. |
| D: resource and delay stress | −50% capacity shock at week 12, uptake reduced by 0.2, delays 1/2/4 weeks, commitment horizon and horizon lengths | Reliability under staffing and delivery uncertainty. |
| E: group and cohort stress | Proxy cutoff ≥1/≥2/3, individual components; math-only extension; age<18 versus all | Dependence on grouping and source-population choices. |
| F: optional language experiment | Structured gold, deliberately masked/noisy structured fields, extracted note facts with unknown/conflict states | Isolate extraction errors from policy and transition assumptions. |

The machine-readable grid is the multi-action primary design. The tutor-only reduction is an initial correctness study under the same budget levels, followed by the listed heterogeneous-action study. Do not combine tutor-only and multi-action results under one policy label. Keep policy hyperparameters and uncertainty-set construction frozen before held-out evaluation. Development seeds are 0–9; held-out world seeds are 1000–1029. Worlds must draw source profiles only from their own split.

For an optional note benchmark, create factual records first, reveal only selected present-time facts and produce notes without outcomes or hidden response. Split scenarios, templates and all paraphrases by anchor group. Hold out a writing style/generator and obtain independently reviewed labels before making extraction-validity claims. A structured form is an essential comparison; do not assume an LLM is necessary. Synthetic notes remain synthetic even when attached to observed profiles.

## Evaluation and statistical analysis

Primary estimand: paired difference in mean simulated endpoint enrollment between robust fair planning and ordinary fair planning, with point-estimate planning and highest-risk allocation as secondary comparisons. Predeclare the family/budget/observation settings for the primary contrast. Report raw retention, difference in percentage points and incremental cost. Attendance/engagement, first-withdrawal incidence and re-entry are separate outcomes.

Report weekly and cumulative resource consumption, active tutoring blocks, new offers, delivered sessions, acceptance, unused capacity, reservation waste and pathwise hard-constraint violations. Report access coverage by fixed-cohort stratum, coverage slack, longest wait, worst-group retention and offer-versus-delivery gaps. Compare utility–access frontiers instead of collapsing them into a single fairness score. Record computation time and memory to establish simulator scale on the available machine.

Pair policies using random draws keyed by world seed, student identity, week and event type. Separate streams for population, common shocks, individual transitions, dropout, uptake, observation masks and policy ties. Different numbers of offers must not shift other policies' random streams. Recompute observations from each policy's own trajectory. Common random numbers improve Monte Carlo precision; they do not make divergent policy states identical.

Treat the episode/world as the independent unit. Use paired world-level differences with 95% bootstrap intervals over the 30 worlds, alongside per-scenario distributions. Students, weeks and resampled source profiles within one episode are not independent repetitions. Increase seeds only if pilot-based precision requirements justify it; do not repeatedly test and stop at significance. Apply a declared correction (e.g. Holm) to secondary families of inferential tests, or label them descriptive. Report all planned contrasts and failures.

Keep Monte Carlo uncertainty separate from response-parameter uncertainty and source-sampling uncertainty. Resample source linkage groups in an outer sensitivity analysis if estimating source-cohort variability. Thousands of bootstrap agents do not expand the observed sample beyond 649 profiles. Intervals conditional on assumed dynamics are not confidence in real-world intervention effectiveness.

Zero-effect worlds are an informative negative control: treated and usual-support policies should have no expected retention difference, apart from any separately declared action burden. Harmful-effect worlds test whether a learned uncertainty-aware policy appropriately avoids harmful offers and whether an access target forces costly conflict. Report that conflict rather than disguising it as successful prevention.

## Validation gates and implementation order

| Gate | Required evidence |
| --- | --- |
| Data | Unique local IDs; no split overlap; exact duplicate sources removed; 358 safe links; all unavailable labels remain unknown; source hashes unchanged. Completed in this package. |
| Reset | Range-valid states; matched observed profile distributions/joints; no controller path to hidden outcomes; resampling confined to source split. CSV fixtures completed, environment read-path test still needed. |
| Dynamics | Probability-simplex validity; absorbing/re-entry rules as configured; known zero-effect behavior; equivalent repeated-seed trajectories; plausible usual-support traces in both families. Pending implementation. |
| Actions | Offer/uptake/delivery distinction; delayed effects; four-week reservations; cancellations; no negative budget or double assignment. Pending implementation. |
| Fairness | Frozen denominators; unique offer counting; correct empty/small-group handling; explicit infeasibility/slack; no manufactured eligibility. Pending implementation. |
| Solver | Tiny-instance exact comparison; independent feasibility validator; reproducible ties; logged termination/gap. Pending implementation. |
| Evaluation | Keyed common-random-number pairing; episode-level uncertainty; frozen policy parameters; held-out world/split separation. Pending implementation. |

Implement the simulator without language models first, then policies and diagnostics, then staged experiments, then the optional extraction layer. Preserve source manifests, configuration hashes, policy version, world seed, student/action/state logs and solver trace for every run. A useful first result is a retention–coverage–cost table with an explicit zero-effect comparison. Field validation requires actual school records and an appropriately designed intervention evaluation; the computational study cannot substitute for it.

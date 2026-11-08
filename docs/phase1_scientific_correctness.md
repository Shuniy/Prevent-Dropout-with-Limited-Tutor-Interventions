# Phase 1 scientific correctness

Scope: R02, R03 and R14 only. Written from the current implementation and the
Phase 1 task on 2026-11-08; deleted historical guidance was not consulted or
restored. This is a contract and implementation report, not a research protocol
or validation of past experimental results.

Documentation recovery note (2026-11-09): the historical evaluation protocol has
since been restored unchanged. References below to its deletion describe the
Phase 1 checkout before recovery. See the [README authority policy](../README.md#documentation-navigation-and-authority)
for its historical status and future protocol/amendment requirements.

## Information contract

Ordinary closed-loop policies receive immutable `DecisionState` snapshots built
by `operational_snapshot`: source-context support priorities and demographic
proxies, current authorized enrollment records, posterior condition estimates,
risk estimates, evidence provenance, public mentor calendars, budget and past
admissions. They do not receive generated reset attendance/engagement, raw math
G1, private condition maps, future draws/outcomes or realized response parameters.
The controller's explicit `oracle` mode uses the labeled legacy fully observed
snapshot. Evaluator truth and the privileged observation generator remain separate
from ordinary decision construction. This is an API boundary, not a security
sandbox against arbitrary Python code accessing private environment attributes.

Source-context needs and estimated condition are separate. Numeric attendance and
engagement cannot be reconstructed from categorical condition emissions. Therefore
no attendance/engagement-specific support eligibility is inferred from an unobserved
reset value. The existing zero-severity tutoring fallback remains when no source
need is present. Enrollment eligibility comes from the administrative registry;
fairness proxy membership uses source education, internet and travel context.
Mentor compatibility and need-priority baselines consume the same corrected source
profile. No fairness targets, allocation objectives or transition matrices changed.

## R02: received evidence versus condition assimilation

Previously `last_observation_month` and `missing_current_signal` scanned received
facts, even when the Bayesian update rejected them. They now use only source months
of successfully normalized condition emissions, recomputed during chronological
replay. A successful emission need not numerically change an already concentrated
posterior. It must pass the existing correlation and likelihood rules.

`observation_history`/`evidence_ids` retain received facts. The existing update log's
`accepted_observations` means newly admitted to history, not assimilated. Conflicts
and zero-likelihood events remain in rejected logs and unresolved observations;
unknown qualitative facts remain unresolved. `observed_support_history` independently
retains workflow facts. Registry masks still constrain beliefs but never refresh
condition information. Event facts are sorted by evidence identity for deterministic
replay; duplicate evidence gains no extra Bayesian weight. Delayed facts retain their
source month, never their receipt cutoff.

The robust builder continues to use the unchanged formula:

`rho = min(1, radius * missingness_multiplier**missing * (1 + min(age,F)/F))`

Here `age = cutoff - 1 - latest_assimilated_source_month`, or `F` when none exists.
Missing means no assimilated signal for `cutoff - 1`. Defaults are radius .25,
multiplier 1.5 and F=3. These are synthetic sensitivity assumptions, not calibrated
confidence intervals. No usable evidence gives rho=.75. A current usable signal
gives .25. Source-month 0 evidence at cutoff 3 gives .625, even if received late.
Adding a rejected month-2 conflict to that history previously reset freshness to
month 2 and rho=.25; now it preserves month 0, rho=.625 and the missing/stale stratum.

## R03: private reset versus public source needs

Previously the shared need rule read generated reset attendance and engagement,
then exported their derived severity/support type through environment `_profiles`.
Changing reset attendance from 1 to .01 could expose severity .99 and attendance
planning, even with identical authorized evidence.

`calculate_needs` now excludes reset measurements and reset enrollment by default.
`Student.need_profile`, `need_score`, `primary_support_type` and `_profiles` inherit
that boundary. In the controlled regression, both worlds now expose need 0 and
tutoring, identical compatibility, eligibility, fairness fields, estimates, serialized
snapshots and baseline allocations. Their private initial conditions still differ
(stable versus disengaged), and fixed WAIT actions follow the same keyed transition
model in each world. Actual later observations/outcomes may consequently differ.

Recorded-history performance evaluation explicitly opts into `legacy_runtime=True`
for its existing attendance, engagement and enrollment measurements. That opt-in is
not used by categorical research snapshot construction. Private initial condition
still uses the historical two-grade reset formula so this correction does not
silently change simulated reset mechanics.

## R14: academic availability

The initial decision landmark is assumed to follow the Portuguese first grading
period. Portuguese anchor G1 is usable under that assumption; its operational gap
is `clip((10 - Portuguese_G1)/10, 0, 1)`. There is no verified synchronized math-G1
availability in the current source contract. Mathematics G1 is excluded from all
operational learning gaps and resulting support priorities, whether present or
missing. The source field and loader/schema remain unchanged, including `None`.

No optional mathematics authorization switch is introduced: this benchmark rejects
operational inclusion at every cutoff until a future change supplies a verified
availability contract. Thus the conditional test for authorized inclusion is not
applicable. No fabricated availability date, zero imputation or inferred
synchronization is used. With anchor G1=10, replacing missing math G1 by 0 previously
changed the gap from 0 to .5; it now remains 0, with identical earlier decision
inputs and nontrivial need-priority ordering. Anchor G1=2 still gives gap .8.

## Changed files and compatibility

- `src/school/state_estimator.py`: assimilation-based source freshness and canonical replay ordering.
- `src/school/belief_state.py`: documents the corrected meaning of the existing freshness field.
- `src/school/uncertainty_scenarios.py`: documents the freshness consumed by the unchanged formula.
- `src/school/needs.py`: public source-only defaults; explicit legacy runtime opt-in.
- `src/school/performance.py`: labels the recorded-history opt-in.
- `src/school/student.py`: anchor-only operational gap and shared grade-shortfall arithmetic.
- `src/school/cmdp_environment.py`: preserves private legacy grade-based reset initialization.
- `tests/test_phase1_correctness.py`: new deterministic counterexamples and integrated invariants.
- `tests/test_student_models.py`: replaces old public-reset/nonmissing-grade expectations with
  corrected assertions, retaining explicit legacy measurement tests.
- `tests/test_research_information.py`: supplies test-only protocol text for manifest mechanics
  because the historical protocol was deleted; production still requires a real protocol.
- This document: new contract, rationale, verification and limitations.

The public dataclass schema and estimate field names are retained. Freshness semantics,
public needs, compatibility and priorities intentionally change. The legacy atomic
benchmark remains available and its transition/resource model remains unchanged,
but its newly computed public priorities also use the corrected source rules.
Recorded-history academic gaps also use anchor-only grades. Source datasets,
historical outputs/results and reference artifacts are unchanged. Historical
performance claims must be rerun before being attributed to this information model.

## Verification

New tests were executed before implementation: 5 methods produced 8 assertion
failures/subtest failures covering rejected freshness, zero likelihood, aging,
hidden reset and unavailable grades. The pre-existing estimator/uncertainty suite
passed 13 tests before the changes, demonstrating that it did not catch these bugs.

The default `python` was 3.10.19 and failed imports (`tomllib`). The existing `.venv`
was 3.14.8, outside the declared >=3.12,<3.14 range. Initial full-suite execution
there found obsolete need/grade expectations and a missing-protocol fixture error;
these were corrected as described above, not suppressed.

Supported verification uses CPython 3.12.12 in `/tmp/phase1-python312` with numpy
2.3.5, scipy 1.18.1, jsonschema 4.26.0, pandas 2.2.3, matplotlib 3.11.2 and tabulate
0.10.0. Only offline runtime/test dependencies were installed; this is not a
certification of notebook, Torch or model-service environments.

Commands (run from repository root):

```sh
MPLCONFIGDIR=/tmp/phase1-mpl /tmp/phase1-python312/bin/python -m unittest tests.test_phase1_correctness tests.test_feedback_estimation tests.test_uncertainty_scenarios tests.test_student_models tests.test_research_information
MPLCONFIGDIR=/tmp/phase1-mpl /tmp/phase1-python312/bin/python -m unittest discover -s tests
MPLCONFIGDIR=/tmp/phase1-mpl /tmp/phase1-python312/bin/python -m src.main --extractor fixture --students 3 --months 2 --budget 5 --seed 73 --output /tmp/phase1-fixture-comparison
```

Focused suite: 31 tests pass. Fixture comparison: completed, 17 comparison rows,
zero real LLM calls; artifacts were written outside the repository. Full-suite
result is recorded below after completion.

## Remaining scope limits

The observation/transition models and uncertainty parameters remain synthetic.
Source contextual availability other than the declared grade boundary is assumed,
not independently verified here. No real LLM validation, Phase 2 remediation,
research experiment rerun or refreshed research protocol is supplied. In particular,
research manifest freezing still needs an independently approved replacement for
the deleted protocol. The full research workflow is not certified by Phase 1.

## Final acceptance

Full offline suite: **237 tests, PASS**, 41.606 seconds, CPython 3.12.12; no
failures or errors. `git diff --check` passes. Diff inspection confirms no data,
historical result, transition-matrix, fairness-target or policy-objective edits.

| Criterion | Status | Evidence |
|---|---|---|
| R02 | PASS | Invalid/unknown/workflow/zero-likelihood evidence cannot refresh condition metadata; valid, delayed, duplicate and replay cases check both posterior and robust radius/stratum. |
| R03 | PASS | Two separate environments differ privately but expose identical whole snapshots, mentor compatibility, eligibility, fairness fields and baseline allocations under fixed evidence; fixed WAIT transitions remain correct. |
| R14 | PASS | Missing/source math values preserved; present unavailable math cannot alter operational gaps, snapshots or two-student priority ordering; Portuguese anchor remains usable. Optional synchronized inclusion is deliberately not supported. |

No commit or push was performed; changes are available for independent review on
`fix/phase-1-scientific-correctness`. Phase 2 has not been started.

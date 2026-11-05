# Step 6 implementation and reproduction

The [research protocol](research_evaluation_protocol.md) was frozen before the
held-out comparison. [Results and limitations](research_results.md) report the
actual executions; [the original generated report](../results/research_evaluation_v1/research_results.md)
keeps artifact links beside the data. No training, new support type, RAG or
application dashboard was introduced.

## Implementation files

- [Robust fairness planner](../src/school/robust_fair_planner.py): continuous eta,
  finite-scenario aggregate max-min benefit, original rolling-window hard resources,
  fairness slack, exact cost and canonical tie priorities.
- [Uncertainty scenarios](../src/school/uncertainty_scenarios.py): bounded probability
  mixtures from authorized belief, missingness and observation age; no hidden truth.
- [Existing fairness planner](../src/school/fairness_planner.py) and
  [MILP helper](../src/school/optimization.py): narrow optional support for mixed
  integer/continuous feasible vectors and negative eta lower bounds; original
  callers keep their previous defaults.
- [Note renderer](../src/intervention/feedback_notes.py): optional controlled
  ambiguity, negation and partial reporting in addition to omission, misreporting,
  conflict and delay, all driven by separate keyed draws.
- [Existing closed-loop controller](../src/school/closed_loop_controller.py):
  explicit student-to-note-quality mapping for declared group-quality experiments.
  [Existing feedback exports](../src/school/feedback_experiments.py) record it.
- [Extraction benchmark](../src/evaluation/extraction_evaluation.py) and
  [persistent real extractor cache](../src/evaluation/cached_observation_extractor.py):
  note-supported gold, independent semantic table, exact-rule comparator,
  pre/post-validation metrics and complete request/cache provenance.
- [Scorecards](../src/evaluation/scorecards.py): post-execution beliefs, consistent
  WAIT risk target, frozen fairness memberships, retention, resources and solvers.
- [Paired statistics](../src/evaluation/paired_statistics.py): unique equal seed
  sets, sample SD, Student-t intervals, raw means and retention percentage points.
- [Research experiments](../src/evaluation/research_experiments.py): protocol/hash
  guards, development gate, primary, bounded secondary/live stages, resumable
  immutable episodes and reuse of identical default sensitivity cells.
- [Report generation](../src/evaluation/research_report.py): all nine requested
  scientific figures, tables, twelve-section report and selected failure traces.
- [Configuration](../configs/research_evaluation_v1.toml),
  [assumptions](research_assumptions.md), README, architecture, contracts and roadmap
  document the current workflow and scientific boundaries.

The package initializer is [here](../src/evaluation/__init__.py). New offline tests
cover [scenarios](../tests/test_uncertainty_scenarios.py),
[robust optimization](../tests/test_robust_planner.py),
[extraction](../tests/test_extraction_evaluation.py),
[world statistics](../tests/test_paired_statistics.py),
[scorecards](../tests/test_research_scorecards.py), and
[information/manifest isolation](../tests/test_research_information.py).

## Exact reproduction commands

Run from the project root with the configured scientific environment and an
installed local `qwen3.5:latest` model. Source/configuration changes intentionally
invalidate the frozen run; use a new directory rather than silently replacing it.

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/run_extraction_benchmark.py --live \
  --output-dir results/research_reproduction/extraction
.venv/bin/python scripts/run_research_evaluation.py --stage all \
  --output results/research_reproduction
.venv/bin/python results/research_evaluation_v1/analyze_executed.py \
  --output results/research_reproduction --verify-real-replay
.venv/bin/python results/research_evaluation_v1/audit_results.py \
  --output results/research_reproduction
```

Individual stage entry points are
[the pilot](../scripts/run_research_pilot.py),
[primary comparison](../scripts/run_primary_experiment.py),
[sensitivities](../scripts/run_research_sensitivity.py),
[extraction benchmark](../scripts/run_extraction_benchmark.py), and
[report generator](../scripts/generate_research_report.py).
[The main runner](../scripts/run_research_evaluation.py) supports `--stage freeze`,
`pilot`, `primary`, `secondary`, `live`, `report` and `all`.
All stage commands accept `--output`; the extraction benchmark uses `--output-dir`.

The additional post-execution analysis script is preserved with the result
artifacts. It computes prespecified group/denominator and enrolled-only diagnostic
summaries, adds trace examples with explicit model/operational comparators, and
copies the generated report to this documentation directory with corrected links.
Its source and input hashes are recorded independently; it never tunes policies.

## Verification and execution evidence

Before Step 6, all 189 existing tests passed in 45.556 seconds. The completed
regression log is [here](../results/research_evaluation_v1/regression_tests.log).
The versioned protocol, configuration/source hashes, actual package versions and
solver tolerances are in [the manifest](../results/research_evaluation_v1/configuration_manifest.json).
The development and primary gates, detailed solver diagnostics, exact cached-real
replay checks and acceptance audit reside beside the episode artifacts.

The selected environment reports Python 3.14.8 while the project declares
Python 3.12–3.13. No claim of certification on those supported versions follows
from this execution. Model temperature zero does not guarantee bitwise fresh
inference; deterministic cached replay is a separate check.

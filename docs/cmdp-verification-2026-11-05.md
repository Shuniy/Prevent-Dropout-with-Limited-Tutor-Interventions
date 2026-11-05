# CMDP execution and workflow verification — 5 November 2026

The current working tree completed the full CMDP experiment with no observed
runtime failures or solver fallbacks. This verifies the tested configuration and
environment; it does not guarantee success for every input or platform.

## Executed workflow

```sh
.venv/bin/python -m unittest discover -s tests
MPLCONFIGDIR=/private/tmp/cmdp-matplotlib XDG_CACHE_HOME=/private/tmp/cmdp-cache \
  .venv/bin/python -m src.main --suite full \
  --policies wait random severity need_priority longest_waiting terminal_value fairness \
  --output results/cmdp_v1/verification_20261105
.venv/bin/python -m src.basic_examples.cmdp
```

- All **103 current tests passed**, including subprocess execution of both
  `python src/main.py` and `python -m src.main`, real report generation, invalid
  CLI options, resource constraints, solver failure handling, exact planning,
  fairness, reproducibility and observation boundaries.
- The full sweep completed **2,240 episodes**: eight effect/budget scenarios,
  seven policies, ten development seeds and thirty held-out seeds. All episodes
  completed twelve monthly transitions, with **zero solver fallbacks**.
- The standalone teaching example completed successfully. It uses its own reward
  definition and is separate from the school retention experiment.
- The saved output contains the manifest, episodes, representative trajectories,
  summaries, exact reference, Markdown report and both PNG plots.

## Independent checks of saved outputs

An additional audit checked all 26,880 episode-month metric records and all 112
saved representative trajectories. It verified budget and appointment accounting,
monthly mentor capacities, no repeated programmes, no admission after withdrawal,
absorbing withdrawal, population totals, terminal retention and withdrawal counts.
All 784 paired confidence intervals were independently recomputed from episode
differences. All source and population hashes matched the executed working tree.

Zero-effect and zero-budget episode condition counts matched wait-only, and
zero-budget episodes made no allocations. The runner additionally checked complete
student-condition trajectory equality across policies in every zero-effect world.
Every non-timing episode metric matched the historical `full_003` run exactly.

Machine-readable audit results:
[`verification.json`](../results/cmdp_v1/verification_20261105/verification.json).
Full experiment:
[`report.md`](../results/cmdp_v1/verification_20261105/report.md).

## Findings

Held-out default scenario: 100 students, twelve months, budget 150, effect strength 1.

| Policy | Mean terminal enrolled | Paired difference versus wait, 95% CI |
| --- | ---: | --- |
| wait | 71.167 | 0.000 |
| severity | 72.700 | 1.533 [1.197, 1.869] |
| terminal_value | 72.633 | 1.467 [1.117, 1.817] |
| fairness | 72.367 | 1.200 [0.841, 1.559] |

The terminal-value heuristic does not establish an improvement over severity-first:
its paired difference is -0.067 students, 95% CI [-0.161, 0.028]. The exact tiny
reference also confirms that the heuristic is not globally optimal: expected
terminal enrollment is 1.953501435 for the exact policy versus 1.949161250 for the
heuristic, a gap of 0.004340185.

## Limits and documentation observations

- Execution used the existing Python 3.14.8 environment. The project declares
  Python 3.12–3.13; this run does not verify those versions. Managed 3.12 and 3.13
  interpreters are present outside PATH, but the inspected 3.13 interpreter lacks
  NumPy. No dependencies or interpreter settings were changed.
- These are synthetic, fully observed simulation findings. Independent held-out
  transition seeds do not validate real intervention effects or a new student
  population. Confidence intervals exclude transition-model uncertainty.
- Monthly MILP optimality does not imply full-horizon CMDP optimality. Fairness
  mode uses soft coverage targets and can retain unmet access shortfalls without
  an execution failure. LLM-driven closed-loop evaluation remains unimplemented.
- Earlier documentation records historical totals of 102 or 107 tests and an
  allocation CLI that the current CMDP-only CLI no longer exposes. The current
  suite has 103 tests, and its entrypoint tests explicitly reject the removed
  allocation/intervention CLI flags. Those historical verification statements
  should not be treated as current CLI instructions.
- Existing uncommitted edits were preserved; no production code changes were
  needed. Experiment files follow the repository's ignored `results/` convention.

# Student support simulation

School owns mentor allocation, a monthly simulation clock, student performance and
school reports. Intervention runs a confidential synthetic programme using recorded
mentor/student conversations and LLM/RAG analysis, returning only approved structured
outcomes. The dependency direction is `main → school → intervention`.

The default full simulation tracks every student for twelve months. Each student
receives at most one programme with one mentor, with five total planned appointments.
A programme is processed within its admission month. Mentors can serve other students
in later months. School applies participation and reported outcomes without inventing
numeric improvements or changing original source records.

## Setup and commands

Use Python 3.12 or 3.13, as declared in `pyproject.toml`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

The requirements include dependencies for preserved research notebooks. SQLite FTS5
provides retrieval; no embedding model is needed. For live generation:

```bash
ollama serve
# In another terminal:
ollama pull qwen3.5:latest
```

```bash
# School simulation with local Ollama:
python -m src.main --students 2 --mentors 1 --months 12 --sessions 5

# Allocation only; no model needed:
python src/main.py --allocation-only --students 10 --mentors 2 --months 12

# Public school reports, with optional private findings stored separately:
python -m src.main --students 1 --mentors 1 --sessions 1 \
  --output results/example_school --private-output results/example_private

# Private/developer analysis of one history through its second session:
python -m src.intervention.rag \
  01_transport_assessment/intervention_student_001 \
  --through-session 2 --output results/private_history/conclusion.json

# Offline feature tests, including teaching examples:
python -m unittest discover -s tests
```

Equivalent application entry points are `python src/main.py`, `python -m src.main`,
and, after installation, `school-dropout`. Defaults: 10 students, 2 mentors,
12 months, 5 total sessions per programme, mentor capacity 10, budget 10000, seed 42.

Randomness uses NumPy generators configured in `src/utils/constants.py`. Teaching
examples share `DEFAULT_RNG`; school and intervention runs use independent streams
from `create_rng(seed)` so resets and explicit seeds remain reproducible. NumPy
selection changes the sequences previously produced by Python’s `random` module.
Historical corpus generators retain their original RNGs.
Use `--history-root` for another corpus, `--model` for another installed model, and
`OLLAMA_BASE_URL` for a different local endpoint. `--output` must be new or empty.
`--private-output` is optional and must be new/empty and separate from school output;
equal or nested destinations are rejected. Private findings are not saved by default.
The CLI prints one final message and exits nonzero on configuration or model failure.

## Monthly school workflow

1. Read current performance, save a before snapshot and compute ranked support needs
   using the shared baseline/current rules. Need severity determines priority;
   seeded shuffling breaks ties.
2. Allocate suitable mentors using skills, caseload, monthly session limits and
   remaining budget. Reserve the entire planned dose for the month's admissions.
3. Send immutable minimal requests to intervention. It binds a coherent randomly
   chosen support-matched history to the run/programme/student/mentor identity.
4. Process at most the planned number of recorded sessions in order. RAG uses only
   current spoken turns, earlier passages of that history and earlier validated
   findings. Source profiles, headers, future sessions and retrospective labels
   stay outside prompts. Each programme starts fresh memory, with corpus reuse
   permitted and seeded selection reproducible with a deterministic model.
5. School validates matching result identity and counts, rejects duplicate application,
   charges recorded sessions and releases unused reservations. Recorded attendance
   remains available when model analysis fails. Missing history returns zero attendance.
6. Update school-owned participation and known reported outcomes, record after
   snapshots and save the monthly report before advancing the clock. Refunds can
   fund later months; the same month is never refilled.
7. Save student summaries and the final school report after the final month.

All students remain in monthly tracking, including unassigned students and those
whose programme has finished. A student never starts a second programme in a run.
Source grades, demographics and `initial_*` assumptions remain unchanged. Current
metrics, mentoring participation and reported outcomes are separate. A reported
attendance improvement does not become an invented attendance percentage or grade
increase. Unknown/conflicting/failed extraction leaves relevant measures unchanged and records
why. There is no calibrated intervention score or trained predictive model.

Python callers construct `Intervention(index, client, seed=...)` explicitly and call
`school.run_simulation(intervention, output_dir=...)` once; see the
[contracts](docs/contracts.md) for a complete example. `school.allocate_programmes()`
provides the old allocation-only operation and returns monthly maps. It reserves
planned costs without claiming completed attendance. `reset()` restores baseline
performance, initial mentor caseloads and run accounting under a fresh run ID.

### Support rules

Severity is a scenario priority in `[0, 1]`, not a predicted dropout probability.
`learning_gap` is the grade shortfall below 10 divided by 10, using the average
anchor/math grade when math is available, and clipped to `[0, 1]`.

| Condition | Support | Severity |
| --- | --- | --- |
| Initially not enrolled | Reentry support | 1 |
| Learning gap or past failures | Tutoring | Maximum of learning gap and failures / 4, capped at 1 |
| Assumed attendance below 0.85 | Attendance planning | 1 − attendance |
| No home internet | Device access | 0.5 |
| Travel category at least 3 | Transport assessment | (category − 2) / 2 |
| Study-time category 1 | Homework support | 0.25 |
| Family relationship rating at most 2 | Family liaison | (3 − rating) / 3 |
| Health rating at most 2 | Wellbeing check-in | (3 − rating) / 3 |
| Assumed engagement below 0.6 | Peer support | 1 − engagement |
| Financial need explicitly verified | Family finances | 0.75 |
| No condition met | Routine tutoring check-in | 0 |

## Saved results and confidentiality

School reports default to a fresh directory under `results/intervention_simulation/`:

```text
run_.../
  month_01.json
  ...
  month_12.json
  final_report.json
  student_00001/
    final_report.json
```

School retains only limited immutable intervention results: run/programme/pair IDs,
month, support, planned/recorded counts, programme/analysis status, and reported
attendance change, barrier resolution and helpfulness. Exports use an explicit field
allowlist. They contain no transcripts, history IDs/paths, retrieved passages,
private errors, detailed session memory or free-text conclusions.

| School report | Contents |
| --- | --- |
| Monthly | Identity, costs, that month's admissions/results and all student before/after evaluations |
| Student final | Student ID, limited `result` or null, unassigned reason and monthly evaluations |
| Run final | Run ID, months, status, output directory, costs, assignments and student summaries |

Programme `status` is `completed`, `incomplete` (short recorded history) or
`unavailable` (no compatible history). `analysis_status` is independently `completed`,
`failed` or `unavailable`. Failed/unavailable analysis returns unknown outcomes.
A fully attended programme can have failed analysis. Run status is `failed` if any
analysis failed, otherwise `finished`; short or unavailable histories alone do not
cause extraction failure. A student who was never admitted has `result: null` and
an explicit resource/budget reason. Missing history preserves its admission with
zero cost and attendance.

Optional private persistence uses another directory:

```text
example_private/
  programme_00001/
    session_01.json
    private_report.json
```

Private session files contain detailed validated findings and identity/history data.
The private final report can contain narrative conclusions and errors. Earlier valid
sessions survive failed generation. School reports never link to this destination.
Python callers must choose separate public/private destinations, as the CLI does.
The standalone RAG command also writes private output. The findings schema checks
structure, not factual accuracy. Modules in one Python process do not provide an OS
access-control boundary. Historical outputs are not migrated.

## Code organization

Production classes/dataclasses each have their own snake-case file, with explicit
package exports and plain functions for loading, need rules, validation and reporting.

- `src/school/`: source records, runtime performance, mentors, assignments, allocation,
  the School facade, monthly simulation and school reports.
- `src/intervention/`: immutable request/result boundary, private programme profiles,
  history assignment, chronological RAG, index, transcripts and model client.
- `src/utils/`: independent shared enums and constants.
- `src/main.py`: CLI and explicit dependency construction.
- `src/basic_examples/`: independent agent, Markov, MDP and CMDP demonstrations.
- `tests/`: offline feature tests with a shared fake client.

School-specific loading/validation helpers moved from `src.utils.school` to
`src.school.loading`; imports use `src.school`, with no legacy `src.models` alias.
Cohort orchestration moved from intervention to school. There are no school objects
or mutation callbacks in intervention. See [architecture](docs/architecture.md),
[contracts](docs/contracts.md), [roadmap](docs/roadmap.md) and
[implementation guidance](Guidance.md).

## Teaching examples and research material

Run examples independently:

```bash
python -m src.basic_examples.markov_chains
python -m src.basic_examples.simple_agent
python -m src.basic_examples.agent_based_modelling
python -m src.basic_examples.markov_decision_process
python -m src.basic_examples.budgeted_mdp
python -m src.basic_examples.cmdp
```

Imports do not run simulations. Examples keep their essential state counts,
rewards, and optimization algorithms and print a final result. The CMDP example
uses SciPy through the existing scientific environment. The production workflow
uses a need-priority heuristic, not a CMDP optimizer.

The supplied CSVs and transcripts are used directly; no preprocessing command is
required. `data/processed/`, `data/external/`, notebooks, corpus generators, and
`archive/` remain research/reference material. Historical notebooks may need import
or result-field updates before reuse; they are outside this refactor. Historical
research specifications describe possible future work, not the active interface.

Synthetic conversations and assumed attendance/engagement are not observations of
real children or measured treatment effects. Missing appointments have unknown
reasons and do not establish dropout. Historical course failure is not school
dropout. Numeric outcome dynamics, trained risk models, policy evaluation, and
fairness experiments remain future work; see the [roadmap](docs/roadmap.md).

# Current architecture

The active implementation is a small, language-free monthly allocation baseline.
It loads synthetic student profiles, creates or accepts mentor agents and records
feasible tutoring assignments over a configurable horizon.

```text
synthetic student CSV
        │
        ▼
src/utils/school.py ── conversion, validation and feasibility helpers
        │
        ├── StudentSimulation agents
        └── default Mentor agents
                    │
                    ▼
             src/models/school.py
             monthly seeded allocation
                    │
                    ├── monthly_assignments
                    ├── assignment_history
                    └── spent/remaining budget
```

## Active responsibilities

- `src/models/student.py` defines immutable-input-style student profile records and
  derived access/learning-gap properties. It does not yet hold evolving monthly
  state.
- `src/models/mentor.py` defines mentor skills, monthly session availability,
  active caseload and per-session cost.
- `src/models/school.py` owns episode state and the monthly allocation loop. It
  shuffles students reproducibly, selects feasible mentors, records assignments and
  renews mentor caseload between months.
- `src/utils/school.py` loads CSV rows, converts values, validates configuration and
  IDs, creates default mentors and checks assignment feasibility.
- `src/utils/constants.py` holds the default seed, 12-month horizon, population size,
  mentor capacity, five-session dose, per-session cost and total budget.
- `tests/test_school.py` verifies loading, monthly capacity, support-type matching,
  random repeat eligibility, costs, budget limits and deterministic replay.

## Current resource semantics

- Sampling is without replacement inside one month.
- A student selected previously remains eligible in later months.
- Mentor caseload and session limits renew every month.
- The episode budget is shared across all months and does not renew.
- Session duration is not modeled.
- Allocation records scheduled support; it does not yet prove delivery or benefit.

## Planned growth

Add the next responsibilities only when they become executable:

| Planned responsibility | Suggested location |
| --- | --- |
| Mutable monthly student state and support-delivery events | `src/environment/` |
| Attendance, engagement and withdrawal transitions | `src/environment/` |
| No-support and rule-based allocation policies | `src/policies/` |
| Metrics and paired policy comparisons | `src/evaluation/` |
| Structured dated observations and estimated state | `src/state_estimation/` |
| Optional note generation/extraction and LLM evaluation | `src/language/` |

The LLM layer comes after structured observations and policy baselines work. It may
extract supported facts from authorized notes, but it must not bypass resource
checks, directly mutate the simulator or invent intervention effects.

# RAG versus Simple LLM across 13 problem types

Evaluated 4 November 2026 (Asia/Kolkata), using the current prompts unchanged.

**Simple LLM was faster in all 13 paired cases, with 31.0% less total elapsed time
and 45.3% fewer prompt characters. Both passed 38/39 narrow final-field checks.**
Manual review found explicit false-completion examples in seven RAG histories and
four Simple histories. Both also showed ambiguous action labels, delivery-scope
problems and loss of cumulative detail. These observations favor Simple as the
more economical default for this synthetic sample; they do not establish general
accuracy superiority. RAG retains the distinct benefit of enforced future-session
isolation, which Simple's retrospective timeline does not provide.

## Design and scoring

- 13 paired histories, one for every available support type; 39 source sessions.
- Deterministic selection: lexicographically first history with exactly three
  complete recorded sessions per type. No selection based on model outputs.
- Both methods process the same complete history with `qwen3.5:latest`, temperature
  0, context 32,768 and the same question as the earlier single-case comparison.
- RAG makes one call per session; Simple makes one call for all three sessions.
  Method order alternates by type: seven RAG-first and six Simple-first cases.
- Spoken reference evidence is saved in the manifest and excluded from model
  requests. CSV category/outcome indexes and retrospective session records are
  excluded. Descriptive intervention type, date and stage are included in both.
- One generation attempt per call, with no repair/retry. All 26 runs completed.

Three final-field checks per history assess barrier persistence (`no` or `partial`),
unknown school-attendance improvement, and positive session helpfulness. Spoken
turns support a continuing barrier and helpful exercises, but not improved school
attendance. These are **39 narrow checks, not overall extraction accuracy**.
Unlike the previous four-field evaluation, delivery and intervention helpfulness
are not automatically scored: they require interpretation of the support named
by the output. Scores from the two rubrics should not be compared directly.

Follow-up action reports span eight completed, eleven partly completed, four not
completed and three uncertain actions. Source questions and replies are retained
for every session in [manifest.json](manifest.json).

## Aggregate results

| Measure | RAG | Simple LLM |
| --- | ---: | ---: |
| Completed histories | 13/13 | 13/13 |
| Valid, ordered timeline entries | 39 | 39 |
| Model calls | 39 | 13 |
| Total elapsed seconds | 1,491.910 | 1,029.485 |
| Mean elapsed seconds per history | 114.762 | 79.191 |
| Median elapsed seconds per history | 119.966 | 81.651 |
| Total prompt characters, including schemas | 982,879 | 537,434 |
| Narrow final-field checks | 38/39 | 38/39 |
| Continuing-barrier checks | 12/13 | 13/13 |
| Unknown-attendance-improvement checks | 13/13 | 12/13 |
| Positive-session-helpfulness checks | 13/13 | 13/13 |
| Histories with confirmed false-completion examples | 7/13 | 4/13 |

Prompt characters are not tokens, and do not measure generation cost or hardware
utilization. Semantic-review counts are a targeted manual error audit, not an
accuracy metric; an unflagged history can still have errors.

## Results by problem type

Each score is out of the same three narrow final-field checks. Times include
method setup, local generation and artifact writing as instrumented by the runner.

| Problem type | RAG checks | Simple checks | RAG seconds | Simple seconds |
| --- | ---: | ---: | ---: | ---: |
| Transport assessment | 3/3 | 3/3 | 82.438 | 49.367 |
| Tutoring | 3/3 | 3/3 | 122.109 | 81.651 |
| Homework support | 3/3 | 3/3 | 113.788 | 81.381 |
| Attendance planning | 3/3 | 2/3 | 123.431 | 75.800 |
| Device access | 3/3 | 3/3 | 104.182 | 75.005 |
| Family finances | 3/3 | 3/3 | 116.386 | 81.980 |
| Family liaison | 3/3 | 3/3 | 127.158 | 83.569 |
| Language support | 3/3 | 3/3 | 112.350 | 81.531 |
| Learning access | 2/3 | 3/3 | 120.419 | 86.118 |
| Peer support | 3/3 | 3/3 | 119.966 | 87.217 |
| Re-entry support | 3/3 | 3/3 | 120.306 | 86.577 |
| School meals | 3/3 | 3/3 | 106.714 | 69.056 |
| Wellbeing check-in | 3/3 | 3/3 | 122.663 | 90.233 |

The two final-field failures differ:

- **RAG, learning access:** barrier resolution is `unknown`, despite its narrative
  saying the seating/visibility barrier remains unresolved and the dialogue
  explicitly reporting persistence.
- **Simple, attendance planning:** attendance improvement is `partial`. A reported
  better lesson and completion of a record-checking task do not establish improved
  school attendance.

Final-field agreement between methods was 12/13 for barrier resolution, 12/13 for
attendance improvement, 13/13 for session helpfulness, 6/13 for intervention
helpfulness and 2/13 for service delivery. Agreement is not correctness.
RAG reports intervention helpfulness `yes` in homework, attendance, device access,
finances, peer support, re-entry and wellbeing; Simple keeps it `unknown` throughout.
RAG sets service delivery `false` throughout; Simple uses `false` for transport and
wellbeing and null for the other eleven types.

## Semantic review by problem type

The following observations come from manually comparing spoken source turns with
both reports, including intermediate entries. They are not independent blinded
judgments or automated full-report accuracy scores. Report links expose the exact
entries behind each observation.

| Problem type | RAG observations | Simple LLM observations |
| --- | --- | --- |
| Transport assessment | Preserves the original crossing concern and new support-office inquiry. The uncertain departure task has pending status despite explicit unclear-completion wording. [Report](01_transport_assessment/rag/conclusion.json) | Correctly describes uncertainty, but completed refers to a task review rather than the task itself. Final primary concern loses the specific crossing; delivery=false conflicts with the completed mentoring activity named as the intervention. [Report](01_transport_assessment/simple/conclusion.json) |
| Tutoring | Final tracked details misattribute the new bring-an-attempt task to session 2 instead of tracking the previous worked-example task. Delivery is framed around an unreceived external service. [Report](02_tutoring/rag/conclusion.json) | Marks both partly completed between-session tasks completed despite contrary prose. Tutoring is marked not_discussed although exercises occurred. [Report](02_tutoring/simple/conclusion.json) |
| Homework support | Session 3 omits the reported completion of the first-two-steps task and focuses on the new clarification request. [Report](03_homework_support/rag/conclusion.json) | Retains that completion. Session 2 tracked details substitute the in-session breakdown activity for the specific new between-session agreement. [Report](03_homework_support/simple/conclusion.json) |
| Attendance planning | Marks the partly completed morning task completed; also labels the new contact/practice step completed. Keeps school-attendance improvement unknown. [Report](04_attendance_planning/rag/conclusion.json) | Retains partial action completion in prose and unresolved status, but asserts partial attendance improvement without supporting attendance evidence; the final contact task is retained only in next_steps. [Report](04_attendance_planning/simple/conclusion.json) |
| Device access | Marks the uncompleted computer-room check completed, contradicting its own narrative. Later offline-option inquiry completion is retained. [Report](05_device_access/rag/conclusion.json) | Preserves the uncompleted computer-room check and completed offline-option inquiry. Delivery stays null, but prose sometimes makes stronger non-delivery claims. [Report](05_device_access/simple/conclusion.json) |
| Family finances | Preserves the completed trusted-adult inquiry and new eligibility-guidance task. Earlier uncertain cost-list task is labelled pending. [Report](06_family_finances/rag/conclusion.json) | Also preserves the completed inquiry and new task. Earlier uncertainty becomes pending; final concern becomes generic rather than retaining travel costs. [Report](06_family_finances/simple/conclusion.json) |
| Family liaison | Retains guardian-contact uncertainty, but the consent-sharing task loses its specific identity and the final liaison-office confirmation task is replaced with a generic contact request. [Report](07_family_liaison/rag/conclusion.json) | Retains uncertain/failed prior-step reports in prose and the final office-confirmation task, but also loses the specific consent-sharing agreement. [Report](07_family_liaison/simple/conclusion.json) |
| Language support | Marks the partly completed instruction-word task completed and carries that erroneous claim forward. Session 3 summary does retain partial completion of the sentence-frame task. [Report](08_language_support/rag/conclusion.json) | Prose correctly preserves incomplete tasks and new steps; completed review labels obscure underlying task state. [Report](08_language_support/simple/conclusion.json) |
| Learning access | Uses unknown barrier resolution despite explicit persistence. Marks the partly completed monitoring task completed; session 3 summary retains the later partial task. [Report](09_learning_access/rag/conclusion.json) | Correctly reports the barrier unresolved. Completed attempt labels are ambiguous because tasks were not fully finished. [Report](09_learning_access/simple/conclusion.json) |
| Peer support | Retains both reported completions and the original friend-moved-classes concern. Final next steps omit the specific new pastoral-lead contact check and return to earlier monitoring. [Report](10_peer_support/rag/conclusion.json) | Retains completed tasks and the final pastoral-lead next step, but conflates rehearsal with a real between-session interaction in session 2 and calls session 3 Final follow-up. [Report](10_peer_support/simple/conclusion.json) |
| Re-entry support | Marks the partly completed timetable task completed; later teacher-prioritisation completion and new help-request task are retained. [Report](11_reentry_support/rag/conclusion.json) | Also marks the partial timetable task completed despite contrary prose. Captures the later teacher task, but describes the next action as rehearsal rather than using the request. [Report](11_reentry_support/simple/conclusion.json) |
| School meals | Marks the partly completed lunch-access log completed. Session 3 summary retains the partial catering inquiry, while tracked details focus on the new office task. [Report](12_school_meals/rag/conclusion.json) | Marks both partly completed tasks completed despite incomplete-task prose; support is marked not_discussed despite activities. [Report](12_school_meals/simple/conclusion.json) |
| Wellbeing check-in | Marks the uncompleted monitoring task and partly completed pause task completed. Says the check-in was delivered while service_delivered is false. [Report](13_wellbeing_checkin/rag/conclusion.json) | Also marks both tasks completed despite contrary prose. Delivery=false refers to outside support while intervention.type names the completed check-in; final concern loses the initial loss-of-interest detail. [Report](13_wellbeing_checkin/simple/conclusion.json) |

The clearest repeated failure is disagreement between narrative and structured
completion status. [semantic_review.json](semantic_review.json) records 16
source-linked examples across the flagged histories, with JSON pointers, source
questions/replies and exact model details. One language-support error is repeated
in later memory, so these are not 16 independent actions. The flag excludes
ambiguous completed-review/attempt labels; those remain separate review concerns.

Delivery scope also remains unresolved. Some outputs name tutoring, peer support
or a wellbeing check-in, describe in-session support as completed, and then use
service_delivered to discuss a separate external service. Elsewhere unverified
external receipt becomes a categorical non-delivery claim. Positive feedback about
practice may support reported activity usefulness, but it does not automatically
establish later benefit from the intended intervention or causal effectiveness.
The schema permits these outputs structurally; that does not make them consistent.

Several final conclusions also become generic or concentrate on the latest meeting,
losing earlier action progress or the original barrier. RAG sometimes retains more
specific original concerns, but generated-memory errors can persist. Simple has
all source sessions visible yet still loses detail. Neither architecture removes
the need for semantic review.

## Assessment

For this set, **retain Simple LLM as the practical default when retrospective
extraction and lower runtime matter**. It completed every case faster, matched
RAG's narrow check total, and had fewer histories with confirmed explicit
false-completion examples in this targeted audit. This is evidence about these
selected synthetic histories, not proof of superior general extraction accuracy.

Use RAG when enforced session-by-session evidence cutoff is required. Its extra
calls did not produce a clear overall quality advantage here. Before relying on
either report automatically, address action identity/status consistency, delivery
scope and cumulative final conclusions. Prompts and production behavior were not
changed during this evaluation.

## Verification, reproducibility and limits

[verification.json](verification.json) records an audit of all 52 exact requests
and 78 timeline entries: source hashes, complete conversations, metadata, fixed
prompts/question, raw-response/report equality, schema/order validation, final
conclusion equality, RAG prior-passage cutoff, memory continuity and character
totals all passed. This checks the workflow, not the truth of extracted claims.

The offline suite ran 56 tests: 55 passed; one failed because it expects the old
literal phrase `never use later disclosures`. The revised prompt expresses that
restriction differently. This is a stale wording assertion, not a demonstrated
chronology failure. Tests and prompts were left unchanged. The benchmark and tests
used Python 3.14.8, outside the project's declared Python 3.12–3.13 range.

Only one history per type and one run per method were evaluated. The histories
share generator templates and mostly unresolved outcomes; 13 types are not 13
independent tests of broad linguistic generalization. There is no rigorous positive
resolution/attendance-improvement control or contradictory-outcome test set here.
Selection is deterministic, not a representative random sample. There was no
independent reference annotator or inter-rater agreement study. Alternating method
order reduces a fixed ordering bias but does not control warm-up, cache, background
load or generation variability. Latency differences have no confidence intervals.
Simple's earlier entries are retrospective reconstructions with later sessions
visible; the input audit does not prove absence of temporal leakage in their content.
No real-world effectiveness, causal effect or dropout-prevention claim follows.

Run again with:

```bash
.venv/bin/python scripts/evaluate_intervention_types.py
```

The runner retains existing measurements, including failures, and checks its
manifest before resuming. To perform a fresh run, set its OUTPUT to a new directory;
reusing the current directory does not repeat model calls. The runner regenerates
numeric summaries; the manual semantic review and this narrative require review
again for new model outputs.

Artifacts: [summary.json](summary.json), [comparison.csv](comparison.csv),
[comparison.json](comparison.json), [manifest.json](manifest.json),
[semantic_review.json](semantic_review.json), [verification.json](verification.json),
and per-type method directories with exact requests, raw responses, validated
conclusions, partial timelines and measurements. The earlier
[single-case evaluation](../intervention_extraction_evaluation/evaluation.md)
is preserved separately.

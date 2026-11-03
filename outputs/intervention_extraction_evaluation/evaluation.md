# RAG versus Simple LLM: updated-prompt evaluation

Evaluated 4 November 2026 (Asia/Kolkata). Both methods completed on the same three
sessions of `01_transport_assessment/intervention_student_003`, using
`qwen3.5:latest`, temperature 0, 32,768 context, the existing question and reference.
The transcript hash and first-request output schemas match the preceding saved run.
Prompts were left unchanged for this evaluation.

| Measure | RAG | Simple LLM |
| --- | ---: | ---: |
| Model calls | 3 | 1 |
| Elapsed seconds | 131.669 | 80.581 |
| Prompt characters, including schemas | 74,643 | 38,631 |
| Final-field reference checks | 4/4 | 4/4 |
| Valid, correctly ordered timeline entries | 3 | 3 |
| Session helpfulness yes | 3/3 | 3/3 |

Simple LLM used 38.8% less elapsed time and 48.2% fewer prompt characters. Characters
are not tokens. Both final outcomes are barrier unresolved, attendance improvement
unknown and intervention helpfulness unknown, with service_delivered false.

## Changes from the preceding prompt run

The preceding run is preserved in
[before_rerun_20261104_012321](before_rerun_20261104_012321/evaluation.md), including
its executed notebook, reports and exact requests. The still earlier
[prior_prompt_run](prior_prompt_run/evaluation.md) remains intact.

| Measure | Previous RAG | Current RAG | Previous Simple | Current Simple |
| --- | ---: | ---: | ---: | ---: |
| Reference checks | 3/4 | 4/4 | 3/4 | 4/4 |
| Elapsed seconds | 129.409 | 131.669 | 75.261 | 80.581 |
| Prompt characters | 61,702 | 74,643 | 35,088 | 38,631 |

Both corrected the previous intervention_helpful=yes result to unknown while retaining
session_helpful=yes. This improves the conservative final-field checks, but does not
establish complete semantic correctness. RAG now retains the support-office inquiry
that its preceding output omitted. Simple no longer calls session 3 a final follow-up.

## Qualitative review against spoken source turns

These observations are separate from the four automated final-field checks.

| Requirement | RAG | Simple LLM |
| --- | --- | --- |
| Session 1 journey-time task remains future | Retains two journey times as pending | Retains two journey times as pending |
| Session 2 journey-time task completed | Carries task forward as completed | Explicitly links completed review to session 1 |
| Session 2 alternative-departure agreement | Captures in next steps; absent from tracked details | Captures as pending in tracked details |
| Session 3 departure-task completion uncertain | Says unclear in prose, but uses pending status | Prose and uncertainties retain uncertainty; completed status describes the review, leaving task status ambiguous |
| Session 3 support-office evidence inquiry | Retains as pending | Retains as pending |
| Original crossing barrier survives to final findings | Retained in tracked details | Final primary concern becomes generic; route uncertainty remains elsewhere |
| Final conclusion synthesizes earlier progress | Omits explicit recap of completed journey-time work | Also omits explicit recap of completed journey-time work |

RAG offers better continuity of the original barrier in this case. Simple captures
the session-2 timetable comparison result (one journey close to timetable, another
much later), which RAG's narrative does not specify. Neither final conclusion fully
synthesizes progression across all three sessions.

Delivery remains problematic. Simple names completed mentoring activities in
intervention.type but sets service_delivered=false, despite explicit prompt guidance
that delivery should correspond to the activity named there. Its narrative switches
to external support as the referent. RAG consistently names the intended Transport
Assessment, but carries false and categorical non-delivery claims into later sessions
where the safer interpretation is that external receipt has not been established.
The historical delivery reference accepts false or null, so it does not detect these
scope and certainty problems. RAG also introduces a formal assessment/route-verification
framing that is more specific than the source establishes. Simple assigns external
verification next steps to the mentor without an explicit recorded commitment.

## Interpretation and verification

The revised prompts improve the measured final outcome distinction for both methods.
Simple remains more efficient; RAG better preserves the original barrier. These results
do not establish an overall accuracy winner. Further review should focus on delivery
scope, explicit uncertain action status and genuinely cumulative final conclusions.

Both live responses passed the existing schema validation and timeline-order checks.
The offline suite ran 56 tests: 55 passed and one failed because
`test_sparse_source_numbers_keep_position_separate_and_pass_metadata` asserts the old
literal phrase `never use later disclosures`. The new prompt states the same
chronology restriction with different wording. This is a stale wording assertion,
not observed proof of a chronology failure. Tests and prompts were not edited.
Offline Python was 3.14.8; the notebook kernel used 3.10.19, both outside the declared
3.12–3.13 range.

This is one synthetic case, one run per method, executed RAG first. Startup, cache and
generation variability are uncontrolled. Four reference checks do not measure full
narrative accuracy or intervention effectiveness. Simple sees all selected sessions;
its earlier entries are retrospective reconstructions, while RAG enforces future-session
isolation. Findings labelled validated have passed structure checks only.

Artifacts: [comparison](comparison.json), [RAG report](rag/conclusion.json),
[Simple report](simple/conclusion.json), [RAG requests](rag/requests.json),
[Simple requests](simple/requests.json), and
[executed notebook](../../notebooks/intervention_extraction_evaluation.ipynb).

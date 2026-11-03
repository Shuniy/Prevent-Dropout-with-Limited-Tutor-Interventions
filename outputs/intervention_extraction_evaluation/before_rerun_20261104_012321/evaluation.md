# RAG versus SimpleLLM after intervention-prompt changes

Evaluated on 4 November 2026 (Asia/Kolkata), using the same three recorded sessions
of `01_transport_assessment/intervention_student_003`, `qwen3.5:latest`, question,
temperature 0, 32,768-token context setting and output schema as the prior run.
The new inputs add descriptive Markdown metadata; the new prompts explain intervention
evaluation and distinguish session usefulness, delivery and outcomes. SimpleLLM inputs
explicitly label conversation positions and list earlier source session numbers.

## Current measurements

| Measure | RAG | SimpleLLM |
| --- | ---: | ---: |
| Model calls | 3 | 1 |
| Elapsed seconds | 129.409 | 75.261 |
| Total prompt characters including schemas | 61,702 | 35,088 |
| Existing final-field reference checks | 3/4 | 3/4 |
| Structurally valid, ordered timeline entries | 3 | 3 |
| Session helpfulness reported yes | 3/3 | 3/3 |

SimpleLLM used 41.8% less elapsed time and 43.1% fewer total prompt characters than
RAG in this run. These are characters, not tokens. Both returned barrier unresolved,
attendance improvement unknown, intervention helpful yes, and service delivery null.

The unchanged reference expects intervention helpfulness to remain unknown. Both
failed this check. Both left service delivery unknown while claiming helpfulness,
despite explicit prompt instructions requiring delivery and subsequent usefulness
evidence. Session feedback supports a helpful meeting, but should not automatically
establish intervention effectiveness. Direct in-session activities can constitute
support, so delivery scope also requires care: SimpleLLM names the completed
activity as its intervention, yet still leaves that activity's delivery null.
These outputs illustrate semantic inconsistency rather than a schema failure.
The historical delivery check accepts false or null; it is a narrow external-support
reference and is not a universal scoring rule for interventions delivered in-session.

## Narrative and chronology review

Review is based on the spoken transcripts, not the excluded outcome notes. The following
are qualitative observations, not additional automated accuracy scores.

| Transcript requirement | RAG observation | SimpleLLM observation |
| --- | --- | --- |
| Session 1: recording two journey times is a future action | Mentions recording journey times only conditionally; loses the count of two | Explicitly retains two journey times as pending |
| Session 2: recording journey times is reported completed | Retains completion and count of two | Retains completion, linked to session 1 |
| Session 2: checking an alternative departure becomes the next agreed task | Mentions it conditionally in next steps rather than clearly tracking the agreement | Explicitly tracks it as pending |
| Session 3: alternative-departure completion is unclear | Narrative acknowledges uncertainty, but detail is pending and summary says unclear/uncompleted | Correctly labels completion unknown |
| Session 3: ask support office about assessment evidence | Omits this specific new agreed task | Retains this task and possible teacher explanation |
| Preserve the original crossing barrier in final findings | Final primary concern retains the crossing | Final primary concern becomes generic; alternative-route uncertainty survives elsewhere |
| Keep final conclusion cumulative | Retains the route issue, but final narrative mainly describes session 3 | Refers to earlier task, but does not fully synthesize initial mapping and completed journey-times work |

SimpleLLM follows the central action chronology: it does not mark the journey-times
task complete in session 1, introduces alternative-departure checking in session 2,
and leaves its completion uncertain in session 3. This is evidence of chronology
handling for these actions in this run, not proof of temporal isolation or complete
absence of information leakage. SimpleLLM calls the third session a "Final follow-up"
even though the last supplied record need not mark programme completion.

Both now capture positive session-level feedback. Both still overstate some claims:
RAG's final primary concern introduces "occasional absence" where the cited dialogue
only establishes difficulty affecting some school days, and its prose repeatedly
claims no external support was delivered rather than consistently preserving uncertainty.
SimpleLLM's first conclusion also states non-receipt broadly, although the student's
initial report does explicitly deny receiving extra support at that point.

## Comparison with prior prompts

Prior artifacts are preserved in [prior_prompt_run](prior_prompt_run/evaluation.md).

| Measure | Prior RAG | Current RAG | Prior SimpleLLM | Current SimpleLLM |
| --- | ---: | ---: | ---: | ---: |
| Elapsed seconds | 108.05 | 129.409 | 71.55 | 75.261 |
| Prompt characters | 48,835 | 61,702 | 30,733 | 35,088 |
| Existing reference checks | 4/4 | 3/4 | 4/4 | 3/4 |

Compared with the earlier saved narrative review, SimpleLLM improves initial action
specificity (including two journey times) and recognizes session helpfulness. It still
loses the crossing detail in its final primary concern. Both regress on the conservative
intervention-helpfulness indicator. Consequently the revised prompts improve framing
and some extraction details, but this run does not demonstrate overall accuracy improvement.

## Verification and limits

All 56 offline tests passed, including chronological input order, sparse source session
numbers, metadata propagation, cutoff isolation, and exclusion of outcome notes.
Offline tests ran under Python 3.14.8; the executed notebook's existing kernel used
Python 3.10.19. Neither run establishes validation under the project's declared Python
3.12–3.13 range. Both live responses validated against the existing findings schema.

This is one synthetic case and one sequential run per method, with RAG first.
Startup, cache effects and generation variability were not controlled. Changes combine
prompt wording and metadata, so their individual effects are not isolated. Four final-field
checks do not measure full narrative quality. More explicit chronological prompting does
not physically hide later sessions from SimpleLLM. The findings do not establish general
extraction accuracy or real-world intervention effectiveness.

Artifacts: [comparison](comparison.json), [RAG report](rag/conclusion.json),
[SimpleLLM report](simple/conclusion.json), [exact RAG requests](rag/requests.json),
[exact SimpleLLM request](simple/requests.json), and
[executed notebook](../../notebooks/intervention_extraction_evaluation.ipynb).

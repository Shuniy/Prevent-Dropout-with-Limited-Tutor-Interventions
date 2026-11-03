# RAG versus all-sessions LLM: one intervention

Evaluated `01_transport_assessment/intervention_student_003`, all three recorded sessions, with
`qwen3.5:latest`, temperature 0 and a 32,768-token context setting. Both
methods received the same question and used the existing findings contract.
The notebook was executed with Python 3.10.19; the offline
feature suite was also checked separately under supported Python 3.12.

| Measure | Session-by-session RAG | All-sessions LLM |
| --- | ---: | ---: |
| Model calls | 3 | 1 |
| Elapsed seconds | 108.05 | 71.55 |
| Total prompt characters, including schemas | 48,835 | 30,733 |
| Final indicator reference checks passed | 4/4 | 4/4 |
| Valid ordered timeline entries | 3 | 3 |

The single-call method took 33.8% less elapsed time and supplied 37.1%
fewer total prompt characters in this run. These are descriptive measurements from
one sequential run; startup and caching were not controlled, and characters are
not tokens.

Both final results reported the barrier unresolved (`no`), school-attendance
improvement `unknown`, intervention helpfulness `unknown` and external service
delivery `null`. All three public outcome indicators agreed. The reference was
fixed from spoken transcript excerpts before generation; it was not sent to the
model. Four passing checks cover these final fields, not the full narrative.

## Review of the saved narratives

- Both preserved the session-2 report that recording journey times was completed.
  Both kept the later alternative-departure task unconfirmed. Simple LLM labeled
  that task `unknown`; RAG labeled it `pending` while its summary described
  completion as unclear. `unknown` more directly matches the reported uncertainty.
- RAG retained the specific instruction to record **two actual journey times**
  in its initial tracked details. Simple LLM initially used the generic label
  “Agreed Action” and a less specific next step. Simple LLM recovered the journey
  times task in session 2 but did not retain the count of two.
- RAG kept the crossing/route barrier explicit in the final primary concern.
  Simple LLM's final concern became broader (persistent difficulty and task
  uncertainty), although alternative-route verification remained in its details.
- RAG marked session helpfulness `yes`; Simple LLM marked it `unknown` in all
  three entries despite explicit student statements that examples clarified the
  step and that writing down a small step was less confusing. This is a missed
  positive session-level signal in the single-call output; intervention-level
  helpfulness correctly remained unknown in both.
- Both generated some prose that stated no external support was delivered, while
  the structured delivery field remained `null`. The more conservative wording
  is that delivery was not established. Schema validation does not resolve this
  difference between narrative certainty and the structured field.

## Implementation and interpretation

Simple LLM is now the default for `Intervention` and the school CLI. It passes all
selected conversations together with no index, retrieval or prior generated
memory. It requests the existing timeline in one response and derives the final
conclusion from its last entry. Session JSON filenames, final private report fields
and public school outputs keep their existing structure. The complete response
must validate before session files are saved. Recorded attendance remains available
if generation fails. Choose `--method rag` to retain the previous behavior,
including partial validated session files if a later call fails.

The simple timeline is a retrospective reconstruction: all selected sessions are
visible in the single call. Its prompt asks for each entry to describe only what
was known by that session, but RAG provides stronger temporal isolation. This one
synthetic intervention supports the observed reduction in calls and elapsed time;
it does not establish general extraction accuracy or real-world effectiveness.

Artifacts: [RAG report](rag/conclusion.json), [simple report](simple/conclusion.json),
[machine-readable comparison](comparison.json), and
[executed notebook](../../notebooks/intervention_extraction_evaluation.ipynb).

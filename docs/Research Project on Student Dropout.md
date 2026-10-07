{\rtf1\ansi\ansicpg1252\cocoartf2907
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;\f1\fnil\fcharset0 LucidaGrande;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww17280\viewh13200\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs36 \cf0 I am developing a research project on **fair sequential allocation of limited mentoring/support resources for students at risk of school dropout**.\
\
I have uploaded/provided several real dropout/education datasets, generated or semi-synthetic datasets, student datasets, and a research-plan document. I want you to act as a research data scientist and simulation-design reviewer.\
\
Do not start by building a large system. First audit the available data and determine what can and cannot legitimately be supported by it.\
\
## Research concept\
\
The intended system works approximately as follows.\
\
We begin with a population of students. Some students have higher risk of eventually dropping out, but dropout should not simply be predetermined.\
\
A limited number of mentors/support workers are available. Because capacity is limited, not every student can receive support and some mentors may remain unused depending on eligibility, capacity and allocation.\
\
Students receiving support undergo a configurable number of intervention sessions, initially consider approximately five sessions as an experimental setting.\
\
A sequential allocation algorithm, most likely a constrained MDP/rolling-horizon allocator, periodically decides which students should receive which mentor/support intervention.\
\
Random allocation, longest-waiting, predicted-risk priority, benefit-based allocation and possibly an RMAB/bandit method should be considered as baselines rather than automatically combining every method into the main algorithm.\
\
Intervention effects occur inside an explicit simulation environment. The environment should determine the true latent effect of interventions using transparent stochastic transition assumptions.\
\
Examples of mutable student factors might include attendance, engagement, academic difficulty, transport access, financial barriers, family-contact status, learning support need or similar variables actually justified by the datasets and project definition.\
\
Mentor/intervention notes are generated from events and observable student information. The notes should not reveal the complete latent simulator state or future dropout outcome.\
\
An LLM processes those notes and extracts structured observations. Those observations update the controller's estimated student state.\
\
The allocator should normally receive the estimated/observed state, not the simulator's hidden ground-truth state.\
\
The updated state is used in the next allocation iteration.\
\
At the end of the simulation, policies are compared using retention/dropout outcomes, intervention utilization, cost/resource usage, waiting time and fairness/access metrics.\
\
RAG may later retrieve evidence concerning intervention options, programme eligibility and support guidance.\
\
QLoRA may later be used for a narrow extraction task if experiments show that prompting alone is inadequate.\
\
The LLM must NOT be treated as the causal ground truth for whether an intervention succeeds. Intervention effects must come from the explicit environment/transition model.\
\
## Task 1 \'97 Inventory all supplied data\
\
Inspect every relevant dataset and document available in the workspace.\
\
For every file determine:\
\
- source/provenance if known;\
- real, synthetic or semi-synthetic status;\
- unit of observation;\
- number of records;\
- number and type of fields;\
- student identifier fields;\
- target/outcome fields;\
- demographic/contextual fields;\
- attendance/performance fields;\
- temporal information;\
- school/household identifiers;\
- missing data;\
- duplicated records;\
- intervention/action information;\
- mentor information;\
- free-text/note information;\
- survey weights or sampling structure;\
- licensing/access limitations if available in accompanying documentation.\
\
Do not assume that similarly named variables mean the same thing across datasets.\
\
## Task 2 \'97 Determine what each dataset can legitimately support\
\
Classify the role of each dataset.\
\
Possible roles include:\
\
1. real dropout-risk prediction;\
2. grounding synthetic student population distributions;\
3. estimating correlations/joint distributions;\
4. temporal modelling;\
5. validation of synthetic populations;\
6. fairness/subgroup analysis;\
7. intervention-effect estimation;\
8. mentor allocation;\
9. note-generation grounding;\
10. unsuitable for the proposed use.\
\
Clearly distinguish observational prediction from causal intervention estimation.\
\
If a dataset contains dropout labels but no intervention histories, state explicitly that it does NOT directly identify the causal effect of mentoring, financial support, transport support or other interventions.\
\
Check whether any dataset actually contains longitudinal intervention/action/outcome information before proposing treatment-effect estimation.\
\
## Task 3 \'97 Audit the dropout target\
\
For each real dataset containing a dropout-related target:\
\
identify exactly how dropout is defined.\
\
Check whether the variable actually means:\
\
- permanent school dropout;\
- temporary withdrawal;\
- university-course withdrawal;\
- enrolment status;\
- failure;\
- absence;\
- academic underperformance;\
- another outcome.\
\
Do not silently convert failure, poor grades or absence into dropout.\
\
Calculate the empirical dropout prevalence where appropriate.\
\
Treat this empirical prevalence as a descriptive dataset baseline, not automatically as the untreated counterfactual dropout rate of the simulator.\
\
## Task 4 \'97 Leakage analysis\
\
Perform a detailed leakage audit.\
\
Look for variables containing information only available after the prediction time, such as:\
\
- final grades;\
- final outcome;\
- future-semester performance;\
- withdrawal dates;\
- future attendance;\
- intervention outcomes;\
- variables derived directly from the target.\
\
Recommend a realistic prediction time point and list features available at that time.\
\
Create explicit recommendations for train/validation/test splitting.\
\
Ensure the same student, household, school trajectory or synthetic scenario does not accidentally appear in both training and test sets where this would create leakage.\
\
## Task 5 \'97 Evaluate the student schema\
\
From the available real datasets, determine which variables should belong to the project's canonical Student schema.\
\
Separate the schema into:\
\
STATIC OR SLOWLY CHANGING VARIABLES\
\
Examples might include age or school context.\
\
MUTABLE STATE VARIABLES\
\
Examples might include attendance, engagement or academic progress.\
\
OBSERVED VARIABLES\
\
Information actually available to the allocator.\
\
LATENT SIMULATOR VARIABLES\
\
Information used internally by the simulation but hidden from the allocator.\
\
OUTCOME VARIABLES\
\
Such as retained, withdrawn or dropout status.\
\
SENSITIVE/AUDITED VARIABLES\
\
Variables potentially used for fairness evaluation.\
\
Do not invent sensitive attributes from free-text notes.\
\
Recommend a canonical machine-readable schema and map every source dataset field into it where possible.\
\
For fields unavailable in the real data, mark them explicitly as:\
\
UNKNOWN / NOT AVAILABLE\
\
rather than silently generating them.\
\
## Task 6 \'97 Audit synthetic and semi-synthetic student data\
\
Identify all student records that were generated synthetically or transformed from real datasets.\
\
Evaluate whether the synthetic data reasonably reflects the real source population.\
\
Compare, where applicable:\
\
- numerical distributions;\
- categorical distributions;\
- missingness;\
- class balance;\
- important pairwise relationships;\
- correlation structure;\
- subgroup proportions;\
- target relationships;\
- impossible combinations;\
- duplicate or near-duplicate records;\
- outliers;\
- unrealistic values;\
- suspiciously deterministic relationships.\
\
Use appropriate statistics and visualisations.\
\
For important numeric features consider distribution plots, quantiles, standardized differences and KS/Wasserstein-style comparisons where meaningful.\
\
For categorical features compare frequency distributions and suitable divergence/distance measures.\
\
For joint behaviour examine correlations and selected conditional relationships relevant to dropout.\
\
Do not demand that synthetic data exactly duplicate the real dataset. Identify which deviations are intentional versus unexplained.\
\
Most importantly, check whether the generated synthetic dataset contains columns representing intervention outcomes or causal improvements that are unsupported by the source data.\
\
Classify every synthetic variable or parameter as one of:\
\
OBSERVED FROM DATA\
ESTIMATED FROM DATA\
DERIVED\
EXTERNALLY INFORMED\
ASSUMED FOR SIMULATION\
GENERATED\
\
Produce an assumptions/provenance register.\
\
## Task 7 \'97 Evaluate whether my simulator design is identifiable from the data\
\
Determine which parts of the planned simulator can be estimated from the supplied datasets and which must remain explicit research assumptions.\
\
In particular assess whether we can estimate:\
\
P(dropout | observed student features)\
\
versus quantities such as:\
\
P(next_state | current_state, no additional intervention)\
\
and\
\
P(next_state | current_state, intervention)\
\
Do not treat predictive correlations as intervention effects.\
\
Recommend reasonable ways of parameterising the unsupported transition effects for a semi-synthetic simulation, including:\
\
- weak-effect scenario;\
- moderate-effect scenario;\
- zero-effect scenario;\
- delayed-effect scenario;\
- heterogeneous-response scenario;\
- adverse/no-benefit stress test.\
\
The goal is sensitivity analysis, not manufacturing evidence that mentoring works.\
\
## Task 8 \'97 Define the simulation baseline\
\
Recommend two separate baselines.\
\
First, calculate an empirical descriptive dropout prevalence from the relevant real dataset wherever valid.\
\
Second, define the actual experimental control as a simulation policy representing usual support / no additional scarce intervention.\
\
The important policy comparison should therefore resemble:\
\
Usual support\
vs\
Random feasible allocation\
vs\
Waiting-time/round-robin allocation\
vs\
Highest predicted risk\
vs\
Estimated benefit/resource allocation\
vs\
Fair constrained allocation\
vs\
Proposed uncertainty-aware sequential allocation.\
\
All policies must receive equivalent information and operate under identical capacity and budget conditions.\
\
## Task 9 \'97 Review the mentor model\
\
Determine what mentor variables are actually available from data.\
\
If mentor data is synthetic, clearly state that.\
\
Recommend a minimal mentor schema including only defensible properties such as:\
\
mentor_id,\
skills/support types,\
availability,\
capacity,\
current caseload,\
eligible student/intervention types,\
cost or time per session.\
\
Do not invent complex personality/compatibility effects unless they serve an explicit experiment.\
\
Resolve this modelling rule:\
\
Not every mentor must receive a student.\
\
Active mentors may have a configurable capacity, initially perhaps 1\'962 simultaneous students.\
\
Not every eligible student receives a mentor because support is scarce.\
\
Five sessions should be treated as a configurable intervention duration rather than a universal factual assumption.\
\
## Task 10 \'97 Review the intervention model\
\
Propose a small initial action space rather than dozens of interventions.\
\
Use interventions justified by the chosen context and available evidence.\
\
Separate:\
\
offer,\
acceptance,\
delivery,\
completion,\
outcome.\
\
Intervention effects should modify only mutable state variables.\
\
Do not allow an intervention to directly overwrite the dropout label.\
\
The transition should conceptually be:\
\
student state at t\
+ intervention/action\
+ uptake\
+ stochastic response\
+ external shocks\

\f1 \uc0\u8594 
\f0 \
student state at t+1\
\
and the resulting state then changes later dropout probability.\
\
## Task 11 \'97 Define the sequential decision model\
\
Based on the audited data and project goals, determine whether a constrained MDP / rolling-horizon constrained optimizer is the most defensible primary model.\
\
Define conceptually:\
\
state,\
observation,\
action,\
transition,\
reward/objective,\
resource constraints,\
mentor capacity,\
intervention duration,\
fairness constraints,\
episode,\
decision interval,\
terminal outcome.\
\
Do not force CMDP terminology where it is mathematically unjustified.\
\
Explain where an RMAB/bandit formulation would be useful as a baseline or simplified experiment.\
\
Explain separately how student, mentor and school entities can constitute a multi-agent simulation without requiring LLM agents.\
\
## Task 12 \'97 Define fairness evaluation\
\
Determine which fairness attributes are actually available or defensibly generated.\
\
Recommend a small number of clearly defined metrics.\
\
Consider:\
\
support offer rate among comparable-need eligible students,\
waiting time,\
worst-group retention,\
completed-support rate,\
mentor workload,\
resource allocation across groups.\
\
Do not equate equal allocation with fairness.\
\
Where sample sizes permit, report intersectional groups carefully.\
\
Any fairness constraint should have an explicit mathematical definition.\
\
## Task 13 \'97 Design the mentor-note experiment\
\
The note-generation pipeline must avoid circularity.\
\
Generate or construct structured observable facts first.\
\
Then produce mentor notes revealing only some of those facts.\
\
Notes should sometimes include:\
\
missing information,\
uncertain language,\
negation,\
conflicting statements,\
different dates,\
irrelevant information,\
partial improvement,\
failed interventions.\
\
The note should NOT contain:\
\
hidden simulator parameters,\
future dropout labels,\
future outcomes,\
the exact allocation reward,\
the true intervention-effect parameter.\
\
Create a separate ground-truth structured record against which extraction can be measured.\
\
Recommend an extraction schema containing at least:\
\
field,\
value,\
status,\
timestamp/source date,\
evidence span,\
unknown/conflicting status,\
optional calibrated confidence.\
\
Explain how to avoid evaluating an LLM only on notes produced by the same LLM/template family.\
\
## Task 13A \'97 Define exactly how LLM intervention processing updates the student state\
\
Design the precise pipeline through which mentor/intervention notes are converted into information that can be used in the next allocation round.\
\
The intended flow is:\
\
intervention occurs in simulator\

\f1 \uc0\u8594 
\f0  simulator updates the hidden true student state\

\f1 \uc0\u8594 
\f0  observable events occur\

\f1 \uc0\u8594 
\f0  mentor/intervention notes are generated\

\f1 \uc0\u8594 
\f0  LLM processes the notes\

\f1 \uc0\u8594 
\f0  LLM extracts structured observations\

\f1 \uc0\u8594 
\f0  estimated/observed student profile is updated\

\f1 \uc0\u8594 
\f0  dropout-risk model recalculates estimated risk\

\f1 \uc0\u8594 
\f0  updated estimated state and risk are supplied to the sequential allocator/CMDP\

\f1 \uc0\u8594 
\f0  next intervention allocation is selected.\
\
Keep the following concepts strictly separate.\
\
### 1. Hidden simulator state\
\
The simulator maintains the true synthetic state of the student.\
\
For example:\
\
financial_barrier = 0.72  \
attendance = 0.61  \
engagement = 0.43  \
academic_need = 0.55\
\
These values are used to simulate outcomes but should normally NOT be directly visible to the LLM or allocator.\
\
### 2. Intervention outcome generated by the simulator\
\
The simulator determines what actually happened after an intervention according to explicit stochastic transition assumptions.\
\
For example:\
\
financial_barrier: 0.82 
\f1 \uc0\u8594 
\f0  0.72  \
attendance: 0.55 
\f1 \uc0\u8594 
\f0  0.61  \
engagement: 0.40 
\f1 \uc0\u8594 
\f0  0.43\
\
The LLM must not invent these causal changes.\
\
### 3. Observable intervention information\
\
Only part of the true change should be visible in records or mentor notes.\
\
For example:\
\
\'93The student attended more regularly this week. The family continues to report difficulties paying transport costs. A transport-support application has been submitted and is awaiting approval.\'94\
\
### 4. LLM extraction result\
\
The LLM should convert the note into structured observations rather than directly outputting a new dropout probability or claiming that an intervention caused dropout reduction.\
\
An example output might resemble:\
\
\{\
  "attendance": \{\
    "status": "observed",\
    "trend": "improving",\
    "evidence": "student attended more regularly this week",\
    "confidence": 0.88\
  \},\
\
  "transport_barrier": \{\
    "status": "still_present",\
    "trend": "unchanged_or_uncertain",\
    "evidence": "family continues to report difficulties paying transport costs",\
    "confidence": 0.91\
  \},\
\
  "transport_support": \{\
    "status": "pending",\
    "evidence": "application has been submitted and is awaiting approval",\
    "confidence": 0.97\
  \}\
\}\
\
The exact schema should be designed based on the audited datasets and simulator variables.\
\
The LLM should be able to represent:\
\
- improved;\
- worsened;\
- unchanged;\
- present;\
- resolved;\
- partially resolved;\
- pending;\
- unknown;\
- contradictory;\
- insufficient evidence.\
\
Do not force a numeric value when the note only supports a qualitative observation.\
\
### 5. Estimated student-state update\
\
Define a deterministic and auditable mechanism for translating extracted observations into the controller's estimated student state.\
\
For example:\
\
previous estimated attendance = 0.55\
\
LLM evidence indicates improved attendance.\
\
The state-update component might produce:\
\
estimated attendance = 0.63\
\
The LLM itself should preferably not arbitrarily choose the numeric update.\
\
Define the conversion/update rules separately in code or through a calibrated observation model.\
\
Where information is uncertain, preserve the uncertainty rather than pretending the new value is known exactly.\
\
### 6. Dropout-risk recalculation\
\
Once the estimated student profile has been updated, run the dropout-risk prediction model again.\
\
For example:\
\
P(dropout | estimated state at t) = 0.66\
\
after new observations:\
\
P(dropout | estimated state at t+1) = 0.54\
\
This probability must come from the risk model, not directly from the LLM.\
\
The change in predicted risk should not automatically be interpreted as the causal effect of the intervention.\
\
### 7. Feedback into sequential allocation\
\
The next CMDP/sequential-allocation decision should receive the updated estimated student state, relevant intervention history, resource state and current predicted risk.\
\
For example:\
\
student_id\
current estimated features\
predicted_dropout_risk\
previous interventions\
intervention completion status\
unresolved barriers\
observation uncertainty\
waiting time\
mentor/support eligibility.\
\
The allocator can then decide whether to:\
\
continue the same intervention,\
switch intervention,\
assign another support type,\
stop additional support,\
place the student back in the waiting pool,\
or allocate the scarce resource to another student.\
\
### 8. Preserve the distinction between true and estimated state\
\
The experiment should store both:\
\
TRUE SIMULATOR STATE\
\
and\
\
ESTIMATED CONTROLLER STATE.\
\
This is essential for evaluating information error.\
\
Design experiments comparing at least:\
\
A. Oracle allocator using true simulator state as a diagnostic upper-information condition.\
\
B. Allocator using perfectly structured observable information.\
\
C. Allocator using information extracted from mentor notes by the LLM.\
\
D. Allocator using deliberately noisy/missing notes.\
\
This allows measurement of how much allocation performance and fairness deteriorate because of information extraction errors.\
\
### 9. Evaluate the LLM processing stage separately\
\
Measure the LLM's intervention-processing performance using metrics such as:\
\
per-field precision/recall/F1,\
correct trend classification,\
unknown handling,\
unsupported assertion rate,\
negation errors,\
contradiction handling,\
temporal errors,\
confidence calibration where confidence is used.\
\
Then measure its downstream consequences:\
\
change in student ranking,\
change in intervention assignment,\
assignment disagreement with structured-information allocation,\
difference in simulated retention,\
difference in access/fairness,\
unnecessary interventions,\
missed interventions.\
\
The research should therefore distinguish:\
\
LLM extraction quality\
\
from\
\
dropout prediction quality\
\
from\
\
allocation quality\
\
from\
\
simulated intervention effectiveness.\
\
### 10. Important prohibition\
\
Do NOT design the LLM output as:\
\
\'93Intervention successful: dropout probability reduced from 70% to 40%.\'94\
\
unless that probability was independently calculated by the risk model after an auditable state update.\
\
The LLM's role is to extract and structure evidence from notes.\
\
The simulator determines the hidden intervention response.\
\
The observation-update component converts extracted evidence into estimated state.\
\
The dropout model estimates risk.\
\
The CMDP/sequential allocator makes the next resource-allocation decision.\
\
## Task 14 \'97 Evaluate the role of RAG and QLoRA\
\
Treat RAG and QLoRA as experiments, not requirements.\
\
RAG should primarily retrieve evidence concerning support options, programme rules, eligibility, guidance or evidence-backed explanations.\
\
QLoRA should be considered only if a narrow extraction benchmark shows an important measurable weakness.\
\
Define appropriate ablations such as:\
\
structured ground truth,\
prompted extraction,\
prompted extraction + RAG where relevant,\
fine-tuned extraction,\
fine-tuned extraction + retrieval where relevant.\
\
Do not use QLoRA simply because it is available.\
\
## Task 15 \'97 Recommend research questions\
\
Based on the actual datasets and what they support, refine the main research question.\
\
A candidate direction is:\
\
\'93How does uncertainty and error in mentor-note-derived student information affect the effectiveness and fairness of sequential allocation of limited dropout-prevention support?\'94\
\
Assess whether the available data supports this question.\
\
Suggest no more than 3\'964 primary research questions.\
\
## Task 16 \'97 Produce concrete outputs\
\
After performing the audit, create or present:\
\
A. Dataset inventory\
\
B. Dataset suitability assessment\
\
C. Canonical student schema\
\
D. Mentor schema\
\
E. Field mapping from each real dataset to the canonical schema\
\
F. Leakage report\
\
G. Synthetic-data validation report\
\
H. Variable provenance/assumptions register\
\
I. Recommended dropout prediction baseline\
\
J. Recommended simulator state and transition design\
\
K. Proposed intervention action space\
\
L. Recommended sequential allocation formulation\
\
M. Fairness metrics\
\
N. Experimental baselines\
\
O. Note-generation/extraction design\
\
P. RAG/QLoRA role\
\
Q. Key research risks and validity threats\
\
R. A revised end-to-end architecture\
\
S. A recommended implementation order.\
\
Where useful, calculate statistics and generate plots directly from the provided datasets rather than reasoning only from column names.\
\
Do not modify or overwrite source datasets.\
\
Do not invent information that is absent from the datasets.\
\
Clearly distinguish findings from assumptions and recommendations.\
\
## Final task \'97 Generate a Codex implementation prompt\
\
After completing the dataset and methodology audit, create a separate detailed prompt titled:\
\
CODEX IMPLEMENTATION PROMPT\
\
This prompt will be copied into Codex and used against my local project repository.\
\
The Codex prompt must use the actual findings from this audit rather than generic placeholder assumptions.\
\
It should instruct Codex to implement the project incrementally.\
\
The recommended implementation sequence should approximately be:\
\
data ingestion and validation\

\f1 \uc0\u8594 
\f0  canonical schemas\

\f1 \uc0\u8594 
\f0  preprocessing\

\f1 \uc0\u8594 
\f0  dropout prediction baselines\

\f1 \uc0\u8594 
\f0  synthetic/semi-synthetic population generator\

\f1 \uc0\u8594 
\f0  environment/state transition simulator\

\f1 \uc0\u8594 
\f0  usual-support control\

\f1 \uc0\u8594 
\f0  simple allocation baselines\

\f1 \uc0\u8594 
\f0  fairness metrics\

\f1 \uc0\u8594 
\f0  constrained sequential allocator\

\f1 \uc0\u8594 
\f0  experiment runner\

\f1 \uc0\u8594 
\f0  mentor/intervention event generation\

\f1 \uc0\u8594 
\f0  note-generation benchmark\

\f1 \uc0\u8594 
\f0  LLM extraction interface\

\f1 \uc0\u8594 
\f0  downstream allocation comparison\

\f1 \uc0\u8594 
\f0  RAG\

\f1 \uc0\u8594 
\f0  optional QLoRA.\
\
The Codex prompt must tell Codex to build tests throughout the implementation, particularly for:\
\
data leakage,\
schema validation,\
resource constraints,\
mentor capacity,\
budget accounting,\
state transitions,\
forbidden access to latent variables,\
reproducible random seeds,\
fairness calculations,\
train/test separation,\
tiny allocation instances where correctness can be manually verified.\
\
Prefer a modular repository structure such as:\
\
configs/\
data/\
src/data/\
src/models/\
src/environment/\
src/policies/\
src/language/\
src/evaluation/\
tests/\
results/\
docs/\
\
However, if a repository already exists, Codex should inspect and adapt to the existing structure instead of destructively reorganising it.\
\
The Codex prompt should explicitly instruct Codex NOT to implement RAG, QLoRA, LangGraph, complex multi-agent orchestration or a dashboard before the data pipeline, prediction baselines, simulator and simple allocation baselines have passed their tests.\
\
The generated Codex prompt should contain enough context that Codex can begin implementing the project without having to infer the research methodology itself.}
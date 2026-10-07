# Research plan for fair allocation of school dropout prevention support

Prepared for Sphinx on 5 October 2026

## Recommendation and scope

Build a reproducible, semi-synthetic research benchmark for allocating limited educational support when information comes partly from imperfect teacher notes. Use real education data to ground population characteristics and observational patterns, an explicit stochastic simulator for intervention responses, and independently evaluated language models for extracting information and retrieving evidence. Use a mathematical allocator to enforce resource constraints and an explicitly chosen access-fairness policy.

The recommended research title is **Fair sequential allocation of educational support under uncertainty in language-derived student information**. The motivating application is preventing school dropout among disadvantaged children. Before field evaluation, describe the output as a simulation study and decision-support prototype; do not claim demonstrated dropout prevention.

The primary question is: **How do errors and missing information in language-derived student records affect the effectiveness and equity of limited educational support, and can uncertainty-aware allocation reduce those effects?**

This provides a coherent role for LLMs, RAG, optional QLoRA, multi-agent modelling, and sequential decision-making. It also defines a testable contribution beyond combining existing technologies. A stronger game-theory version would study repeated matching of students to tutors with preferences and strategic reports; treat that as an alternative research focus or a later extension.

The quantities, workloads, model settings, experiment sizes, and timeline below are proposed starting points, not findings from published studies or promises about runtime.

## Research search and limits

This is a targeted scoping review, not a systematic review or proof of novelty. Google Scholar's search page could not be accessed in this environment. Papers were discovered through scholarly web searches and checked against proceedings, author preprints, institutional repositories, and official dataset pages. Some records were assessed from abstracts and documentation rather than full-text replication. No dataset was downloaded or audited row by row, and no experiment has yet been run.

Useful Google Scholar searches to repeat manually:

- `school dropout early warning randomized controlled trial intervention`
- `education intervention allocation causal policy learning fairness`
- `restless bandits fairness multi worker intervention`
- `language models resource allocation decision language model`
- `language model information extraction downstream allocation fairness`
- `school choice matching constraints strategyproofness`
- `LLM human simulation causal validity`

For the project literature log, record title, year, venue or preprint status, population, data access, action space, objective, constraints, baselines, evaluation setting, limitations, and code availability. Follow references and forward citations from the closest papers. Separate schoolchildren from university students and observational prediction from causal intervention evaluation. Search updates and inspect full methods before asserting a new research gap.

## What the existing research contributes

| Research | Established contribution | Implication for this project |
| --- | --- | --- |
| Haimovich, Vazquez and Adelman, *Scalable Early Warning Systems for School Dropout Prevention*, World Bank working paper, 2021 [1] | A 4,000-school randomized trial in Guatemala evaluated a programme combining guidance, training and other early-warning components. The paper reports a 1.3 percentage point reduction in dropout among schools assigned to the programme. | An actual support programme can be evaluated causally. Do not attribute the whole programme effect to prediction alone or reuse it as the effect of an individual tutoring session. |
| UNICEF, *Building a predictive early warning system for school dropout in India*, 2026 [2] | Describes state-level systems linking identification with teacher-led support and referrals. | Establishes practical relevance in India. This programme report is not, by itself, a randomized evaluation of the proposed algorithm. |
| Herlihy et al., *Planning to Fairly Allocate*, preprint first posted 2021 [3] | ProbFair studies positive lower bounds on intervention probabilities within a restless-bandit allocation problem. | A fair-allocation baseline; probabilistic access does not automatically imply fair realized outcomes. |
| Li and Varakantham, *Efficient Resource Allocation with Fairness Constraints in Restless Multi-Armed Bandits*, 2022 [4] | Planning and learning methods for constrained fair RMAB allocation. | Fairness-constrained sequential allocation is established prior work; changing the application alone may not provide sufficient novelty. |
| Biswas et al., *Fairness for Workers Who Pull the Arms*, 2023 [5] | Models heterogeneous workers, intervention costs, individual budgets and worker-load fairness. | Useful when tutor qualifications, worker capacity and beneficiary access must all be considered. |
| Ou et al., *Networked Restless Multi-Armed Bandits for Mobile Interventions*, AAMAS 2022 [6] | Network effects couple the rewards of different arms. | Peer effects need an explicit coupled model; ordinary independent-arm index methods lose their usual justification. |
| Behari et al., *A Decision-Language Model for Dynamic Restless Multi-Armed Bandit Tasks in Public Health*, NeurIPS 2024 [7] | Translates language preferences into reward code and evaluates proposed rewards through simulations. | LLM-guided bandit allocation already exists. Its LLM component was demonstrated in simulation; do not conflate that with an LLM field deployment. |
| Verma et al., *Balancing Act*, preprint 2024 [8] | Uses an external adjudicator and social welfare functions to select among LLM-designed rewards. | An external optimizer or fairness adjudicator alone is not a novel contribution. |
| Parthasarathy et al., *Multilinguality in LLM-Designed Reward Functions for Restless Bandits*, preprint 2025 [9] | Investigates performance and fairness changes across prompt languages and complexity. | A multilingual extension must account for existing work and use competent human annotation. |
| Abdulkadiroğlu and Sönmez, *School Choice A Mechanism Design Approach*, AER 2003 [10] | Formalizes educational assignment through mechanism design. | Foundation for tutor matching, preference elicitation and incentives. Its guarantees do not transfer automatically to new quotas or repeated matching. |
| Jiang and Li, *Doubly Robust Off-policy Value Evaluation for Reinforcement Learning*, ICML 2016 [11] | Evaluates policies using historical trajectories under specified assumptions. | Relevant only if action, outcome and behaviour-policy information are available with adequate support and defensible confounding assumptions. |
| Gui and Toubia, *The Challenge of Using LLMs to Simulate Human Behavior*, preprint initially 2023, subsequently revised [12] | Shows causal-validity problems in LLM simulations of counterfactual behaviour. | Use explicit transition models for the main benchmark; plausible LLM role-play is not validated evidence about children. |
| Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, NeurIPS 2020 [13] | Combines retrieval with generation. | Technical foundation for an evidence assistant, not a guarantee of correct eligibility or causal reasoning. |
| Dettmers et al., *QLoRA*, NeurIPS 2023 [14] | Efficient adapter training on a quantized base model. | Useful for a focused extraction experiment after establishing prompting baselines. |

The candidate gap from this scan is the propagation of **note-extraction uncertainty into repeated, capacity-constrained educational allocation**, especially when note quality differs between groups. This remains a hypothesis about the literature until a closer full-text and citation review is completed.

## Implementation directions

| Direction | Main question and method | Data requirement | Suitability |
| --- | --- | --- | --- |
| Risk prediction and optimization | Predict risk; prioritize by risk or assumed intervention benefit under a budget using integer optimization. | Observational records for risk; effect assumptions or action logs for benefits. | Essential baseline and simplest prototype. Risk is not treatment benefit. |
| Causal policy learning | Estimate who benefits from which support using uplift models, causal forests or doubly robust learners, then optimize assignment. | Randomized intervention data or strong observational action histories and identification assumptions. | Strongest route to evidence about real interventions, but currently data-gated. |
| Sequential allocation | Model changing student states, delayed effects, worker capacity and recurring support using constrained planning or RMABs. | Longitudinal observations plus a simulator or identified action-dependent transitions. | Recommended computational core. Start with rolling-horizon planning. |
| Matching and mechanism design | Match students to tutors considering preferences, availability, quotas and truthful reporting. | Preferences and compatibility data, initially synthetic if necessary. | Best fit if game theory is the main intellectual goal. Can be a separate paper. |
| LLM extraction and evidence retrieval | Convert notes into sourced facts and retrieve relevant support evidence; measure downstream allocation changes. | Labelled note benchmark, evidence corpus, structured case records. | Recommended LLM contribution. |
| Multi-agent LLM negotiation | Let schools or service teams propose allocations and negotiate, then validate the result. | Explicit agent objectives and information; realistic case and capacity inputs. | Experimental comparison, not the default controller. Match token and information budgets. |
| Network-aware intervention | Model peer or household effects and compare coupled planning with independent-arm methods. | Network structure and plausible interaction effects, or explicitly synthetic graphs. | Later extension; substantially increases validity and computational demands. |

Do not implement all seven directions. The core project should combine sequential allocation with the language-information experiment. Select either matching or network effects as a follow-on once the core result is stable.

## Real versus synthetic data

**The best eventual evidence is real longitudinal intervention data from the target population. The best practical starting point for this independent project is a semi-synthetic environment.** Real data and simulation answer different questions.

| Approach | What it supports | What it cannot establish alone |
| --- | --- | --- |
| Real observational education data | Associations, subgroup distributions, predictive performance and some temporal patterns. | The counterfactual effect of unrecorded support actions. |
| Real intervention logs or randomized data | Treatment-effect and policy evaluation when identification and coverage conditions hold. | Automatic generalization to other regions, age groups, programmes or budgets. |
| Fully synthetic environment | Debugging, controlled stress tests, known latent states and counterfactual comparisons. | Realistic intervention effects or real-world impact. |
| Semi-synthetic environment | Tests of algorithms in empirically grounded populations across explicit assumptions. | Proof that simulated benefits will occur in real schools. |

A dataset containing family income, grades and a dropout label does not tell you what would have happened had a child received transport support. Adding an invented intervention column does not resolve this. Likewise, synthetic teacher notes attached to real rows remain synthetic text, and learned observational transitions are not automatically untreated transitions.

Use three clearly separated evidence layers:

1. Real data for population and observational modelling, with held-out validation.
2. Transparent assumed action effects for simulation, with parameter ranges including weak, zero and adverse effects.
3. A separate annotated note corpus for assessing language extraction and its downstream consequences.

Label the provenance of every variable and parameter as observed, estimated, externally informed, assumed, or generated. Never present assumed weekly trajectories as measured school records.

## Dataset and corpus requirements

| Source | Relevant contents and access | Appropriate use | Important limit |
| --- | --- | --- | --- |
| UCI Student Performance [15] | Secondary-school records from two Portuguese schools; grades, absences and contextual attributes. The official landing page lists 649 instances for its displayed dataset and provides subject-specific files. Public download, CC BY 4.0. | Small secondary-school schema prototype and feature-processing exercise. | It is primarily a performance dataset, not a verified longitudinal dropout/intervention dataset. Failure and absence are not dropout. Subject files may contain overlapping students. |
| UCI Predict Students' Dropout and Academic Success [16] | 4,424 higher-education students, 36 features, enrolment information and semester performance; dropout/enrolled/graduate target. Public download, CC BY 4.0. | Quick real-data prediction baseline. | University students, not disadvantaged schoolchildren. No sequential randomized support log. Avoid future semester leakage. |
| Open University Learning Analytics Dataset [17] | Linked student, registration, assessment and dated virtual-learning activity tables for seven modules. Openly published under CC BY 4.0. | Best of these options for a separate temporal pipeline benchmark. | Higher education; clicks are not physical attendance, and course withdrawal is not necessarily permanent educational dropout. No verified teacher-note or intervention-assignment corpus in the documented tables. |
| India Human Development Survey [18] | Public download route through ICPSR, with registration. IHDS-I covers 2004–05 and IHDS-II 2011–12; household and individual linking files are supplied. | Indian household and schooling distributions, and historical panel transitions where definitions and linkage allow. | Old, widely spaced waves; not weekly school data. Household sample size is not the eligible student sample size. Audit attrition and weights. |
| UNICEF MICS and MICS-EAGLE [19] | Country-specific household surveys on children, education and inequalities; foundational learning modules in relevant surveys. Microdata access is for legitimate research under the applicable process. | Ground a child-focused population in one selected country and survey year. | Usually not an intervention panel. Country, modules and ages differ; check the codebook before selecting a cohort. |
| UDISE+ [20] | Indian school education reports and dashboards; a separate data-sharing portal advertises login-based download. | External aggregate checks for an Indian scenario and school-resource context. | Do not assume unrestricted child-level longitudinal data, teacher notes or intervention logs are available. |
| EEF attendance evidence review, UNICEF and programme documents [21, 2] | Evidence reviews and programme descriptions. | RAG knowledge base and intervention design rationale. | Different jurisdictions and populations; preserve scope and distinguish guidance from causal evidence. |
| School or NGO partner | Potential pseudonymous attendance, support offers, uptake, worker time and subsequent outcomes. | Target-domain validation and eventual prospective evaluation. | Access, privacy, research approval, annotation and operational feasibility must be established. Availability is not assumed. |

Recommended selection:

- For an India-focused project, begin with the IHDS codebooks and UDISE+ aggregates. Use IHDS as historical population grounding and disclose its age. The weekly dynamics remain assumed.
- If geography is flexible, evaluate one suitably documented MICS survey for the chosen child age range. Do not assume it represents India.
- Use OULAD only as a separate technical benchmark for temporal prediction. Do not pool its rows with an Indian child population or transfer its transition estimates as if they were validated for that population.
- Use the UCI higher-education dataset for a short baseline exercise if it saves setup time; it need not become a core experiment.

Prefer original custodians over unverified Hugging Face or Kaggle mirrors. A mirror is useful only after checking its source, licence, transformations, record counts and checksums. This search did not identify and verify an open dataset containing all of schoolchildren, longitudinal support assignments, outcomes, teacher notes and resource constraints.

## Research questions and hypotheses

**RQ1:** How much do incorrect or missing extracted facts change support assignments and simulated outcomes? Compare ground-truth structured observations with template extraction, prompted LLM extraction and tuned extraction.

**RQ2:** Does an uncertainty-aware allocator improve the effectiveness–equity trade-off relative to a point-estimate allocator when note quality differs across groups? A null result is informative; conservative methods can also under-serve poorly documented students.

**RQ3:** Does RAG improve evidence-grounded intervention descriptions and eligibility handling, beyond simply adding more prompt context? Keep the underlying optimization objective fixed.

**RQ4, optional:** Does QLoRA improve extraction on unseen note authors, templates and missingness patterns enough to justify training and inference costs?

**RQ5, alternative game-theory extension:** How do preferences, capacity constraints and strategic reports affect repeated tutor matching, stability and access?

Pre-register the primary comparison as uncertainty-aware allocation versus the same allocator using point estimates, under a specified group-dependent observation-noise scenario. Define the primary outcome and acceptable equity/utility trade-off before tuning. All other comparisons are secondary or exploratory.

## Model the educational process

Start with an illustrative population of 500 students across five simulated schools, a 24-week horizon and weekly decisions. Expand only after profiling. Use a fixed age range such as 12–16 if the chosen data supports it. These are benchmark settings, not a representation of a particular district.

Maintain three distinct concepts:

- **Latent simulator state:** engagement, learning need, access barriers, response tendency and shock exposure.
- **Observed record:** available attendance summaries, past actions, consent/acceptance information, dated notes and verified contextual fields.
- **Estimated state:** what the controller infers from those observations, including unknown and conflicting fields.

The controller must not receive hidden states, future outcomes or the simulator's true response parameters. A clearly labelled oracle may access true parameters for a diagnostic comparison, but never future random draws.

Represent states such as engaged, intermittent attendance, persistent disengagement and withdrawn. Allow recovery and re-entry where appropriate. Model transfers and temporary absence separately from dropout if the data provides them. Define dropout through a documented administrative or study-specific enrolment criterion; do not silently equate four missed weeks with permanent dropout.

Begin with four actions:

1. Continue usual support and monitoring, with no extra intervention.
2. Offer an academic tutoring block.
3. Offer an attendance or family liaison contact.
4. Offer transport-support assessment or referral where such a programme is available in the scenario.

An offer, acceptance, delivery and successful outcome are different events. Include these stages, with explicit delay and resource accounting. Model realistic tutoring duration; do not assume one session instantly removes a long-standing barrier. Allow support to have no effect or adverse burden in stress tests.

Student and household agents govern uptake and evolving state; school agents hold local information and staffing limits; tutor or support-worker agents have skills and schedules; a central allocation component coordinates scarce resources. This is multi-agent modelling even if none of these actors uses an LLM. To claim game-theoretic analysis, additionally define utilities, information, feasible deviations and a solution concept. Merely naming several agents does not provide that analysis.

## Allocation objective and fairness

Define x[i,a,t] as whether student i is offered action a at week t. Maximize estimated incremental educational benefit over usual support, under the chosen transition model. For the main study, report simulated end-of-horizon retention as the primary outcome and attendance/engagement as separate secondary outcomes. Do not disguise a weighted proxy score as observed dropout reduction.

Constrain:

- At most one new support assignment per student per decision interval, unless the scenario explicitly permits combinations.
- Money and each staff skill's available hours.
- Programme capacity, eligibility, availability and accepted scheduling conditions.
- Multi-week commitments and already-reserved sessions.
- A predeclared access policy for comparable-need eligible students.

A practical initial access measure is the fraction of eligible students in each group who were offered appropriate support in a four-week window. Count unique students rather than repeated contacts. Define the eligible cohort at the start of the window, separately within broad need strata, so the algorithm cannot improve the denominator by changing whom it calls eligible. Measure offers and completed services separately to expose unequal uptake barriers.

For example, require a minimum offer coverage q for each audited group within an agreed need stratum, subject to a documented feasibility check. Also report access gaps, waiting time, worst-group retention and worker-load distribution. Repeat analyses for overlapping groups if sample sizes permit.

Equal allocation is not automatically fair when need differs. Outcome parity, access parity, minimum coverage and individual waiting-time guarantees are different objectives; do not claim to satisfy all of them. Sensitive attributes used for evaluation must come from authorized structured data or explicit synthetic labels, not LLM guesses.

When constraints conflict, never silently overbook staff or violate the budget. Return an infeasibility report and use a documented priority rule: hard resource and eligibility constraints remain hard; any permitted access-target shortfall is exposed as slack with its magnitude reported. A penalty on fairness is not a hard guarantee.

For uncertainty, begin with multiple plausible estimated states or transition parameter sets. Compare expected-value allocation with a robust or downside-sensitive criterion across those scenarios. Calibrate uncertainty on held-out labelled data; an LLM's self-reported confidence is not automatically a probability. Include a bounded manual-review option for unresolved consequential information. Measure whether conservative estimates systematically deny support to poorly documented groups.

## Architecture and responsibilities

| Component | Responsibility | Must not be assumed |
| --- | --- | --- |
| Observation generator | Produces dated records and note facts from current state. | Complete observation or access to future outcomes. |
| Extraction component | Returns structured facts, evidence spans, timestamps and unknown/conflict markers. | Inference of diagnoses, intentions or protected traits from vague wording. |
| Retrieval component | Finds source passages about support options and context. | That a retrieved passage applies to this location, age or current policy. |
| Eligibility catalogue | Stores human-reviewed machine-readable action rules. | An LLM-created rule is binding policy without review. |
| Allocator | Chooses feasible assignments under fixed objectives and constraints. | Correct inputs or known real treatment effects. |
| Validator | Recomputes budgets, capacity, eligibility and access statistics in code. | That an LLM auditor can certify mathematical constraints. |
| Explanation component | Explains the actual assignment using facts, source references and solver trace. | A plausible explanation proves the decision was causally effective. |
| Environment | Applies offers, uptake, delays and stochastic state transitions. | Simulated responses are measured behaviour. |

An ordinary orchestrated workflow is sufficient initially. Add LangGraph or a similar framework only if branching, retries and persistent state improve the implementation. An agent framework is not itself a research contribution.

## Step by step implementation

### Step 1 Freeze scope and evidence standards

Choose population, geography, decision horizon, support actions and primary metric. Write an assumptions register and a one-page protocol. Complete the literature matrix and identify the closest three comparison papers. Decide what would count as an informative negative result.

Deliverable: protocol, literature matrix, data-selection decision and claim boundaries.

### Step 2 Audit one primary dataset

Read its codebook and licence; obtain access through the custodian; inspect units, survey weights, timestamps, duplicated people, target definition and missingness. Build an explicit mapping from source fields to project fields. Keep unavailable fields unknown. Create split files before modelling.

For longitudinal data, split by time and school or person as applicable. The same student must not appear across train and test through different weeks or courses. For survey data, respect household and cluster structure. Use sampling weights when estimating population distributions and report effective sample sizes.

Deliverable: reproducible ingestion, data card and leakage audit.

### Step 3 Establish observational baselines

Fit logistic regression and a boosted-tree baseline to an appropriately defined observed outcome. Compare against simple attendance or missing-assignment rules when those fields exist. Evaluate calibration, PR-AUC and recall at a limited review capacity, with subgroup intervals. If the data has only grades, call the task performance prediction, not dropout prediction.

An OULAD experiment can use information available at a fixed week to predict later module withdrawal. Never include final_result, a future unregistration date or later submissions as input. Explicitly separate it from the child-focused simulation experiment.

Deliverable: a credible real-data benchmark, not a treatment-effect estimator.

### Step 4 Build the simulator without language models

Initialize a synthetic population using the audited distributions, preserving plausible joint structure rather than independently sampling all marginal fields. Fit or select a transparent baseline state-evolution model. Add an action-response component with explicit assumptions and distributions over uncertainty.

Implement reset, observation, step, state transition, resource accounting and logging. Include delayed effects, shocks, declining effects of redundant support, acceptance and re-entry. Keep random streams separate for population, observation noise, uptake and state transitions.

Validate population marginals and selected joint distributions against data. Check plausible no-extra-support trajectories, but label these as simulated usual-care assumptions because real observational histories may already contain support. Use at least two structurally different plausible transition families, not only different seeds of one convenient model.

Deliverable: versioned environment, parameter provenance and calibration plots.

### Step 5 Implement allocation baselines

Implement in this order:

1. Usual support only.
2. Random feasible allocation under the same resources.
3. Round-robin or longest-waiting eligible student allocation.
4. Highest predicted risk first.
5. Highest estimated incremental benefit per unit of resource, with a feasibility step.
6. Integer-program allocation using point estimates.
7. The same allocation with the chosen access constraints.
8. Uncertainty-aware fair allocation, the proposed method.

Use rolling-horizon optimization for sequential planning: project a short future window, reserve multi-week commitments, execute the first decision, observe, and replan. Start with one-step optimization to establish correctness. Report horizon and approximation limits.

An RMAB baseline can initially reduce the problem to binary action and independent arms. Check indexability or clearly label a numerical index heuristic. Do not present the standard binary Whittle method as an exact solution to heterogeneous, multi-action, network-coupled allocation.

On tiny instances, enumerate feasible assignments or solve exactly to verify the optimizer and validator. These are meaningful checks because violations would invalidate the experiment.

Deliverable: baseline results with identical resources and observations.

### Step 6 Create a separate note-extraction benchmark

Construct structured facts first, then write notes that reveal only some of them. Keep latent facts separate from observable facts. Include omitted information, explicit negation, uncertain statements, conflicting notes and dates. No dropout label or future intervention result should appear in the prompt that generates the note.

For example, “The parent reports that the bus did not run on Monday” supports a reported transport disruption. It does not establish chronic poverty, neglect, depression or family instability. If family circumstances are unmentioned, encode unknown rather than false.

Start with 300–500 development cases and a separately authored 150–200-case test set. If fine-tuning is justified, expand training to roughly 2,000–5,000 examples after checking label quality. These are planning quantities; assess sampling uncertainty before treating them as sufficient evidence.

Split by underlying scenario, household and writing template before generating paraphrases. Keep all paraphrases together. Include a held-out writing style or generator and independently written notes. Have two reviewers annotate a subset where possible and report disagreement. A second LLM alone is not independent human validation.

Represent extracted fields with value, evidence span, source date and status such as supported, unknown or conflicting. If adding confidence, evaluate calibration against held-out labels.

Deliverable: a documented synthetic note corpus and extraction benchmark.

### Step 7 Build the RAG evidence assistant

Collect approximately 20–40 relevant documents from official education sources and research programmes. Store document version, date, jurisdiction, age range, programme availability, source URL and evidence type. Keep guidance, eligibility and effect-size evidence distinguishable.

Use a lexical retrieval baseline first. Add small dense embeddings and compare retrieval quality. Tune passage length on actual questions; small embedding models may truncate long passages, so observe their tokenizer limits. Filter by jurisdiction and age before ranking when those are required conditions.

Create roughly 100–150 test questions, including unsupported, ambiguous, outdated and wrong-jurisdiction cases. Measure retrieval recall at k, source relevance, evidence-supported answers, citation correctness and appropriate abstention. Inspect a human-reviewed sample. Retrieved documents cannot command changes to system rules or execution of tools.

For eligibility, use a human-reviewed structured catalogue. RAG supplies relevant text and explanation evidence; it should not silently compile new binding policy rules. Estimates of intervention effects enter the simulator only through a documented evidence or assumption process.

Deliverable: versioned corpus, retrieval evaluation and source-grounded answers.

### Step 8 Connect language output to allocation

Feed validated extracted facts into the controller's observation model. Keep authorized structured fields authoritative and log conflicts. Compare known structured facts, deliberately noisy structured facts, and actual extracted facts to isolate the source of performance changes.

Make the allocator expose selected action, binding constraints, alternatives and the actual estimated benefit term. Generate explanations from this trace and source evidence. Check that action IDs, costs and factual claims match the trace. Explanations cannot edit the allocation.

Run matched cases with structured forms instead of free text. If a simple form achieves the same benefit with less uncertainty and cost, that is a valuable finding about whether an LLM is needed.

Deliverable: an end-to-end benchmark with traceable decisions.

### Step 9 Add QLoRA only for a measured weakness

Choose a narrow task such as extraction of transport barriers, attendance facts and uncertainty into a fixed schema. Do not train on invented stories asserting which intervention will prevent a particular child's dropout.

Compare the same base checkpoint in four settings: prompted base, base with retrieval, tuned model, tuned model with retrieval. Use retrieval where domain evidence is actually needed; purely factual note extraction may not benefit from it. Keep the test set, output schema, context allowance and evaluation procedure fixed.

Begin with rank 8 or 16, batch size 1, modest sequence length and short pilot runs; choose hyperparameters using validation data only. These are starting values to profile, not an established optimum. Report base revision, quantization method, adapter targets, training budget and seeds. Preserve unknown and abstention examples in training.

MLX-LM documents local LoRA and quantized-model adapter training on Apple silicon [22]. The Hugging Face PEFT quantization guide documents a common QLoRA workflow [23]. Do not assume a CUDA-oriented tutorial runs unchanged on an M2 or claim that every MLX quantization setup reproduces the original NF4 QLoRA configuration.

Deliverable: an ablation showing whether adaptation helps beyond prompting, including harmful error rates and downstream allocation effects.

### Step 10 Run the predeclared experiment suite

Use staged comparisons rather than an enormous full cross-product. First choose a working allocator with structured inputs. Then compare language configurations through that allocator. Finally evaluate the proposed uncertainty-aware method on stress tests.

Start with three resource levels, for example enough capacity for approximately 5%, 10% and 20% of eligible students per week. These are scenarios, not real school staffing estimates. Cross them with accurate, randomly missing and group-dependent missing-information conditions, then test unseen transition families and budget shocks.

Use a pilot of 10 seeds to estimate variance, followed by at least 30 independent held-out simulation seeds for the primary comparisons; increase only if intervals are too imprecise. Couple exogenous random streams by student and time across policies, so policy-dependent random-number consumption does not destroy pairing. Recompute observations from each policy's actual state trajectory.

Aggregate at the independent episode level; students within one coupled simulation are not independent experimental repetitions. Report paired differences, 95% confidence intervals and the full utility–equity frontier. Simulation intervals describe Monte Carlo uncertainty conditional on the model, not certainty about real schools. Evaluate uncertainty in response parameters separately.

Deliverable: reproducible tables, plots, failure cases and negative findings.

### Step 11 Add one extension if the core is complete

For the game-theory extension, give students preferences over tutor slots and staff preferences or priorities that are relevant to a support programme. Compare feasible welfare-maximizing matching with an appropriate deferred-acceptance baseline. Study blocking pairs, unmatched rates, access, preference satisfaction and benefits from strategic reports. Group constraints may invalidate standard stability or strategyproofness results; test or prove the actual properties of the modified mechanism.

Alternatively, add a synthetic peer graph and vary positive, zero and adverse spillover assumptions. Treat the graph and effects as hypothetical unless observed data supports them. Re-evaluate independent-arm baselines under coupling. Do not infer school friendships from similar demographic attributes and describe them as actual social ties.

Deliverable: one focused extension, not an additional unrelated architecture.

### Step 12 Prepare reproducibility and partner validation

Package versioned configuration files, data-access instructions, code, synthetic artefacts permitted for release, prompts, benchmark splits, source manifest and an experiment runner. Release a demo with fictional cases only. Do not redistribute source microdata or full evidence documents where terms do not permit it.

If a school or NGO engages, first validate the action catalogue, workflows, data definitions and false factual claims with practitioners. Next consider a shadow-mode study in which recommendations do not control support. A prospective impact study requires an appropriate comparison design, school-level clustering where needed, power analysis, research approvals and participant protections. No timetable or recruitment is assumed in the independent project.

Deliverable: research report, reproducible benchmark and a concrete partner-review protocol.

## Experimental measurements

| Layer | Primary measurements | Diagnostic measurements |
| --- | --- | --- |
| Prediction | PR-AUC, calibration and recall at fixed review capacity. | Brier score, time-specific errors, subgroup intervals and leakage checks. |
| Extraction | Per-field precision/recall/F1, unsupported assertion rate, correct unknown handling. | Negation, contradiction, timestamp errors, JSON validity and confidence calibration. |
| Retrieval and generation | Retrieval recall at k, supported-answer rate and correct source references. | Wrong-jurisdiction evidence, stale sources, abstention and adversarial document tests. |
| Allocation | Simulated retention relative to usual support; cost and completed-support utilization. | Assignment disagreement, estimated regret against an appropriate oracle, runtime and infeasibility. |
| Equity | Offers among eligible comparable-need students, group waiting times and worst-group outcomes. | Completed-support disparities, intersectional counts and staff workload distribution. |
| Robustness | Performance on unseen noise and transition settings. | Zero-effect interventions, delayed effects, shocks, skewed note quality and missing groups. |

Do not collapse all metrics into one score. Present costs and benefits of access constraints transparently. Report both a same-method true-parameter diagnostic and, only when actually available, an exact tiny-instance optimum. A true-parameter heuristic is not necessarily an upper bound.

For comparisons with an LLM-only or multi-agent LLM planner, supply the same case information, objective, resource constraints and bounded context. Score raw feasibility separately from outcomes after a common repair layer. Use equal or explicitly reported inference budgets. Repairing an invalid proposal does not show the original model satisfied the constraints.

## Software and hardware requirements

| Function | Suggested tools | Notes |
| --- | --- | --- |
| Data and baseline models | Python, NumPy, pandas or Polars, scikit-learn; optional boosted trees. | Start with transparent models and pin the tested versions. |
| Simulation | Plain vectorized Python; optional Gymnasium interface or Mesa. | Frameworks are optional; use one state implementation. |
| Optimization | OR-Tools or SciPy mixed-integer optimization. | Validate returned solutions and solver status; a time limit need not imply optimality. |
| Networks and matching | NetworkX; explicit matching and feasibility routines. | Only needed for the selected extension. |
| LLM | Candidate: Qwen3-4B-Instruct-2507 from the official Qwen Hugging Face repository [24]. | This is an available candidate, not a claim that it is the best current model. Benchmark before committing. |
| Embeddings | Candidate: all-MiniLM-L6-v2 for English [25], plus lexical retrieval. | Choose a separate evaluated multilingual model if language scope expands. |
| Local model runtime | MLX-LM [22]. | Verify the exact checkpoint and quantization format. |
| Cloud adaptation option | Transformers, PEFT and an appropriate supported quantization backend [23]. | Use only if local profiling fails or matching a paper's setup matters. |
| Schemas and experiment records | Pydantic or JSON Schema, YAML configs, Parquet/JSONL, Git and simple run logs. | Log prompts, model revisions, seeds and data hashes. |
| Demo | Streamlit or Gradio with fictional case data. | The dashboard is secondary to experiments. |

A MacBook M2 is a reasonable starting platform for hundreds or a few thousand simple agents, CPU optimization and small-model inference. The M2 name alone does not establish available unified memory. An 8 GB machine may require a smaller model or external inference; 16 GB offers more room, but fine-tuning feasibility still depends on context length, quantization, optimizer and other memory use. No 8B fine-tuning or 100,000-agent runtime guarantee is made.

Profile 50–100 inference cases and a short training pilot. Record time, peak memory and swap pressure. Cache extraction for unchanged observations, and run language inference only when new notes arrive. Do not call an LLM for every student every week. Build the environment and solver first so a model-compute bottleneck cannot block the core research.

## Suggested project structure

| Path | Purpose |
| --- | --- |
| `configs/` | Population, dynamics, interventions, policy and experiment settings. |
| `data/raw/` | Authorized source files, excluded from public release where required. |
| `data/processed/` | Audited features and immutable split manifests. |
| `data/notes/` | Synthetic notes, observable-fact labels and provenance. |
| `corpus/` | Evidence manifest, permitted source material and retrieval index. |
| `src/data/` | Loading, linkage, survey weighting and validation. |
| `src/environment/` | State, observations, uptake, transitions and resource accounting. |
| `src/policies/` | Baselines, optimizer and uncertainty-aware planner. |
| `src/language/` | Extraction, retrieval, explanation and adapter configuration. |
| `src/evaluation/` | Metrics, paired experiments and sensitivity analysis. |
| `tests/` | Constraint, leakage, transition and tiny-instance checks. |
| `results/` | Versioned run records and generated figures. |
| `docs/` | Protocol, assumptions register, data cards and report. |

A conceptual weekly loop is: observe available records; extract supported facts from new notes; retrieve relevant evidence; update estimated state; optimize assignments; independently validate feasibility; log and explain the actual decision; simulate uptake and transitions; reveal newly available outcomes. Learning uses only outcomes observed by that time.

## Timeline and decision gates

Estimate 16 weeks at roughly 15–20 focused hours per week for the core study, excluding unpredictable access delays or a field trial. Treat QLoRA or a game-theory extension as an additional two to four weeks if it cannot fit without weakening evaluation.

| Weeks | Work | Gate to continue |
| --- | --- | --- |
| 1–2 | Literature matrix, scope, dataset codebook audit and protocol. | One defensible population and one precise contribution. |
| 3–4 | Ingestion, splits, observational baselines and initial population model. | Valid labels, no identified leakage and documented access terms. |
| 5–6 | Simulator, usual-support dynamics and simple allocation policies. | Plausible sensitivity ranges and correct resource accounting. |
| 7–8 | Integer optimizer, access policy, uncertainty model and core ablations. | Demonstrable correctness; no claim of optimality without evidence. |
| 9–10 | Note benchmark, prompted extraction and downstream error analysis. | Independently checked labels and held-out styles. |
| 11–12 | RAG, evidence tests and optional small tuning pilot. | Each added component has a measured purpose. |
| 13–14 | Locked comparisons, repeated seeds, model misspecification and fairness analysis. | Results robustly characterized, including failures. |
| 15–16 | Report, reproducibility package and fictional-data demo. | Claims match the data and evaluation setting. |

Stop expanding the architecture if the benchmark or annotations are not trustworthy. If real target-domain data remains unavailable, complete the simulation study and narrow the title and conclusions accordingly. If notes add no value beyond a structured form, report that result rather than manufacturing a role for the LLM.

## First ten working days

1. Write the precise research question, target population and outcome definition.
2. Read the Guatemala evaluation and UNICEF India report; map the actual support workflow.
3. Read the fair-RMAB and DLM papers; fill the literature comparison table.
4. Inspect IHDS or one selected MICS codebook; choose one primary source.
5. Record access terms, available fields and missing requirements; freeze the data plan.
6. Build an initial population of 100 fictional students with explicit state and observation separation.
7. Add usual support, one extra action, uptake and resource accounting.
8. Compare random, waiting-time and risk-priority allocation on identical scenarios.
9. Create 30–50 hand-checked notes with negation, missing facts and conflicting dates.
10. Run a prompted small-model extractor and measure whether errors change allocation decisions.

This establishes whether the central research problem is observable before spending time on elaborate agent orchestration or fine-tuning.

## Claims and route to practical impact

The initial paper can support claims about algorithm performance under specified empirically grounded simulation assumptions, extraction quality on a documented corpus, and sensitivity to information quality. It cannot show that real dropout fell or that simulated children accurately represent individual children.

The strongest practical output is a workflow that shows practitioners what information is missing, produces feasible support schedules and makes allocation trade-offs reviewable. Human-reviewed action rules and an explicit correction route are part of the study design. When real child records are involved, minimize identifying text and follow the partner's approved access and research processes; public releases should contain only permitted data and fictional examples.

If a partner later supplies time-stamped intervention logs, revisit causal policy learning. Audit treatment selection, overlap, missing outcomes and interference before using off-policy evaluation. Do not report causal improvements from observational prediction accuracy. For clustered or network interventions, use an evaluation design that accounts for interactions between students and schools.

## Sources and access links

Sources were checked on 5 October 2026. Dates attached to preprints refer to their initial posting unless otherwise stated; inspect the current version and publication metadata when preparing a bibliography.

1. Haimovich, Vazquez and Adelman. *Scalable Early Warning Systems for School Dropout Prevention*. World Bank Working Paper 9685, 2021. https://documents1.worldbank.org/curated/en/983591622568486300/pdf/Scalable-Early-Warning-Systems-for-School-Dropout-Prevention-Evidence-from-a-4-000-School-Randomized-Controlled-Trial.pdf
2. UNICEF. *Building a predictive early warning system for school dropout in India*, 10 July 2026. https://www.unicef.org/digitaleducation/stories/building-predictive-early-warning-system-school-dropout-india
3. Herlihy et al. *Planning to Fairly Allocate*. https://arxiv.org/abs/2106.07677
4. Li and Varakantham. *Efficient Resource Allocation with Fairness Constraints in Restless Multi-Armed Bandits*. https://arxiv.org/abs/2206.03883
5. Biswas et al. *Fairness for Workers Who Pull the Arms*. https://arxiv.org/abs/2303.00799
6. Ou et al. *Networked Restless Multi-Armed Bandits for Mobile Interventions*. https://arxiv.org/abs/2201.12408 and https://www.ifaamas.org/AAMAS/aamas2022/Papers.html
7. Behari et al. *A Decision-Language Model for Dynamic Restless Multi-Armed Bandit Tasks in Public Health*. https://proceedings.neurips.cc/paper_files/paper/2024/hash/074f42212be2c8ee651db00f17965ec4-Abstract-Conference.html
8. Verma et al. *Balancing Act*. https://arxiv.org/abs/2408.12112
9. Parthasarathy et al. *Multilinguality in LLM-Designed Reward Functions for Restless Bandits*. https://arxiv.org/abs/2501.13120
10. Abdulkadiroğlu and Sönmez. *School Choice A Mechanism Design Approach*. https://www.aeaweb.org/articles?id=10.1257/000282803322157061
11. Jiang and Li. *Doubly Robust Off-policy Value Evaluation for Reinforcement Learning*. https://proceedings.mlr.press/v48/jiang16.pdf
12. Gui and Toubia. *The Challenge of Using LLMs to Simulate Human Behavior*. https://arxiv.org/abs/2312.15524
13. Lewis et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. https://proceedings.neurips.cc/paper/2020/file/6b493230205f780e1bc26945df7481e5-Paper.pdf
14. Dettmers et al. *QLoRA*. https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract-Conference.html
15. UCI Student Performance. https://archive.ics.uci.edu/dataset/320/student+performance
16. UCI Predict Students' Dropout and Academic Success. https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success
17. OULAD official landing page and documentation. https://research.stem.open.ac.uk/ouanalyse/dataset/ and https://research.stem.open.ac.uk/ouanalyse/open-dataset-more/
18. IHDS download and registration information. https://ihds.umd.edu/data/data-download and https://ihds.umd.edu/faq
19. UNICEF MICS-EAGLE and microdata background. https://data.unicef.org/resources/mics-education-analysis-for-global-learning-and-equity/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC6771654/
20. UDISE+ and data-sharing portal. https://udiseplus.gov.in/ and https://microdata.udiseplus.gov.in/
21. Education Endowment Foundation attendance evidence review, 2022. https://educationendowmentfoundation.org.uk/education-evidence/evidence-reviews/attendance-interventions-rapid-evidence-assessment
22. MLX-LM and adapter-training documentation. https://github.com/ml-explore/mlx-lm and https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md
23. Hugging Face PEFT quantization guide. https://huggingface.co/docs/peft/developer_guides/quantization
24. Qwen3-4B-Instruct-2507 official model repository. https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
25. all-MiniLM-L6-v2 model repository. https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

# Research assumptions

The Step6 [frozen protocol](research_evaluation_protocol.md) defines all numerical
assumptions. The source CSV is synthetic/semi-synthetic and its retained enrolled
prefix is fixed across worlds. Stochastic episode seeds are independent draws of
transitions and information mechanisms, not new schools. Four-state transition
matrices, programme causal effects, group information quality and uncertainty
mixtures are declared research assumptions, not fitted empirical quantities.

All support types use the same transition-effect matrix. Eligibility allows one
programme per student and uses authorized administrative enrollment; uncertainty
changes values and observed need strata, not operational ground truth. Notes
report observable signals, never future outcomes or treatment-effect parameters.
The exact controlled grammar restricts generalization and makes a simple phrase
lookup baseline unusually strong. No independent human annotation was performed.

Finite scenarios are a bounded sensitivity heuristic; they provide no coverage
guarantee for the true state, no optimal POMDP solution and no guaranteed retention
improvement. Risk calibration references the declared WAIT model, not observed
school-dropout outcomes. Fairness coverage is neither demographic nor outcome
parity. Confidence intervals quantify finite episode simulation uncertainty only.

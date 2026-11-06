"""Read-only evaluator scorecards for completed closed-loop episodes.

Truth is joined here after execution. Nothing in this module updates an
estimator, constructs a decision, or supplies evaluator truth to a policy.
WAIT risks are scored against the conditional reference-model probability,
never against an endpoint realized under treatment.
"""

from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
import math

import numpy as np

from ..school.fairness_audit import ATTRIBUTES, audit_access, audit_group, group_retention
from ..school.student_condition import STATES, StudentCondition


LOG_EPSILON = 1e-15


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def _truth(controller):
    return {row["month"]: dict(row["conditions"]) for row in controller.evaluator_truth}


def _validate_completed(controller):
    if not controller.environment.done or not controller.snapshots:
        raise ValueError("scorecards require a completed episode with decision snapshots")


def _information_records(controller):
    truth = _truth(controller)
    profiles = {student.student_id: student for student in controller.snapshots[0].students}
    risks = {(risk.as_of_month, risk.student_id): risk for risk in controller.risks}
    snapshots = [(snapshot.month, snapshot.students, snapshot.estimated_student_states)
                 for snapshot in controller.snapshots]
    terminal_cutoff = controller.environment.config.horizon + 1
    snapshots.append((terminal_cutoff, (), tuple(controller.estimates.values())))
    reference_wait = np.asarray(controller.environment.transition_assumptions[0], dtype=float)
    assumed_wait = np.asarray(controller.risk_estimator.wait, dtype=float)
    belief_rows, risk_rows = [], []
    for cutoff, students, estimates in snapshots:
        student_by_id = {student.student_id: student for student in students}
        estimate_by_id = {estimate.student_id: estimate for estimate in estimates}
        remaining = max(0, controller.environment.config.horizon - cutoff + 1)
        reference_endpoint = np.linalg.matrix_power(reference_wait, remaining)[:, -1]
        assumed_endpoint = np.linalg.matrix_power(assumed_wait, remaining)[:, -1]
        for sid, profile in sorted(profiles.items()):
            actual = StudentCondition(truth[cutoff - 1][sid])
            true_index = STATES.index(actual)
            oracle = controller.mode == "oracle"
            if oracle:
                # The oracle policy consumes current exact state, not the
                # controller's unused noisy filtering diagnostic.
                observed = student_by_id[sid].condition if students else actual
                probabilities = np.eye(4)[STATES.index(observed)]
                last_observation, missing, unresolved = cutoff - 1, False, 0
                source = "oracle_current_state_reference"
            else:
                estimate = estimate_by_id[sid]
                probabilities = np.asarray(estimate.condition_probabilities, dtype=float)
                uncertainty = dict(estimate.observation_uncertainty)
                last_observation = estimate.last_observation_month
                missing = bool(uncertainty.get("missing_current_signal", last_observation != cutoff - 1))
                unresolved = len(estimate.unresolved_observations)
                source = "estimated_decision_belief"
            predicted_index = int(np.argmax(probabilities))
            one_hot = np.eye(4)[true_index]
            groups = {attribute: audit_group(profile, attribute) for attribute in ATTRIBUTES}
            base = {"student_id": sid, "cutoff": cutoff, "truth_month": cutoff - 1,
                    "months_remaining": remaining, "terminal_diagnostic": cutoff == terminal_cutoff,
                    "enrolled": actual != StudentCondition.WITHDRAWN,
                    "prediction_source": source, **groups}
            belief_rows.append({
                **base, "true_condition": actual.value,
                "predicted_condition": STATES[predicted_index].value,
                **{f"p_{state.value}": float(probabilities[index])
                   for index, state in enumerate(STATES)},
                # Multiclass Brier is the SUM over all four class errors.
                "brier": float(np.sum((probabilities - one_hot) ** 2)),
                "nll": -math.log(max(LOG_EPSILON, float(probabilities[true_index]))),
                "accuracy": int(predicted_index == true_index),
                "entropy_nats": -sum(float(p) * math.log(float(p)) for p in probabilities if p > 0),
                "missing_current_signal": int(missing), "unresolved_count": unresolved,
                "last_observation_month": last_observation,
                "freshness_months": cutoff - 1 - last_observation if last_observation is not None else None,
                "no_observation_history": int(last_observation is None),
            })
            risk = risks[(cutoff, sid)]
            prediction = float(np.clip(probabilities @ assumed_endpoint, 0, 1)) if oracle else risk.probability
            reference = float(np.clip(reference_endpoint[true_index], 0, 1))
            clipped = min(1 - LOG_EPSILON, max(LOG_EPSILON, prediction))
            risk_rows.append({
                **base, "prediction": prediction, "reference_probability": reference,
                "reference_policy": risk.reference_policy, "target": risk.target,
                "scoring_convention": "expected_Bernoulli_proper_score_against_conditional_WAIT_probability",
                "expected_brier": reference * (1 - prediction) ** 2 + (1 - reference) * prediction ** 2,
                "expected_log_loss": -reference * math.log(clipped) - (1 - reference) * math.log(1 - clipped),
                "probability_squared_error": (prediction - reference) ** 2,
                "calibration_bin": min(9, int(prediction * 10)),
            })
    return belief_rows, risk_rows


def _grouped_information(records, *, belief):
    grouped = defaultdict(list)
    for record in records:
        grouped[(record["cutoff"], "all", "all")].append(record)
        for attribute in ATTRIBUTES:
            grouped[(record["cutoff"], attribute, record[attribute])].append(record)
    rows = []
    for (cutoff, attribute, group), members in sorted(grouped.items()):
        row = {"cutoff": cutoff, "attribute": attribute, "group": group,
               "count": len(members), "enrolled_count": sum(r["enrolled"] for r in members),
               "terminal_diagnostic": members[0]["terminal_diagnostic"],
               "prediction_source": members[0]["prediction_source"]}
        metrics = (("brier", "nll", "accuracy", "entropy_nats", "missing_current_signal",
                    "freshness_months", "no_observation_history", "unresolved_count") if belief else
                   ("expected_brier", "expected_log_loss", "probability_squared_error"))
        row.update({metric: _mean(r[metric] for r in members if r[metric] is not None)
                    for metric in metrics})
        if belief:
            row["confusion_matrix"] = json.dumps([
                [sum(r["true_condition"] == truth.value and r["predicted_condition"] == predicted.value
                     for r in members) for predicted in STATES] for truth in STATES])
            row["confusion_labels"] = json.dumps([state.value for state in STATES])
            row["brier_convention"] = "sum_over_four_classes"
            row["nll_clip_epsilon"] = LOG_EPSILON
        else:
            row["scoring_convention"] = members[0]["scoring_convention"]
            row["reference_probability"] = _mean(r["reference_probability"] for r in members)
            row["prediction"] = _mean(r["prediction"] for r in members)
        rows.append(row)
    return rows


def _access_rows(controller):
    env = controller.environment
    rows = []
    for window in controller.windows:
        audits = audit_access(window.cohorts, env.records, start_month=window.start,
                              end_month=window.end, minimum_access=window.target,
                              small_group_threshold=env.config.fairness_small_group_threshold)
        for cohort, row in zip(window.cohorts, audits):
            identity = json.dumps(sorted(cohort.student_ids), separators=(",", ":"))
            rows.append({**row, "student_ids": identity,
                         "membership_digest": sha256(identity.encode()).hexdigest(),
                         "normalized_shortfall_contribution": row["normalized_shortfall"] or 0.0,
                         "excluded_no_compatible_count": len(window.excluded_no_compatible_ids)})
    return rows


def _monthly_results(controller):
    env = controller.environment
    truth = _truth(controller)
    count = len(truth[0])
    rows = []
    cumulative_spending = 0.0
    previous_enrolled = count
    for month in sorted(truth):
        conditions = Counter(StudentCondition(condition).value for condition in truth[month].values())
        record = env.records[month - 1] if month else None
        assignments = record.allocation.assignments if record else ()
        spending = sum(assignment.cost_units for assignment in assignments)
        cumulative_spending += spending
        enrolled = count - conditions[StudentCondition.WITHDRAWN.value]
        rows.append({"month": month, **{state.value: conditions[state.value] for state in STATES},
                     "enrolled": enrolled, "newly_withdrawn": previous_enrolled - enrolled,
                     "retention_rate": enrolled / count if count else None,
                     "programmes": len(assignments),
                     "appointments": sum(assignment.sessions for assignment in assignments),
                     "spending": spending, "cumulative_spending": cumulative_spending,
                     "remaining_budget": record.remaining_budget if record else env.config.budget,
                     "mean_eligible_waiting_months": record.mean_eligible_waiting_months if record else 0.0})
        previous_enrolled = enrolled
    return rows


def _solver_rows(controller):
    result = []
    for record in controller.environment.records:
        allocation = record.allocation
        values = {key: value for key, value in asdict(allocation).items()
                  if key not in ("assignments", "tentative_assignments", "solver_settings",
                                 "projected_coverage")}
        # Full per-student scenario provenance stays in the compressed immutable
        # allocation trace. Keep tabular solver diagnostics compact and usable.
        settings = dict(allocation.solver_settings)
        values.update(solver_settings=json.dumps({key: value for key, value in settings.items()
            if key not in ("scenario_provenance", "scenario_names")}),
            scenario_count=len(settings.get("scenario_names", ())),
            robust_worst_case_benefit=settings.get("robust_worst_case_benefit"))
        # Baselines have no lexicographic solver and are not failed solves.
        incomplete = bool(allocation.solver_settings and not allocation.lexicographic_complete)
        result.append({"month": record.month, **values,
                       "solver_incomplete": incomplete,
                       "solver_fallback": "fallback" in allocation.status.lower()})
    return result


def _mentor_workload(controller):
    assignments = [assignment for record in controller.environment.records
                   for assignment in record.allocation.assignments]
    result = []
    for mentor_id, admissions, appointments in controller.environment.completed_resource_totals():
        delivered = [assignment for assignment in assignments if assignment.mentor_id == mentor_id]
        sessions = sum(assignment.sessions for assignment in delivered)
        result.append({"mentor_id": mentor_id, "programmes": len(delivered),
                       "appointments": sessions, "spending": sum(a.cost_units for a in delivered),
                       "admission_capacity": admissions, "appointment_capacity": appointments,
                       "admission_utilization": len(delivered) / admissions if admissions else 0.0,
                       "appointment_utilization": sessions / appointments if appointments else 0.0})
    return result


def score_episode(controller):
    """Return CSV-ready tables, plus individual records used for diagnostics."""
    _validate_completed(controller)
    beliefs, risks = _information_records(controller)
    access = _access_rows(controller)
    return {
        "belief_metrics": _grouped_information(beliefs, belief=True),
        "risk_metrics": _grouped_information(risks, belief=False),
        "belief_records": beliefs, "risk_records": risks,
        "group_access": access,
        "fairness_shortfalls": [dict(row) for row in access],
        "retention_by_group": [row for attribute in ATTRIBUTES for row in group_retention(
            controller.snapshots[0], controller.environment.records, attribute)],
        "monthly_results": _monthly_results(controller),
        "solver_diagnostics": _solver_rows(controller),
        "mentor_workload": _mentor_workload(controller),
    }


def episode_summary(controller, policy, mode, setting, seed):
    """Return one world-level row for descriptive and paired comparisons."""
    tables = score_episode(controller)
    env = controller.environment
    count = len(controller.snapshots[0].students)
    assignments = [assignment for record in env.records for assignment in record.allocation.assignments]
    resources = env.completed_resource_totals()
    admissions = sum(resource[1] for resource in resources)
    appointment_slots = sum(resource[2] for resource in resources)
    spending = sum(assignment.cost_units for assignment in assignments)
    access = tables["group_access"]
    comparable_gaps = [row["access_disparity"] for row in access if row["access_disparity"] is not None]
    waiting_gaps = [row["mean_waiting_disparity"] for row in access if row["mean_waiting_disparity"] is not None]
    rates = [row["access_rate"] for row in access if row["access_rate"] is not None]
    diagnostics = tables["solver_diagnostics"]
    # Terminal evidence is a useful diagnostic but is not another decision.
    beliefs = [row for row in tables["belief_records"] if not row["terminal_diagnostic"]]
    risks = [row for row in tables["risk_records"] if not row["terminal_diagnostic"]]
    return {
        "policy": policy, "mode": mode, "setting": setting, "seed": seed,
        "students": count, "months": env.config.horizon,
        "terminal_enrolled": env.terminal_reward(),
        "retention_rate": env.terminal_reward() / count if count else None,
        "enrolled_student_months": sum(row["enrolled"] for row in tables["monthly_results"] if row["month"]),
        "spending": spending, "budget_utilization": spending / env.config.budget if env.config.budget else 0.0,
        "programmes": len(assignments), "appointments": sum(a.sessions for a in assignments),
        "normalized_shortfall": sum(row["normalized_shortfall_contribution"] for row in access),
        "access_gap": max(comparable_gaps) if comparable_gaps else None,
        "worst_group_access": min(rates) if rates else None,
        "waiting_disparity": max(waiting_gaps) if waiting_gaps else None,
        "mean_waiting_months": _mean(wait for _, wait in env.records[-1].waiting_months),
        "mean_recipient_waiting_months": _mean(wait for record in env.records for wait in record.recipient_waiting_months),
        "mentor_admission_utilization": len(assignments) / admissions if admissions else 0.0,
        "appointment_slot_utilization": sum(a.sessions for a in assignments) / appointment_slots if appointment_slots else 0.0,
        "solver_runtime_seconds": sum(row["runtime_seconds"] for row in diagnostics),
        "max_monthly_solver_runtime_seconds": max((row["runtime_seconds"] for row in diagnostics), default=0.0),
        "solver_incomplete_count": sum(row["solver_incomplete"] for row in diagnostics),
        "solver_fallback_count": sum(row["solver_fallback"] for row in diagnostics),
        "belief_brier": _mean(row["brier"] for row in beliefs),
        "belief_nll": _mean(row["nll"] for row in beliefs),
        "risk_expected_brier": _mean(row["expected_brier"] for row in risks),
        "risk_expected_log_loss": _mean(row["expected_log_loss"] for row in risks),
        "risk_probability_mse": _mean(row["probability_squared_error"] for row in risks),
    }

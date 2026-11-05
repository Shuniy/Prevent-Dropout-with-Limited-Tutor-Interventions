"""Episode-level simulation metrics and paired, world-level confidence intervals."""

from collections import Counter
from dataclasses import asdict

import numpy as np
from scipy.stats import t as student_t

from .student_condition import STATES, StudentCondition
from .fairness_audit import audit_access


def paired_difference(values, reference):
    if len(values) != len(reference) or not values:
        raise ValueError("paired comparisons require equal nonempty episode lists")
    differences = np.asarray(values, dtype=float) - np.asarray(reference, dtype=float)
    mean = float(np.mean(differences))
    # Paired 95% CI = mean(d) +/- t_(.975,n-1) * sd(d) / sqrt(n).
    margin = (
        (
            float(student_t.ppf(0.975, len(differences) - 1))
            * float(np.std(differences, ddof=1))
            / np.sqrt(len(differences))
        )
        if len(differences) > 1
        else None
    )
    return {
        "mean": mean,
        "ci95_low": mean - margin if margin is not None else None,
        "ci95_high": mean + margin if margin is not None else None,
        "paired_episodes": len(differences),
    }


def monthly_summaries(env, initial_state):
    """Summarize initialization and recorded months using realized resources."""
    count = len(initial_state.students)
    summaries = []
    supported = set()
    previous_withdrawn = 0
    cumulative_spending = 0.0
    initial_counts = Counter(student.condition.value for student in initial_state.students)
    initial_capacities = tuple(
        (mentor.mentor_id, mentor.admissions, mentor.appointments)
        for mentor in initial_state.mentors
    )
    # Month zero reports available first-month capacities with no usage.
    initial_waits = tuple((student.student_id, student.waiting_months) for student in initial_state.students)
    months = [(0, initial_counts, (), initial_state.remaining_budget, initial_capacities,
               initial_waits, ())]
    months.extend(
        (
            record.month,
            Counter(condition.value for _, condition in record.conditions),
            record.allocation.assignments,
            record.remaining_budget,
            record.mentor_capacities,
            record.waiting_months,
            record.recipient_waiting_months,
        )
        for record in env.records
    )
    for month, counts, assignments, remaining, capacities, waits, recipient_waits in months:
        supported.update(item.student_id for item in assignments)
        spending = sum(item.cost_units for item in assignments)
        cumulative_spending += spending
        withdrawn = counts[StudentCondition.WITHDRAWN.value]
        if month == 0:
            enrolled_ids = {
                student.student_id for student in initial_state.students if student.enrolled
            }
        else:
            enrolled_ids = {
                student_id
                for student_id, condition in env.records[month - 1].conditions
                if condition != StudentCondition.WITHDRAWN
            }
        mentor_counts = Counter(item.mentor_id for item in assignments)
        eligible_waits = [wait for student_id, wait in waits if student_id in enrolled_ids - supported]
        summaries.append(
            {
                "month": month,
                **{condition.value: counts[condition.value] for condition in STATES},
                "newly_withdrawn": withdrawn - previous_withdrawn,
                "enrolled": count - withdrawn,
                "retention_rate": (count - withdrawn) / count if count else None,
                "dropout_rate": withdrawn / count if count else None,
                "programmes_started": len(assignments),
                "appointments_delivered": 5 * len(assignments),
                "spending": spending,
                "cumulative_spending": cumulative_spending,
                "remaining_budget": remaining,
                "eligible_students": len(enrolled_ids - supported),
                "mean_eligible_waiting_months": (
                    float(np.mean(eligible_waits)) if eligible_waits else 0.0
                ),
                "max_eligible_waiting_months": max(eligible_waits, default=0),
                "eligible_waiting_distribution": dict(sorted(Counter(eligible_waits).items())),
                "mean_recipient_waiting_months": (
                    float(np.mean(recipient_waits)) if recipient_waits else None
                ),
                "mentor_utilization": [
                    {
                        "mentor_id": mentor_id,
                        "programmes": mentor_counts[mentor_id],
                        "appointments": 5 * mentor_counts[mentor_id],
                        "admission_capacity": admissions,
                        "appointment_capacity": appointments,
                        "admission_utilization": (
                            mentor_counts[mentor_id] / admissions if admissions else 0.0
                        ),
                        "appointment_utilization": (
                            5 * mentor_counts[mentor_id] / appointments if appointments else 0.0
                        ),
                    }
                    for mentor_id, admissions, appointments in capacities
                ],
            }
        )
        previous_withdrawn = withdrawn
    return summaries


def episode_metrics(env, initial_state, cohorts):
    final = env.observe()
    assignments = [item for record in env.records for item in record.allocation.assignments]
    monthly = []
    withdrawal = {}
    for record in env.records:
        counts = Counter(condition.value for _, condition in record.conditions)
        monthly.append(
            {
                "month": record.month,
                **{condition.value: counts[condition.value] for condition in STATES},
            }
        )
        for student_id, condition in record.conditions:
            if condition == StudentCondition.WITHDRAWN:
                withdrawal.setdefault(student_id, record.month)
    waits = [student.waiting_months for student in final.students]
    recipient_waits = [wait for record in env.records for wait in record.recipient_waiting_months]
    eligible_waits = [student.waiting_months for student in final.students if student.eligible]
    workload = []
    for mentor_id, admissions_capacity, appointment_capacity in env.completed_resource_totals():
        delivered = sum(item.mentor_id == mentor_id for item in assignments)
        workload.append(
            {
                "mentor_id": mentor_id,
                "programmes": delivered,
                "appointments": 5 * delivered,
                "admission_utilization": (
                    delivered / admissions_capacity if admissions_capacity else 0
                ),
                "appointment_utilization": (
                    5 * delivered / appointment_capacity if appointment_capacity else 0
                ),
            }
        )
    count = len(initial_state.students)
    spending = sum(item.cost_units for item in assignments)
    resource_totals = env.completed_resource_totals()
    admissions_capacity = sum(item[1] for item in resource_totals)
    appointment_capacity = sum(item[2] for item in resource_totals)
    return {
        "terminal_enrolled": env.terminal_reward(),
        "retention_rate": env.terminal_reward() / count if count else None,
        "enrolled_student_months": sum(count - month["withdrawn"] for month in monthly),
        "monthly_conditions": monthly,
        "monthly_summaries": monthly_summaries(env, initial_state),
        "withdrawal_months": dict(sorted(Counter(withdrawal.values()).items())),
        "spending": spending,
        "budget_utilization": spending / env.config.budget if env.config.budget else 0,
        "programmes": len(assignments),
        "appointments": 5 * len(assignments),
        "unique_students_supported": len({item.student_id for item in assignments}),
        "cumulative_withdrawals": count - env.terminal_reward(),
        "remaining_budget": final.remaining_budget,
        "cost_per_supported_student": spending / len(assignments) if assignments else None,
        "waiting_months": waits,
        "recipient_waiting_months": recipient_waits,
        "mean_waiting_months": float(np.mean(waits)) if waits else 0,
        "waiting_p50": float(np.quantile(waits, 0.5)) if waits else 0,
        "waiting_p90": float(np.quantile(waits, 0.9)) if waits else 0,
        "mean_eligible_waiting_months": float(np.mean(eligible_waits)) if eligible_waits else 0.0,
        "max_eligible_waiting_months": max(eligible_waits, default=0),
        "eligible_waiting_distribution": dict(sorted(Counter(eligible_waits).items())),
        "max_waiting_months": max(waits, default=0),
        "mean_recipient_waiting_months": float(np.mean(recipient_waits)) if recipient_waits else None,
        "mentor_admission_utilization": (
            len(assignments) / admissions_capacity if admissions_capacity else 0.0
        ),
        "appointment_slot_utilization": (
            5 * len(assignments) / appointment_capacity if appointment_capacity else 0.0
        ),
        "mentor_workload": workload,
        "group_access": audit_access(cohorts, env.records),
        "solver_runtime_seconds": sum(record.allocation.runtime_seconds for record in env.records),
        "max_monthly_solver_runtime_seconds": max(
            (record.allocation.runtime_seconds for record in env.records), default=0.0),
        "estimated_total_benefit": sum(record.allocation.objective for record in env.records),
        "feasibility_validation_failures": sum(record.allocation.validation_failures
                                                for record in env.records),
        "solver_diagnostics": [
            {key: value for key, value in asdict(record.allocation).items()
             if key != "assignments"}
            for record in env.records
        ],
        "solver_statuses": dict(Counter(record.allocation.status for record in env.records)),
        "solver_failures": sum("fallback" in record.allocation.status for record in env.records),
        "solver_optimality_gaps": [
            record.allocation.optimality_gap
            for record in env.records
            if record.allocation.optimality_gap is not None
        ],
        "solver_objective_bounds": [
            record.allocation.objective_bound
            for record in env.records
            if record.allocation.objective_bound is not None
        ],
    }

"""Structured source attributes only; the disadvantage proxy is not verified income."""

from collections import defaultdict

from .access_cohort import AccessCohort
from .student_condition import StudentCondition


def freeze_cohorts(state):
    grouped = defaultdict(list)
    for student in state.students:
        if not student.eligible:
            continue
        condition = student.condition.value if student.condition is not None else "unknown"
        for attribute, group in (
            ("disadvantage_proxy", str(student.disadvantage_proxy)),
            ("sex_source", student.sex_source or "unknown"),
        ):
            key = (attribute, group, condition, student.support_type)
            grouped[key].append(student.student_id)
    return tuple(AccessCohort(*key, tuple(ids)) for key, ids in sorted(grouped.items()))


def coverage_shortfall(cohorts, offered_ids, minimum_access):
    # xi_g = max(0, q * |E_g| - distinct offers_g).
    # Sum xi_g / |E_g| gives equal weight to each nonempty comparable-need group.
    return sum(
        max(
            0.0,
            minimum_access * len(cohort.student_ids)
            - len(set(cohort.student_ids) & set(offered_ids)),
        )
        / len(cohort.student_ids)
        for cohort in cohorts
    )


def audit_access(cohorts, records, *, start_month=1, end_month=None, minimum_access=0.0):
    if not records:
        return []
    end_month = records[-1].month if end_month is None else end_month
    assignments = {
        item.student_id: item
        for record in records
        if start_month <= record.month <= end_month
        for item in record.allocation.assignments
    }
    final_conditions = dict(records[-1].conditions)
    withdrawal_month = {}
    for record in records:
        for student_id, condition in record.conditions:
            if condition == StudentCondition.WITHDRAWN:
                withdrawal_month.setdefault(student_id, record.month)
    audits = []
    for cohort in cohorts:
        ids = set(cohort.student_ids)
        offers = ids & assignments.keys()
        waiting = []
        for student_id in ids:
            if student_id in offers:
                waiting.append(assignments[student_id].month - start_month)
            else:
                # Unserved waits are censored by window end or simulated withdrawal.
                waiting.append(
                    max(
                        0,
                        min(end_month, withdrawal_month.get(student_id, end_month))
                        - start_month
                        + 1,
                    )
                )
        retained = sum(
            final_conditions[student_id] != StudentCondition.WITHDRAWN for student_id in ids
        )
        shortfall = max(0.0, minimum_access * len(ids) - len(offers))
        audits.append(
            {
                "attribute": cohort.attribute,
                "group": cohort.group,
                "condition_at_start": cohort.condition_at_start,
                "support_type": cohort.support_type,
                "window_start": start_month,
                "window_end": end_month,
                "eligible_count": len(ids),
                "unique_offers": len(offers),
                "access_rate": len(offers) / len(ids),
                "completed_programme_rate": len(offers) / len(ids),
                "mean_waiting_months": sum(waiting) / len(waiting),
                "terminal_retention_rate": retained / len(ids),
                "coverage_shortfall": shortfall,
                "normalized_shortfall": shortfall / len(ids),
            }
        )
    return audits

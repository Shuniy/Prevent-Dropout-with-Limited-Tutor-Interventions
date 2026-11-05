"""Independent admission audits of authorized, frozen comparable-need cohorts."""

from collections import defaultdict
from decimal import Decimal, ROUND_CEILING

from .access_cohort import AccessCohort
from .student_condition import StudentCondition


ATTRIBUTES = ("disadvantage_proxy", "sex_source")


def audit_group(student, attribute):
    if attribute == "disadvantage_proxy":
        value = student.disadvantage_proxy
        return str(value) if type(value) is bool else "unknown"
    if attribute == "sex_source":
        value = student.sex_source
        return value if value in ("F", "M") else "unknown"
    raise ValueError("select one authorized audit attribute")


def required_access(target, size):
    """Decimal arithmetic avoids ceil(0.14 * 100) accidentally becoming 15."""
    return int((Decimal(str(target)) * size).to_integral_value(rounding=ROUND_CEILING))


def compatible_ids(state, end_month=None):
    """Operational compatibility ignores shared affordability, not mentor capacity.

    Include any announced compatible slot in this window. Absent a calendar,
    only current resources are known; no future capacity is invented.
    """
    end_month = state.month if end_month is None else end_month
    resources = [state.mentors]
    resources.extend(mentors for month, mentors in state.known_mentor_schedule
                     if state.month < month <= end_month)
    return {student.student_id for student in state.students if student.eligible
            if any(student.student_id in mentor.compatible_student_ids
                   and student.support_type in mentor.support_types
                   and mentor.admissions > 0 and mentor.appointments >= 5
                   for mentors in resources for mentor in mentors)}


def freeze_cohorts(state, grouping_attribute="disadvantage_proxy", *, end_month=None):
    """One audit axis, three broad oracle-observed conditions; include empty cells."""
    if grouping_attribute not in ATTRIBUTES:
        raise ValueError("select one authorized audit attribute")
    estimated = state.observation_mode == "estimated_state_v1"
    if state.observation_mode != "fully_observed_benchmark" and not estimated:
        raise ValueError("frozen_condition requires the labelled oracle benchmark interface")
    groups = ("False", "True", "unknown") if grouping_attribute == "disadvantage_proxy" else ("F", "M", "unknown")
    strata = [condition.value for condition in tuple(StudentCondition)[:3]]
    if estimated:
        strata.append("uncertain")
    grouped = {(group, condition): [] for group in groups for condition in strata}
    compatible = compatible_ids(state, end_month)
    for student in state.students:
        if student.student_id not in compatible:
            continue
        if estimated:
            # Uncertain enrolled cases retain a denominator, never zero need.
            belief = student.condition_probabilities
            label = (student.condition.value if belief and max(belief) >= .6
                     and student.condition not in (None, StudentCondition.WITHDRAWN) else "uncertain")
            grouped[(audit_group(student, grouping_attribute), label)].append(student.student_id)
            continue
        if student.condition is None or student.condition == StudentCondition.WITHDRAWN:
            raise ValueError("eligible fairness cohort requires an observed enrolled condition")
        grouped[(audit_group(student, grouping_attribute), student.condition.value)].append(student.student_id)
    return tuple(AccessCohort(grouping_attribute, group, condition, "all_compatible_support",
                              tuple(sorted(ids)))
                 for (group, condition), ids in sorted(grouped.items()))


def coverage_shortfall(cohorts, admitted_ids, minimum_access):
    admitted_ids = set(admitted_ids)
    return sum(max(0, required_access(minimum_access, len(cohort.student_ids))
                   - len(set(cohort.student_ids) & admitted_ids)) / len(cohort.student_ids)
               for cohort in cohorts if cohort.student_ids)


def audit_access(cohorts, records, *, start_month=1, end_month=None, minimum_access=0.0,
                 small_group_threshold=30):
    """Use actual admissions only. Retention denominator = this frozen eligible cell.

    Waiting is measured from window start; unserved waits are censored at the
    withdrawal transition or window end. Terminal retention uses the last record
    supplied (the episode's last record in the experiment runner).
    """
    if not records:
        return []
    end_month = records[-1].month if end_month is None else end_month
    assignments = {item.student_id: item for record in records
                   if start_month <= record.month <= end_month
                   for item in record.allocation.assignments}
    final_conditions = dict(records[-1].conditions)
    withdrawal_month = {}
    for record in records:
        for student_id, condition in record.conditions:
            if condition == StudentCondition.WITHDRAWN:
                withdrawal_month.setdefault(student_id, record.month)
    audits = []
    for cohort in cohorts:
        ids = set(cohort.student_ids)
        admissions = ids & assignments.keys()
        waiting = [assignments[sid].month - start_month if sid in admissions else
                   max(0, min(end_month, withdrawal_month.get(sid, end_month + 1) - 1)
                       - start_month + 1) for sid in ids]
        size = len(ids)
        target = required_access(minimum_access, size)
        shortfall = max(0, target - len(admissions))
        retained = sum(final_conditions[sid] != StudentCondition.WITHDRAWN for sid in ids)
        audits.append({
            "attribute": cohort.attribute, "group": cohort.group,
            "condition_at_start": cohort.condition_at_start, "support_type": cohort.support_type,
            "window_start": start_month, "window_end": end_month,
            "eligible_count": size, "unique_admissions": len(admissions),
            "unique_offers": len(admissions),  # legacy export alias; an admission, not an offer/acceptance
            "target_coverage": minimum_access, "required_students": target,
            "access_rate": len(admissions) / size if size else None,
            "completed_programme_rate": len(admissions) / size if size else None,
            "mean_waiting_months": sum(waiting) / size if size else None,
            "max_waiting_months": max(waiting) if waiting else None,
            "terminal_retention_rate": retained / size if size else None,
            "coverage_shortfall": shortfall,
            "normalized_shortfall": shortfall / size if size else None,
            "small_group": 0 < size < small_group_threshold,
            "unknown_group": cohort.group == "unknown",
        })
    for row in audits:
        for metric, name in (("access_rate", "access_disparity"),
                             ("mean_waiting_months", "mean_waiting_disparity"),
                             ("max_waiting_months", "max_waiting_disparity")):
            valid = [other[metric] for other in audits
                     if other["condition_at_start"] == row["condition_at_start"]
                     and other["attribute"] == row["attribute"] and other[metric] is not None]
            row[name] = max(valid) - min(valid) if len(valid) >= 2 else None
    return audits


def group_retention(initial_state, records, attribute):
    """All initially enrolled students, including those with no compatible mentor."""
    final = dict(records[-1].conditions)
    groups = defaultdict(list)
    for student in initial_state.students:
        if student.enrolled:
            groups[audit_group(student, attribute)].append(student.student_id)
    return [{"attribute": attribute, "group": group, "initial_enrolled_count": len(ids),
             "terminal_retention_rate": sum(final[sid] != StudentCondition.WITHDRAWN
                                             for sid in ids) / len(ids)}
            for group, ids in sorted(groups.items())]

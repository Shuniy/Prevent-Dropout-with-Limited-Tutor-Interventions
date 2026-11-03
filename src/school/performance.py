"""Evaluate runtime needs without inventing numeric intervention effects."""

from dataclasses import asdict, replace
from .needs import calculate_needs
from .performance_snapshot import PerformanceSnapshot
from .student_performance import StudentPerformance


def initial_performance(student) -> StudentPerformance:
    return StudentPerformance(
        student.anchor_grade1_0_20, student.math_grade1_0_20,
        getattr(student, "initial_attendance_fraction_assumed", None),
        getattr(student, "initial_engagement_assumed", None),
        getattr(student, "enrolled_initial_assumed", None),
        getattr(student, "support_sessions_completed", 0),
    )


def current_needs(student, performance: StudentPerformance) -> list[dict]:
    # A transient copy lets source and runtime evaluations share exactly one rule set.
    inputs = replace(student, anchor_grade1_0_20=performance.anchor_grade,
                     math_grade1_0_20=performance.math_grade)
    inputs.initial_attendance_fraction_assumed = performance.attendance_fraction
    inputs.initial_engagement_assumed = performance.engagement
    inputs.enrolled_initial_assumed = performance.enrolled
    return calculate_needs(inputs)


def snapshot(student, performance: StudentPerformance) -> PerformanceSnapshot:
    primary = current_needs(student, performance)[0]
    return PerformanceSnapshot(**asdict(performance), need_score=primary["severity"],
                               primary_support_type=primary["support_type"])


def apply_outcomes(performance: StudentPerformance, result) -> None:
    performance.support_sessions_completed += result.sessions_completed
    names = ("attendance_improved", "primary_barrier_resolved", "intervention_helpful")
    if result.analysis_status == "completed":
        for name in names:
            value = getattr(result, name)
            if value not in {"unknown", "conflicting"}:
                setattr(performance, name, value)
        performance.evaluation_reason = "reported_outcomes_only; numeric_measures_unchanged"
    else:
        performance.evaluation_reason = f"analysis_{result.analysis_status}; outcomes_unchanged"
    for status in ("unknown", "conflicting"):
        unchanged = [name for name in names if getattr(result, name) == status]
        if unchanged:
            performance.evaluation_reason += f"; {status}_outcomes_unchanged:" + ",".join(unchanged)

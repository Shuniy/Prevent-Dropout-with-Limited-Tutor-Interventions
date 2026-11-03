"""School exports contain public results and school evaluations only."""

from dataclasses import asdict
import json
from pathlib import Path


def write_report(path: Path, report: dict) -> None:
    contents = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(contents, encoding="utf-8")
    temporary.replace(path)


def public_result(result) -> dict:
    # Deliberate field allowlist; adding private fields elsewhere cannot export them.
    return {name: getattr(result, name) for name in (
        "run_id", "programme_id", "month", "student_id", "mentor_id", "support_type",
        "planned_sessions", "sessions_completed", "status", "analysis_status",
        "attendance_improved", "primary_barrier_resolved", "intervention_helpful",
    )}


def monthly_report(school, month: int) -> dict:
    return {
        "run_id": school.run_id, "month": month,
        "spent_budget": school.spent_budget, "remaining_budget": school.remaining_budget,
        "assignments": [asdict(a) for a in school.assignment_history if a.month == month],
        "results": [public_result(r) for r in school.intervention_results.values() if r.month == month],
        "evaluations": [asdict(e) for e in school.monthly_evaluations[month]],
    }


def final_report(school, output_dir: Path) -> dict:
    results = {r.student_id: r for r in school.intervention_results.values()}
    students = {}
    for number, student in enumerate(school.students, 1):
        sid = student.student_id
        result = results.get(sid)
        report = {
            "student_id": sid,
            "result": public_result(result) if result else None,
            "unassigned_reason": None if result else "no_feasible_mentor_capacity_or_budget",
            "evaluations": [asdict(e) for evaluations in school.monthly_evaluations.values()
                            for e in evaluations if e.student_id == sid],
        }
        students[sid] = report
        write_report(output_dir / f"student_{number:05d}" / "final_report.json", report)
    return {
        "run_id": school.run_id, "months": school.num_months,
        "status": "failed" if any(r.analysis_status == "failed" for r in results.values()) else "finished",
        "output_dir": str(output_dir.resolve()),
        "spent_budget": school.spent_budget, "remaining_budget": school.remaining_budget,
        "assignments": [asdict(a) for a in school.assignment_history], "students": students,
    }

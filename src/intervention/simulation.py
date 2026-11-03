"""Replay feature-matched synthetic programmes through the existing local RAG.

Each student has one mentor and one programme for the entire run. A programme
fits inside an allocation month; its dose defaults to five appointments in total.
Recorded source sessions define participation, without inventing missing meetings
or interpreting the end of a transcript series as school dropout.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import random
from typing import TYPE_CHECKING, Callable

from .intervention import Intervention, write_report
from .rag import HISTORIES, InterventionRAG, OllamaClient, SessionIndex, load_sessions

try:
    from ..models.student import Student, StudentInterventionProfile
except ImportError:  # Direct ``python src/main.py`` entry point.
    from models.student import Student, StudentInterventionProfile

if TYPE_CHECKING:
    from ..models.school import School


RESULTS = Path(__file__).resolve().parents[2] / "results" / "intervention_simulation"
PROBLEM_RULE_VERSION = "feature_rules_v1"


def create_profile(student: Student, planned_sessions: int = 5) -> StudentInterventionProfile:
    """Calculate transparent scenario concerns from available dataset features.

    Severity is an assumed support priority in [0, 1], never a dropout probability.
    Unsupported concerns (e.g. hunger, language needs, diagnoses) are not inferred.
    Missing attendance, engagement and financial need remain unknown.
    """
    if planned_sessions < 1:
        raise ValueError("planned_sessions must be positive")
    attendance = getattr(student, "initial_attendance_fraction_assumed", None)
    engagement = getattr(student, "initial_engagement_assumed", None)
    for name, value in (("attendance", attendance), ("engagement", engagement)):
        if value is not None and not 0 <= value <= 1:
            raise ValueError(f"initial {name} must be between 0 and 1")
    problems = []

    def add(problem: str, support_type: str, severity: float, basis: str) -> None:
        problems.append({"problem": problem, "support_type": support_type,
                         "severity": round(severity, 4), "basis": basis,
                         "provenance": "feature_based_simulation_assumption"})

    if getattr(student, "enrolled_initial_assumed", None) is False:
        add("return_to_learning", "reentry_support", 1.0, "enrolled_initial_assumed is false")
    if student.learning_gap > 0 or student.past_failures_count > 0:
        add("learning_gap", "tutoring", max(student.learning_gap, min(1, student.past_failures_count / 4)),
            "learning_gap > 0 or past_failures_count > 0")
    if attendance is not None and attendance < 0.85:
        add("attendance_routine", "attendance_planning", 1 - attendance,
            "initial_attendance_fraction_assumed < 0.85")
    if student.no_home_internet:
        add("digital_access", "device_access", 0.5, "internet_at_home is false; device ownership is unknown")
    if student.travel_over_30min:
        add("long_journey", "transport_assessment", (student.travel_time_category - 2) / 2,
            "travel_time_category >= 3; transport eligibility is unknown")
    if student.study_time_category == 1:
        add("study_routine", "homework_support", 0.25, "study_time_category == 1")
    if student.family_relationship_rating <= 2:
        add("family_communication", "family_liaison", (3 - student.family_relationship_rating) / 3,
            "family_relationship_rating <= 2")
    if student.health_self_rating <= 2:
        add("wellbeing_checkin", "wellbeing_checkin", (3 - student.health_self_rating) / 3,
            "health_self_rating <= 2; no diagnosis inferred")
    if engagement is not None and engagement < 0.6:
        add("participation_opportunities", "peer_support", 1 - engagement,
            "initial_engagement_assumed < 0.6; peer isolation is not established")
    if getattr(student, "financial_need_verified", None) is True:
        add("verified_financial_need", "family_finances", 0.75, "financial_need_verified is true")
    if not problems:
        add("routine_learning_checkin", "tutoring", 0.0, "no scenario concern threshold met")
    problems.sort(key=lambda problem: (-problem["severity"], problem["problem"]))
    scores = {
        "learning_gap_0_1": student.learning_gap,
        "attendance_fraction_assumed": attendance,
        "engagement_assumed": engagement,
        "support_priority_0_1": problems[0]["severity"],
        "school_dropout_risk": None,
    }
    return StudentInterventionProfile(student.student_id, asdict(student), scores,
                                      problems, planned_sessions)


def run_interventions(
    school: "School", *, root: Path = HISTORIES, output_dir: Path | None = None,
    client: OllamaClient | None = None, progress: Callable[[str], None] | None = None,
) -> dict:
    """Allocate once, replay RAG, and save every session and terminal JSON report.

    Admission reserves the complete dose against monthly mentor capacity and the
    episode budget. Only recorded appointments are charged; unused reservations
    are released after each programme. No student starts a second programme.
    Extraction failures retain validated session reports and mark the run failed.
    A fresh output directory prevents stale sessions from an older run surviving.
    """
    root = Path(root).resolve()
    output_dir = Path(output_dir) if output_dir is not None else RESULTS / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {output_dir}")
    sessions = load_sessions(root)
    index = SessionIndex()
    try:
        index.build(sessions)
        catalogue: dict[str, list[str]] = {}
        for history_id, history in index.sessions.items():
            if [session.number for session in history] != list(range(1, len(history) + 1)):
                raise ValueError(f"History must have consecutive sessions starting at 1: {history_id}")
            folder = history_id.split("/", 1)[0]
            support_type = folder.split("_", 1)[1] if folder[:2].isdigit() else folder
            catalogue.setdefault(support_type, []).append(history_id)
        profiles = {student.student_id: create_profile(student, school.sessions_per_student)
                    for student in school.students}
        school.reset()
        # Existing caller-supplied caseloads keep their mentor. Re-enter them via
        # the same skill, capacity and budget checks as every other programme.
        preferred = dict(school.assignments)
        for mentor in school.mentors:
            for student_id in list(mentor.current_student_ids):
                if student_id in preferred:
                    mentor.release_student(student_id)
        school.assignments.clear()
        school.intervention_profiles = profiles
        output_dir.mkdir(parents=True, exist_ok=True)
        destinations = {student_id: output_dir / f"student_{number:05d}"
                        for number, student_id in enumerate(profiles, 1)}
        requested = {sid: profile.problems[0]["support_type"] for sid, profile in profiles.items()}
        unavailable = {sid for sid, support in requested.items() if support not in catalogue}
        processed = set(unavailable)
        rng = random.Random(school.seed)
        rag = InterventionRAG(index, client)
        reports = {}
        students_by_id = {student.student_id: student for student in school.students}
        mentors_by_id = {mentor.mentor_id: mentor for mentor in school.mentors}

        def notify(message: str) -> None:
            if progress is not None:
                progress(message)

        for month in range(1, school.num_months + 1):
            if len(processed) == len(profiles):
                break
            assignments = school.step(month, student_support_types=requested,
                                      excluded_student_ids=processed,
                                      preferred_mentor_ids=preferred)
            for assignment in assignments:
                sid = assignment.student_id
                profile = profiles[sid]
                profile.mentor_id = assignment.mentor_id
                profile.history_id = rng.choice(catalogue[assignment.support_type])
                intervention = Intervention(
                    rag, profile, destinations[sid], allocation_month=month, progress=notify,
                )
                report = intervention.start_intervention(
                    students_by_id[sid], mentors_by_id[assignment.mentor_id],
                )
                recorded = school.record_intervention_attendance(
                    assignment, profile.sessions_completed,
                )
                report["assignment"] = asdict(recorded)
                reports[sid] = report
                write_report(destinations[sid] / "final_report.json", report)
                processed.add(sid)
                notify(f"{sid}: {profile.status}, recorded sessions={profile.sessions_completed}")
                if report["error"]:
                    notify(f"{sid}: extraction error: {report['error']}")

        for sid, profile in profiles.items():
            if sid not in reports:
                report = {**asdict(profile), "conclusion": None, "school_dropout": None,
                          "unassigned_reason": ("no_matching_history" if sid in unavailable
                                                else "no_feasible_mentor_capacity_or_budget")}
                reports[sid] = report
                write_report(destinations[sid] / "final_report.json", report)
        report = {
            "status": "failed" if any(p.status == "report_failed" for p in profiles.values()) else "finished",
            "seed": school.seed, "problem_rule_version": PROBLEM_RULE_VERSION,
            "history_root": str(root), "output_dir": str(output_dir.resolve()),
            "configuration": {"students": len(profiles), "mentors": len(school.mentors),
                              "allocation_months": school.num_months,
                              "sessions_per_student_total": school.sessions_per_student,
                              "budget": school.budget},
            "assumptions": [
                "Feature rules select hypothetical concerns; priority is not dropout risk.",
                "Seeded matching replays a synthetic history, which may be reused by multiple students.",
                "Dataset profiles select histories and are recorded separately from spoken RAG evidence.",
                "Each programme fits inside its allocation month; there are no numeric treatment effects.",
                "Missing source appointments do not establish refusal or school dropout.",
                "Only recorded appointments incur mentoring cost; whole doses are reserved at admission.",
            ],
            "summary": {"assigned_students": sum(p.mentor_id is not None for p in profiles.values()),
                        "completed_programmes": sum(p.sessions_completed == p.planned_sessions for p in profiles.values()),
                        "incomplete_programmes": sum(p.mentor_id is not None and p.sessions_completed < p.planned_sessions
                                                     for p in profiles.values()),
                        "unassigned_students": sum(p.mentor_id is None for p in profiles.values()),
                        "failed_reports": sum(p.status == "report_failed" for p in profiles.values()),
                        "recorded_sessions": sum(p.sessions_completed for p in profiles.values()),
                        "spent_budget": school.spent_budget, "remaining_budget": school.remaining_budget},
            "assignments": [asdict(a) for a in school.assignment_history],
            "students": reports,
            "participation_completion_score": (
                sum(p.sessions_completed for p in profiles.values()) /
                (len(profiles) * school.sessions_per_student) if profiles else 0.0
            ),
        }
        school.assignments = {sid: profile.mentor_id for sid, profile in profiles.items()
                              if profile.mentor_id is not None}
        school.intervention_report = report
        write_report(output_dir / "final_report.json", report)
        return report
    finally:
        index.close()

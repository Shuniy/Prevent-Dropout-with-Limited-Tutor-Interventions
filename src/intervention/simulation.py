"""Replay feature-matched synthetic programmes through the existing local RAG.

Each student has one mentor and one programme for the entire run. A programme
fits inside an allocation month; its dose defaults to five appointments in total.
Recorded source sessions define participation, without inventing missing meetings
or interpreting the end of a transcript series as school dropout.
"""

try:
    from ..utils.constants import HISTORIES, SIMULATION_RESULTS as RESULTS
except ImportError:  # Direct script entry point.
    from utils.constants import HISTORIES, SIMULATION_RESULTS as RESULTS


from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import random
from typing import TYPE_CHECKING, Callable

from .intervention import Intervention, write_report
from .rag import InterventionRAG, OllamaClient, SessionIndex, load_sessions

try:
    from ..models.student import Student, StudentInterventionProfile
except ImportError:  # Direct ``python src/main.py`` entry point.
    from models.student import Student, StudentInterventionProfile

if TYPE_CHECKING:
    from ..models.school import School


def create_profile(student: Student, planned_sessions: int = 5) -> StudentInterventionProfile:
    """Calculate transparent scenario concerns from available dataset features.

    Severity is an assumed support priority in [0, 1], never a dropout probability.
    Unsupported concerns (e.g. hunger, language needs, diagnoses) are not inferred.
    Missing attendance, engagement and financial need remain unknown.
    """
    if planned_sessions < 1:
        raise ValueError("planned_sessions must be positive")
    return StudentInterventionProfile(
        student.student_id, asdict(student), student.initial_scores,
        student.need_profile, planned_sessions,
    )


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
                                      preferred_mentor_ids=preferred, prioritize_by_need=True)
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
            "output_dir": str(output_dir.resolve()),
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

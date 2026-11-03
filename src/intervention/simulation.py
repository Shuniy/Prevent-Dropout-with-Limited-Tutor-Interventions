"""Replay feature-matched synthetic programmes through the existing local RAG.

Each student has one mentor and one programme for the entire run. A programme
fits inside an allocation month; its dose defaults to five appointments in total.
Recorded source sessions define participation, without inventing missing meetings
or interpreting the end of a transcript series as school dropout.
"""

from ..utils.constants import HISTORIES, SIMULATION_RESULTS as RESULTS


from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import random
from typing import TYPE_CHECKING

from .intervention import Intervention
from .reports import write_report
from .rag import InterventionRAG
from .ollama_client import OllamaClient
from .session_index import SessionIndex
from .transcripts import load_sessions

from ..models.student import Student
from ..models.student_intervention_profile import StudentInterventionProfile

if TYPE_CHECKING:
    from ..models.school import School


def create_profile(student: Student, planned_sessions: int = 5) -> StudentInterventionProfile:
    """Create programme state using the student's highest-priority support."""
    if planned_sessions < 1:
        raise ValueError("planned_sessions must be positive")
    return StudentInterventionProfile(
        student.student_id, student.primary_support_type, planned_sessions,
    )


def run_interventions(
    school: "School", *, root: Path = HISTORIES, output_dir: Path | None = None,
    client: OllamaClient | None = None,
) -> dict:
    """Replay School's existing plan and save session and terminal JSON reports.

    School owns allocation and reserves capacity and budget before this call.
    Only recorded appointments are charged; refunds do not change the plan.
    No student starts a second programme.
    Extraction failures retain validated session reports and mark the run failed.
    A fresh output directory prevents stale sessions from an older run surviving.
    """
    if not school.monthly_assignments:
        raise ValueError("Call school.run_simulation() before run_interventions()")
    if school.intervention_profiles or any(
        assignment.completed_sessions is not None for assignment in school.assignment_history
    ):
        raise ValueError("Interventions have already started; explicitly allocate a new run first")
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
        allocations = list(school.assignment_history)
        if len({a.student_id for a in allocations}) != len(allocations):
            raise ValueError("School allocation plan must contain each student at most once")
        profiles = {student.student_id: create_profile(student, school.sessions_per_student)
                    for student in school.students}
        for assignment in allocations:
            profile = profiles[assignment.student_id]
            profile.support_type = assignment.support_type
            profile.planned_sessions = assignment.sessions
            profile.mentor_id = assignment.mentor_id
        school.intervention_profiles = profiles
        output_dir.mkdir(parents=True, exist_ok=True)
        destinations = {student_id: output_dir / f"student_{number:05d}"
                        for number, student_id in enumerate(profiles, 1)}
        requested = {sid: profile.support_type for sid, profile in profiles.items()}
        unavailable = {sid for sid, support in requested.items() if support not in catalogue}
        rng = random.Random(school.seed)
        rag = InterventionRAG(index, client if client is not None else OllamaClient())
        reports = {}
        students_by_id = {student.student_id: student for student in school.students}
        mentors_by_id = {mentor.mentor_id: mentor for mentor in school.mentors}

        for assignment in allocations:
            sid = assignment.student_id
            profile = profiles[sid]
            if sid in unavailable:
                school.record_intervention_attendance(assignment, 0)
                continue
            profile.history_id = rng.choice(catalogue[assignment.support_type])
            intervention = Intervention(rag, profile, destinations[sid])
            report = intervention.start_intervention(
                students_by_id[sid], mentors_by_id[assignment.mentor_id],
                assignment=assignment,
            )
            recorded = school.record_intervention_attendance(
                assignment, profile.sessions_completed,
            )
            report["assignment"] = asdict(recorded)
            reports[sid] = report
            write_report(destinations[sid] / "final_report.json", report)

        recorded_by_student = {a.student_id: a for a in school.assignment_history}
        for sid, profile in profiles.items():
            if sid not in reports:
                report = {"student_id": sid, "mentor_id": profile.mentor_id, "support_type": profile.support_type,
                          "planned_sessions": profile.planned_sessions, "sessions_completed": 0,
                          "status": "unassigned",
                          "assignment": (asdict(recorded_by_student[sid]) if sid in recorded_by_student else None),
                          "error": None, "conclusion": None,
                          "unassigned_reason": ("no_matching_history" if sid in unavailable
                                                else "no_feasible_mentor_capacity_or_budget")}
                reports[sid] = report
                write_report(destinations[sid] / "final_report.json", report)
        report = {
            "status": "failed" if any(p.status == "report_failed" for p in profiles.values()) else "finished",
            "output_dir": str(output_dir.resolve()),
            "spent_budget": school.spent_budget, "remaining_budget": school.remaining_budget,
            "assignments": [asdict(a) for a in school.assignment_history],
            "students": reports,
        }
        school.intervention_report = report
        write_report(output_dir / "final_report.json", report)
        return report
    finally:
        index.close()

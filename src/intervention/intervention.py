"""Organize one student's recorded sessions with their assigned mentor.

Allocation and resource accounting belong to School/the cohort simulator. This
controller runs one chronological RAG pass and persists each validated session.
"""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Callable

from .rag import InterventionRAG

try:
    from ..models.mentor import Mentor
    from ..models.student import Student, StudentInterventionProfile
except ImportError:  # Direct ``python src/main.py`` entry point.
    from models.mentor import Mentor
    from models.student import Student, StudentInterventionProfile


def write_report(path: Path, report: dict) -> None:
    """Replace one JSON artifact only after its full serialization succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(contents, encoding="utf-8")
    temporary.replace(path)


class Intervention:
    """One assigned programme; create a new instance/profile for another run."""

    def __init__(
        self, rag: InterventionRAG, profile: StudentInterventionProfile,
        output_dir: Path, *, allocation_month: int = 1,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.rag = rag
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.allocation_month = allocation_month
        self.progress = progress

    def start_intervention(self, student: Student, mentor: Mentor) -> dict:
        """Run first and follow-up sessions, returning the student final report.

        The caller must assign a mentor and matching history to the profile first.
        The simulator attaches reconciled resource accounting and saves this final
        report; session files are saved here before the next model call.
        """
        profile = self.profile
        if student.student_id != profile.student_id or mentor.mentor_id != profile.mentor_id:
            raise ValueError("student and mentor must match the assigned profile")
        if student.student_id not in mentor.current_student_ids:
            raise ValueError("student must be assigned to the mentor before intervention")
        if profile.status != "unassigned" or profile.session_reports or profile.sessions_completed:
            raise ValueError("intervention has already started; use a fresh profile")
        if not profile.history_id or profile.planned_sessions < 1:
            raise ValueError("a history and positive planned session count are required")
        history = self.rag.index.history(profile.history_id)[:profile.planned_sessions]
        if [session.number for session in history] != list(range(1, len(history) + 1)) or not history:
            raise ValueError("history must have consecutive sessions starting at 1")
        profile.status = "in_progress"
        self._notify(f"{profile.student_id}: mentor={profile.mentor_id}, history={profile.history_id}")

        def save_session(step: dict) -> None:
            current = history[step["session_number"] - 1]
            completed = len(profile.session_reports) + 1
            record = {
                "student_id": profile.student_id, "mentor_id": profile.mentor_id,
                "history_id": profile.history_id, "allocation_month": self.allocation_month,
                "dataset_profile": profile.dataset_profile,
                "initial_scores": profile.initial_scores, "assigned_problems": profile.problems,
                "planned_sessions": profile.planned_sessions,
                "sessions_completed_as_of_report": completed,
                "conversation": list(current.turns), **step,
            }
            write_report(self.output_dir / f"session_{current.number:02d}.json", record)
            profile.session_reports.append(record)
            profile.sessions_completed = completed
            self._notify(f"{profile.student_id}: session {current.number}/{profile.planned_sessions} report saved")

        error = None
        result = None
        try:
            result = self.rag.analyse(profile.history_id, history[-1].number,
                                      on_session=save_session)
        except (ValueError, RuntimeError) as exc:
            error = str(exc)
        # Recorded attendance is independent of model/extraction availability.
        profile.sessions_completed = len(history)
        profile.status = ("report_failed" if error else
                          "completed" if len(history) == profile.planned_sessions else "incomplete")
        return {
            **asdict(profile), "model": self.rag.client.model,
            "retrieval": "sqlite_fts5_bm25",
            "unrecorded_session_numbers": list(range(len(history) + 1, profile.planned_sessions + 1)),
            "participation_note": "Missing source appointments have unknown reasons; school dropout is unknown.",
            "school_dropout": None, "error": error,
            "conclusion": result["conclusion"] if result else None,
        }

    def _notify(self, message: str) -> None:
        if self.progress is not None:
            self.progress(message)

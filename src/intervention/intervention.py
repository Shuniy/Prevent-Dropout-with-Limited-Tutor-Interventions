"""Run one assigned student's recorded programme and save each valid session."""

from pathlib import Path

from .rag import InterventionRAG
from .reports import write_report
from ..models.mentor_assignment import MentorAssignment
from ..models.mentor import Mentor
from ..models.student import Student
from ..models.student_intervention_profile import StudentInterventionProfile


class Intervention:
    def __init__(self, rag: InterventionRAG, profile: StudentInterventionProfile,
                 output_dir: Path) -> None:
        self.rag = rag
        self.profile = profile
        self.output_dir = Path(output_dir)

    def start_intervention(self, student: Student, mentor: Mentor,
                           *, assignment: MentorAssignment | None = None) -> dict:
        profile = self.profile
        if student.student_id != profile.student_id or mentor.mentor_id != profile.mentor_id:
            raise ValueError("student and mentor must match the assigned profile")
        if assignment is not None:
            # A completed allocation plan can include earlier monthly caseloads.
            if (assignment.student_id != student.student_id
                    or assignment.mentor_id != mentor.mentor_id
                    or assignment.support_type != profile.support_type
                    or assignment.sessions != profile.planned_sessions
                    or assignment.completed_sessions is not None):
                raise ValueError("assignment must match the unprocessed programme")
        elif student.student_id not in mentor.current_student_ids:
            raise ValueError("student must be assigned to the mentor before intervention")
        if profile.status != "unassigned" or profile.session_reports or profile.sessions_completed:
            raise ValueError("intervention has already started; use a fresh profile")
        if not profile.history_id or profile.planned_sessions < 1:
            raise ValueError("a history and positive planned session count are required")
        history = self.rag.index.history(profile.history_id)[:profile.planned_sessions]
        if not history or [s.number for s in history] != list(range(1, len(history) + 1)):
            raise ValueError("history must have consecutive sessions starting at 1")
        profile.status = "in_progress"

        def save_session(step: dict) -> None:
            record = {"student_id": profile.student_id, "mentor_id": profile.mentor_id, **step}
            write_report(self.output_dir / f"session_{step['session_number']:02d}.json", record)
            profile.session_reports.append(record)

        error = None
        result = None
        try:
            result = self.rag.analyse(profile.history_id, history[-1].number, on_session=save_session)
        except (ValueError, RuntimeError) as exc:
            error = str(exc)
        # Attendance is recorded even if the model cannot process every meeting.
        profile.sessions_completed = len(history)
        profile.status = ("report_failed" if error else
                          "completed" if len(history) == profile.planned_sessions else "incomplete")
        return {
            "student_id": profile.student_id, "mentor_id": profile.mentor_id,
            "support_type": profile.support_type,
            "planned_sessions": profile.planned_sessions,
            "sessions_completed": profile.sessions_completed,
            "status": profile.status, "error": error,
            "conclusion": result["conclusion"] if result else None,
        }

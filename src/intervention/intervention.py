"""Confidential programme execution with no school imports or mutation callbacks."""

from dataclasses import asdict
from pathlib import Path
from numpy.random import Generator

from ..utils.constants import SEED, create_rng

from .history_assignment import catalogue_histories, select_history
from .intervention_request import InterventionRequest
from .intervention_result import InterventionResult
from .reports import write_report
from .session_index import SessionIndex
from .student_intervention_profile import StudentInterventionProfile


class Intervention:
    def __init__(self, index: SessionIndex, client, *, seed: int = SEED,
                 private_output_dir: Path | None = None) -> None:
        from .rag import InterventionRAG
        self._rag = InterventionRAG(index, client)
        self._catalogue = catalogue_histories(index)
        self._seed = seed
        self._random_by_run: dict[str, Generator] = {}
        self._programmes: dict[tuple[str, str], StudentInterventionProfile] = {}
        self._private_output_dir = Path(private_output_dir) if private_output_dir is not None else None
        if self._private_output_dir is not None:
            if self._private_output_dir.exists() and any(self._private_output_dir.iterdir()):
                raise FileExistsError("Private output directory must be new or empty")

    def simulate(self, request: InterventionRequest) -> InterventionResult:
        if not isinstance(request, InterventionRequest):
            raise TypeError("simulate requires an InterventionRequest")
        key = (request.run_id, request.programme_id)
        if key in self._programmes:
            raise ValueError("programme has already started")
        if request.run_id not in self._random_by_run:
            self._random_by_run[request.run_id] = create_rng(self._seed)
        rng = self._random_by_run[request.run_id]
        history_id = select_history(self._catalogue, request.support_type, rng)
        profile = StudentInterventionProfile(request, history_id)
        self._programmes[key] = profile
        # Storage names use internal counters, never caller-provided IDs or paths.
        destination = (self._private_output_dir / f"programme_{len(self._programmes):05d}"
                       if self._private_output_dir is not None else None)
        fields = asdict(request)
        if history_id is None:
            return InterventionResult(**fields, sessions_completed=0, status="unavailable",
                                      analysis_status="unavailable")
        history = self._rag.index.history(history_id)[:request.planned_sessions]
        profile.sessions_completed = len(history)

        def save_session(step: dict) -> None:
            profile.session_reports.append(step)
            if destination is not None:
                write_report(destination / f"session_{step['session_number']:02d}.json",
                             {**fields, "history_id": history_id, **step})

        analysis = None
        try:
            analysis = self._rag.analyse(history_id, history[-1].number, on_session=save_session)
        except (ValueError, RuntimeError) as exc:
            profile.error = str(exc)
        # Free text, exception text, paths and detailed findings stay private.
        outcome = analysis["conclusion"]["outcome"] if analysis else {}
        result = InterventionResult(
            **fields, sessions_completed=len(history),
            status="completed" if len(history) == request.planned_sessions else "incomplete",
            analysis_status="failed" if profile.error else "completed",
            attendance_improved=outcome.get("attendance_improved", "unknown"),
            primary_barrier_resolved=outcome.get("primary_barrier_resolved", "unknown"),
            intervention_helpful=outcome.get("intervention_helpful", "unknown"),
        )
        if destination is not None:
            write_report(destination / "private_report.json", {
                **fields, "history_id": history_id, "error": profile.error,
                "result": asdict(result), "conclusion": analysis["conclusion"] if analysis else None,
            })
        return result

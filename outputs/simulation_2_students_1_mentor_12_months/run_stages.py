"""Run the existing simulation and capture its stage outputs for review."""
import json
from dataclasses import asdict
from pathlib import Path

from src.school.school import School
from src.school.performance import snapshot
from src.intervention import Intervention
from src.intervention.ollama_client import OllamaClient
from src.intervention.session_index import SessionIndex
from src.intervention.transcripts import load_sessions
from src.utils.constants import HISTORIES

ROOT = Path(__file__).resolve().parent


def main():
    school = School(num_students=2, num_mentors=1, num_months=12, seed=42)
    captured = {"profiles": [{"source_profile": asdict(s), "needs": s.need_profile,
                              "need_score": s.need_score,
                              "baseline": asdict(snapshot(s, school.performance[s.student_id]))}
                             for s in school.students],
                "mentors": [asdict(m) for m in school.mentors],
                "allocations": [], "requests": [], "processed_results": [], "school_changes": []}
    original_step = school.step
    def step(*args, **kwargs):
        allocations = original_step(*args, **kwargs)
        captured["allocations"].extend(asdict(a) for a in allocations)
        return allocations
    school.step = step
    original_apply = school.apply_intervention_result
    def apply(result):
        student = next(s for s in school.students if s.student_id == result.student_id)
        before = asdict(snapshot(student, school.performance[student.student_id]))
        budget_before = school.spent_budget
        captured["processed_results"].append(asdict(result))
        original_apply(result)
        captured["school_changes"].append({"student_id": student.student_id, "month": result.month,
            "before": before, "after": asdict(snapshot(student, school.performance[student.student_id])),
            "spent_budget_before": budget_before, "spent_budget_after": school.spent_budget})
    school.apply_intervention_result = apply
    index = SessionIndex()
    try:
        index.build(load_sessions(HISTORIES))
        intervention = Intervention(index, OllamaClient(), seed=42, private_output_dir=ROOT / "private")
        original_simulate = intervention.simulate
        def simulate(request):
            captured["requests"].append(asdict(request))
            print(f"Processing programme {len(captured['requests'])}: {request.support_type}", flush=True)
            result = original_simulate(request)
            print(f"Programme result: {result.analysis_status}", flush=True)
            return result
        intervention.simulate = simulate
        report = school.run_simulation(intervention, output_dir=ROOT / "school")
        captured["final_report"] = report
        (ROOT / "stage_capture.json").write_text(json.dumps(captured, indent=2) + "\n")
        print(f"Simulation status: {report['status']}", flush=True)
    finally:
        index.close()


if __name__ == "__main__":
    main()

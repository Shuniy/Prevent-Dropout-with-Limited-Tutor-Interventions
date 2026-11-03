"""School-owned monthly allocation, intervention, evaluation and reporting cycle."""

from pathlib import Path
from uuid import uuid4
from ..utils.constants import SIMULATION_RESULTS
from .monthly_evaluation import MonthlyEvaluation
from .performance import snapshot
from .reports import final_report, monthly_report, write_report


def run_simulation(school, intervention, *, output_dir: Path | None = None,
                   support_type=None) -> dict:
    output_dir = Path(output_dir) if output_dir is not None else SIMULATION_RESULTS / f"run_{uuid4().hex}"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {output_dir}")
    preferred = school._prepare_run()
    output_dir.mkdir(parents=True, exist_ok=True)
    for month in range(1, school.num_months + 1):
        school.current_month = month
        before = {s.student_id: snapshot(s, school.performance[s.student_id]) for s in school.students}
        allocations = school.step(month, support_type=support_type, preferred_mentor_ids=preferred)
        # Plan this whole month before reconciling; never refill it after refunds.
        for assignment in allocations:
            request = school.make_intervention_request(assignment)
            school.apply_intervention_result(intervention.simulate(request))
        school.monthly_evaluations[month] = [
            MonthlyEvaluation(month, s.student_id, before[s.student_id],
                              snapshot(s, school.performance[s.student_id])) for s in school.students
        ]
        report = monthly_report(school, month)
        school.monthly_reports[month] = report
        write_report(output_dir / f"month_{month:02d}.json", report)
        school.current_month = month + 1
    report = final_report(school, output_dir)
    school.simulation_report = report
    write_report(output_dir / "final_report.json", report)
    return report

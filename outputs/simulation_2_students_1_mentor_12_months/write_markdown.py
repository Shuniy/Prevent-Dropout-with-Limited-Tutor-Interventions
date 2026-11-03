"""Format captured outputs without introducing case links or changing results."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    data = json.loads((ROOT / "stage_capture.json").read_text())
    parts = ["# Simulation stage outputs: 2 students, 1 mentor, 12 months\n",
             "Run date: 4 November 2026. Seed: 42. Model: `qwen3.5:latest`. "
             "Students are the first two records in the supplied synthetic population. "
             "Defaults: five planned sessions per student, mentor capacity 10 students / 50 sessions per month, "
             "budget 10,000 units, cost 1 unit per recorded session.\n",
             "This is a replay of synthetic recorded interventions. Each student receives at most one programme; "
             "the programme is processed in its allocation month, rather than spread over 12 months. "
             "No new case-linking logic or cross-case interpretation has been added. "
             "The existing runner selects a recorded history by support type; RAG outputs below are presented "
             "independently in execution order, without source-case links or a student-to-history mapping.\n",
             "The RAG section contains private synthetic narrative findings for this requested review. "
             "The standard school exports remain separate and contain only allowlisted outcomes.\n"]
    def heading(text):
        parts.append(f"\n## {text}\n")
    def block(obj):
        parts.append("\n```json\n" + json.dumps(obj, indent=2, ensure_ascii=False) + "\n```\n")
    heading("Output 1 - Student allocation to mentors")
    parts.append("Allocations at admission, before recorded-session costs are reconciled:\n")
    block(data["allocations"])
    heading("Output 2 - Student profiles, needs, scores and mentor selection reasons")
    parts.append("Need score is the highest rule-based need severity on a 0–1 scale, not a predicted dropout probability. "
                 "Students are considered in descending score order; seeded shuffling breaks ties. "
                 "Mentor eligibility checks support skills, caseload, session capacity and budget. "
                 "Among eligible mentors, the lowest caseload and then mentor ID decide selection.\n")
    for profile in data["profiles"]:
        sid = profile["source_profile"]["student_id"]
        assignment = next((a for a in data["allocations"] if a["student_id"] == sid), None)
        parts.append(f"\n### {sid}\n")
        block(profile)
        if assignment:
            parts.append(f"Selected for `{assignment['mentor_id']}` because the primary need requires "
                         f"`{assignment['support_type']}` and the sole generalist mentor supports that service. "
                         f"The mentor had sufficient student and session capacity, and the budget covered "
                         f"{assignment['sessions']} sessions ({assignment['cost_units']} units reserved). "
                         "There was no competing mentor to rank.\n")
    parts.append("\nMentor configuration:\n")
    block(data["mentors"])
    heading("Output 3 - Intervention results from RAG")
    parts.append("These are the actual validated model findings saved at each session. Earlier validated findings "
                 "and retrieved earlier passages from the same history feed later sessions. "
                 "The final valid session supplies the programme conclusion. A generation or validation failure "
                 "stops that programme's analysis; any saved partial findings are retained.\n")
    for number, directory in enumerate(sorted((ROOT / "private").glob("programme_*")), 1):
        parts.append(f"\n### RAG execution {number}\n")
        for path in sorted(directory.glob("session_*.json")):
            session = json.loads(path.read_text())
            block({"session_number": session["session_number"], "findings": session["findings"]})
        private = json.loads((directory / "private_report.json").read_text())
        block({"error": private["error"], "conclusion": private["conclusion"]})
    heading("Output 4 - Processed intervention results")
    parts.append("Scalar requests sent to Intervention:\n")
    block(data["requests"])
    parts.append("\nImmutable allowlisted results returned to School; private narrative findings are excluded:\n")
    block(data["processed_results"])
    heading("Output 5 - Results processed by School and changes made")
    parts.append("School validates programme identity and session counts, records participation, reconciles reserved costs, "
                 "and applies known reported outcomes. Unknown or conflicting outcomes retain their prior values. "
                 "Grades, attendance fraction, engagement and enrolment are not numerically changed by this policy.\n")
    block(data["school_changes"])
    heading("Output 6 - Monthly school outputs (months 1–12)")
    parts.append("Each month includes allocations, processed results, budget and before/after evaluations for both students. "
                 "Later months do not introduce additional programmes for already assigned students.\n")
    for path in sorted((ROOT / "school").glob("month_*.json")):
        report = json.loads(path.read_text())
        parts.append(f"\n### Month {report['month']}\n")
        block(report)
    heading("Output 7 - Final simulation report")
    block(data["final_report"])
    destination = ROOT / "simulation_stage_outputs.md"
    destination.write_text("\n".join(parts))
    print(destination)


if __name__ == "__main__":
    main()

"""Allocate mentors and process recorded interventions with local Ollama."""

import argparse
from pathlib import Path

if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.school import School
from src.intervention.ollama_client import OllamaClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Allocate students and replay synthetic interventions with local Ollama.")
    parser.add_argument("--students", type=int, default=10)
    parser.add_argument("--mentors", type=int, default=2)
    parser.add_argument("--months", type=int, default=12, help="Allocation windows; students enter only once")
    parser.add_argument("--sessions", type=int, default=5, help="Total planned appointments per student")
    parser.add_argument("--capacity", type=int, default=10, help="Students per mentor per allocation window")
    parser.add_argument("--budget", type=float, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--history-root", type=Path)
    parser.add_argument("--output", type=Path, help="New or empty report directory")
    parser.add_argument("--allocation-only", action="store_true", help="Allocate students without an LLM")
    args = parser.parse_args()
    try:
        school = School(num_students=args.students, num_mentors=args.mentors,
                        num_months=args.months, sessions_per_student=args.sessions,
                        students_per_mentor=args.capacity, budget=args.budget, seed=args.seed)
    except ValueError as exc:
        parser.exit(1, f"Error: {exc}\n")
    school.run_simulation()
    if args.allocation_only:
        print(f"Allocation complete: months={school.num_months}, spent_budget={school.spent_budget}")
        return
    options = {"output_dir": args.output, "client": OllamaClient(args.model)}
    if args.history_root is not None:
        options["root"] = args.history_root
    try:
        report = school.run_interventions(**options)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    path = Path(report["output_dir"]) / "final_report.json"
    if report["status"] == "failed":
        failures = [student["error"] for student in report["students"].values() if student["error"]]
        parser.exit(1, f"Intervention failed: {failures[0]}. Results: {path}\n")
    print(f"Intervention finished: {path}")


if __name__ == "__main__":
    main()

"""Allocate mentors and process recorded interventions with local Ollama."""

import argparse
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.school.school import School
from src.intervention import Intervention
from src.intervention.ollama_client import OllamaClient
from src.intervention.session_index import SessionIndex
from src.intervention.transcripts import load_sessions
from src.utils.constants import HISTORIES, SIMULATION_RESULTS, SEED


def main() -> None:
    parser = argparse.ArgumentParser(description="Allocate students and replay synthetic interventions with local Ollama.")
    parser.add_argument("--students", type=int, default=10)
    parser.add_argument("--mentors", type=int, default=2)
    parser.add_argument("--months", type=int, default=12, help="Months of school tracking; each student enters one programme")
    parser.add_argument("--sessions", type=int, default=5, help="Total planned appointments per student")
    parser.add_argument("--capacity", type=int, default=10, help="Students per mentor per allocation window")
    parser.add_argument("--budget", type=float, default=10000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--history-root", type=Path)
    parser.add_argument("--output", type=Path, help="New or empty school report directory")
    parser.add_argument("--allocation-only", action="store_true", help="Allocate students without an LLM")
    parser.add_argument("--private-output", type=Path, help="Separate private findings directory (optional)")
    args = parser.parse_args()
    try:
        school = School(num_students=args.students, num_mentors=args.mentors,
                        num_months=args.months, sessions_per_student=args.sessions,
                        students_per_mentor=args.capacity, budget=args.budget, seed=args.seed)
    except ValueError as exc:
        parser.exit(1, f"Error: {exc}\n")
    if args.allocation_only:
        school.allocate_programmes()
        print(f"Allocation complete: months={school.num_months}, spent_budget={school.spent_budget}")
        return
    output_dir = args.output if args.output is not None else SIMULATION_RESULTS / f"run_{uuid4().hex}"
    if args.private_output is not None:
        public, private = output_dir.resolve(), args.private_output.resolve()
        if public == private or public in private.parents or private in public.parents:
            parser.exit(1, "Error: School and private intervention output directories must be separate\n")
    index = SessionIndex()
    try:
        index.build(load_sessions(args.history_root if args.history_root is not None else HISTORIES))
        intervention = Intervention(index, OllamaClient(args.model), seed=args.seed,
                                    private_output_dir=args.private_output)
        report = school.run_simulation(intervention, output_dir=output_dir)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    finally:
        index.close()
    path = Path(report["output_dir"]) / "final_report.json"
    if report["status"] == "failed":
        parser.exit(1, f"Intervention failed: analysis failed for one or more programmes. Results: {path}\n")
    print(f"Intervention finished: {path}")


if __name__ == "__main__":
    main()

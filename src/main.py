"""Run school allocation, recorded interventions or synthetic CMDP experiments."""

import argparse
from dataclasses import replace
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


def run_cmdp_experiments(args):
    """Translate CLI choices into explicit school experiment dependencies."""
    from src.school.allocation_policies import DEFAULT_POLICIES
    from src.school.cmdp_experiments import run_experiments
    from src.school.scenario_config import ScenarioConfig

    if args.private_output is not None:
        raise ValueError("private findings output is available only for recorded interventions")
    config_path = args.config or Path(__file__).resolve().parents[1] / "configs/cmdp_v1.toml"
    config = ScenarioConfig.load(config_path)
    fields = {
        "students": "num_students",
        "mentors": "num_mentors",
        "months": "horizon",
        "sessions": "appointments_per_programme",
        "capacity": "monthly_admissions",
        "budget": "budget",
        "seed": "seed",
    }
    overrides = {
        field: getattr(args, argument)
        for argument, field in fields.items()
        if getattr(args, argument) is not None
    }
    config = replace(config, **overrides)
    return run_experiments(
        config,
        output=args.output,
        suite=args.suite or "default",
        development_seed_count=args.development_seeds if args.development_seeds is not None else 10,
        evaluation_seed_count=args.evaluation_seeds if args.evaluation_seeds is not None else 30,
        policies=args.policies if args.policies is not None else DEFAULT_POLICIES,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run school allocation, recorded interventions or synthetic CMDP experiments."
    )
    parser.add_argument("--students", type=int)
    parser.add_argument("--mentors", type=int)
    parser.add_argument(
        "--months", type=int, help="Months of school tracking; each student enters one programme"
    )
    parser.add_argument("--sessions", type=int, help="Total planned appointments per student")
    parser.add_argument("--capacity", type=int, help="Students per mentor per allocation window")
    parser.add_argument("--budget", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument(
        "--method",
        choices=("simple", "rag"),
        default="simple",
        help="One all-sessions extraction (default) or session-by-session RAG",
    )
    parser.add_argument("--history-root", type=Path)
    parser.add_argument("--output", type=Path, help="New or empty school report directory")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--allocation-only", action="store_true", help="Allocate students without an LLM"
    )
    modes.add_argument(
        "--cmdp",
        action="store_true",
        help="Run synthetic retention policy comparisons without an LLM",
    )
    parser.add_argument(
        "--config", type=Path, help="CMDP TOML configuration (default: configs/cmdp_v1.toml)"
    )
    parser.add_argument(
        "--suite",
        choices=("default", "full"),
        help="CMDP default comparison or full effect/budget sweep",
    )
    parser.add_argument(
        "--development-seeds", type=int, help="CMDP development repetitions (1-10; default 10)"
    )
    parser.add_argument(
        "--evaluation-seeds",
        type=int,
        help="CMDP independent evaluation repetitions (1-30; default 30)",
    )
    parser.add_argument(
        "--policies",
        nargs="+",
        help="CMDP policies: wait random severity need_priority longest_waiting terminal_value fairness",
    )
    parser.add_argument(
        "--private-output", type=Path, help="Separate private findings directory (optional)"
    )
    args = parser.parse_args()
    if args.cmdp:
        try:
            output = run_cmdp_experiments(args)
        except (ValueError, RuntimeError, OSError) as exc:
            parser.exit(1, f"Error: {exc}\n")
        print(f"Saved simulation results: {output}")
        return
    if any(
        value is not None
        for value in (
            args.config,
            args.suite,
            args.development_seeds,
            args.evaluation_seeds,
            args.policies,
        )
    ):
        parser.error("CMDP experiment options require --cmdp")
    # Existing recorded/allocation defaults stay independent of CMDP configuration.
    defaults = {
        "students": 10,
        "mentors": 2,
        "months": 12,
        "sessions": 5,
        "capacity": 10,
        "budget": 10000,
        "seed": SEED,
    }
    for name, value in defaults.items():
        if getattr(args, name) is None:
            setattr(args, name, value)
    try:
        school = School(
            num_students=args.students,
            num_mentors=args.mentors,
            num_months=args.months,
            sessions_per_student=args.sessions,
            students_per_mentor=args.capacity,
            budget=args.budget,
            seed=args.seed,
        )
    except ValueError as exc:
        parser.exit(1, f"Error: {exc}\n")
    if args.allocation_only:
        school.allocate_programmes()
        print(
            f"Allocation complete: months={school.num_months}, spent_budget={school.spent_budget}"
        )
        return
    output_dir = (
        args.output if args.output is not None else SIMULATION_RESULTS / f"run_{uuid4().hex}"
    )
    if args.private_output is not None:
        public, private = output_dir.resolve(), args.private_output.resolve()
        if public == private or public in private.parents or private in public.parents:
            parser.exit(
                1, "Error: School and private intervention output directories must be separate\n"
            )
    index = None
    try:
        sessions = load_sessions(args.history_root if args.history_root is not None else HISTORIES)
        if args.method == "rag":
            index = SessionIndex()
            index.build(sessions)
        intervention = Intervention(
            index if index is not None else sessions,
            OllamaClient(args.model),
            seed=args.seed,
            method=args.method,
            private_output_dir=args.private_output,
        )
        report = school.run_simulation(intervention, output_dir=output_dir)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    finally:
        if index is not None:
            index.close()
    path = Path(report["output_dir"]) / "final_report.json"
    if report["status"] == "failed":
        parser.exit(
            1, f"Intervention failed: analysis failed for one or more programmes. Results: {path}\n"
        )
    print(f"Intervention finished: {path}")


if __name__ == "__main__":
    main()

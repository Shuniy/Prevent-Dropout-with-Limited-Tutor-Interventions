"""Run synthetic CMDP experiments."""

import argparse
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_cmdp_experiments(args):
    """Translate CLI choices into explicit school experiment dependencies."""
    from src.school.allocation_policies import DEFAULT_POLICIES
    from src.school.cmdp_experiments import run_experiments
    from src.school.scenario_config import ScenarioConfig

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
    parser = argparse.ArgumentParser(description="Run synthetic CMDP experiments.")
    parser.add_argument("--students", type=int)
    parser.add_argument("--mentors", type=int)
    parser.add_argument("--months", type=int, help="CMDP simulation horizon in months")
    parser.add_argument("--sessions", type=int, help="Total planned appointments per student")
    parser.add_argument("--capacity", type=int, help="Maximum monthly programme admissions")
    parser.add_argument("--budget", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path, help="New or empty CMDP report directory")
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
    args = parser.parse_args()
    try:
        output = run_cmdp_experiments(args)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Saved simulation results: {output}")


if __name__ == "__main__":
    main()

"""Run synthetic CMDP experiments."""

import argparse
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_cmdp_experiments(args):
    """Translate CLI choices into explicit school experiment dependencies."""
    if args.runner == 'delivery':
        from src.school.delivery_config import DeliveryConfig
        from src.school.delivery_experiments import run_demonstration
        if args.months is not None or args.capacity is not None:
            raise ValueError('weekly delivery requires --weeks and explicit weekly calendar settings, not monthly units')
        config = DeliveryConfig.load(args.config or Path(__file__).resolve().parents[1] / 'configs/delivery_weekly_v1.toml')
        fields = {'students':'num_students', 'mentors':'num_mentors', 'weeks':'horizon_weeks',
                  'sessions':'sessions_required', 'budget':'budget', 'seed':'seed', 'effect_strength':'effect_strength'}
        config = replace(config, **{field:getattr(args, key) for key,field in fields.items()
                                   if getattr(args, key) is not None})
        if args.output is None:
            raise ValueError('weekly delivery demonstration requires a new --output directory')
        run_demonstration(config, args.output)
        return args.output
    if getattr(args, 'weeks', None) is not None:
        raise ValueError('--weeks requires --runner delivery; monthly runners use --months')
    if args.runner == "comparison":
        from src.school.simulation_comparison import run_comparison

        return run_comparison(args)
    from src.school.allocation_policies import DEFAULT_POLICIES
    from src.school.cmdp_experiments import run_experiments
    from src.school.scenario_config import ScenarioConfig

    config_path = args.config or Path(__file__).resolve().parents[1] / "configs/cmdp_baselines.toml"
    config = ScenarioConfig.load(config_path)
    fields = {
        "students": "num_students",
        "mentors": "num_mentors",
        "months": "horizon",
        "sessions": "appointments_per_programme",
        "capacity": "monthly_admissions",
        "budget": "budget",
        "seed": "seed",
        "effect_strength": "effect_strength",
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
        print_monthly=args.print_monthly,
        stage=args.stage or "both",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run synthetic CMDP experiments.")
    parser.add_argument("--runner", choices=("comparison", "baselines", "delivery"), default="comparison",
                        help="Monthly comparison (default), legacy baselines, or offline weekly delivery demonstration")
    parser.add_argument("--extractor", choices=("fixture", "ollama"), default="ollama")
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-notes-per-month", type=int,
                        help="Limit intervention programme notes per source month")
    parser.add_argument("--max-monitoring-notes-per-month", type=int, default=1,
                        help="Limit actionable monitoring notes per decision cutoff (default: 1)")
    parser.add_argument("--extraction-contract", choices=("actionable_monitoring", "legacy_programme_only"),
                        default="actionable_monitoring")
    parser.add_argument("--feedback-policies", nargs="+", choices=("resource", "fairness", "robust"),
                        default=["resource", "fairness"])
    parser.add_argument("--modes", nargs="+",
                        choices=("oracle", "structured", "b_matched", "llm_notes", "noisy_notes"),
                        default=["oracle", "structured", "b_matched", "llm_notes", "noisy_notes"])
    parser.add_argument("--students", type=int)
    parser.add_argument("--mentors", type=int)
    parser.add_argument("--months", type=int, help="CMDP simulation horizon in months")
    parser.add_argument('--weeks', type=int, help='Weekly delivery horizon (requires --runner delivery)')
    parser.add_argument("--sessions", type=int, help="Total planned appointments per student")
    parser.add_argument("--capacity", type=int, help="Maximum monthly programme admissions")
    parser.add_argument("--budget", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--effect-strength", type=float, help="Synthetic intervention strength in [0, 1]")
    parser.add_argument("--stage", choices=("development", "both"), default=None,
                        help="Inspect development only, or validate development then run held-out worlds")
    parser.add_argument(
        "--print-monthly",
        action="store_true",
        help="Print month-zero, monthly and terminal summaries for the first development "
        "seed of each policy/scenario",
    )
    parser.add_argument("--output", type=Path, help="New CMDP report directory (never overwrite a run)")
    parser.add_argument(
        "--config", type=Path, help="Shared TOML configuration; defaults to feedback config for "
        "comparison, baseline config for --runner baselines"
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

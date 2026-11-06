"""Run the frozen Step 4 paired fairness, budget and intervention-strength grid."""

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.school.fairness_experiments import run_fairness_experiments
from src.school.scenario_config import ScenarioConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/cmdp_fairness.toml"))
    parser.add_argument("--output", type=Path, default=Path("results/cmdp_fairness"))
    parser.add_argument("--development-seeds", type=int, default=10)
    parser.add_argument("--evaluation-seeds", type=int, default=30)
    parser.add_argument("--stage", choices=("development", "both"), default="both")
    args = parser.parse_args()
    output = run_fairness_experiments(ScenarioConfig.load(args.config), output=args.output,
        development_seed_count=args.development_seeds, evaluation_seed_count=args.evaluation_seeds,
        stage=args.stage)
    print(f"Saved Step 4 results: {output}")


if __name__ == "__main__":
    main()

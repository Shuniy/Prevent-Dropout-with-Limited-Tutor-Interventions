"""Console adapter for the same functions imported by Jupyter notebooks."""
import argparse

from .experiments.runner import DEFAULT_CONFIG, population_summary, run_simulation


def main(argv=None):
    parser = argparse.ArgumentParser(description='Student support research workflows')
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('summary', help='Summarize the supplied population')
    simulation = commands.add_parser('simulate', help='Run or validate simulation inputs')
    simulation.add_argument('--config', default=DEFAULT_CONFIG, help='TOML configuration file')
    simulation.add_argument('--dry-run', action='store_true', help='Validate reset only; no transitions')
    args = parser.parse_args(argv)
    try:
        if args.command == 'simulate':
            result = run_simulation(args.config, dry_run=args.dry_run)
            print(result.to_string(index=False))
        else:
            print(population_summary().to_string())
    except (ValueError, OSError, NotImplementedError) as error:
        parser.exit(2, f'Error: {error}\n')
    return 0

"""Verify retained immutable research records without executing experiments."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.evaluation.provenance import verify_versions

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--allow-historical', action='store_true',
        help='Allow partial legacy verification; derived artifacts remain explicitly unverified')
    args = parser.parse_args()
    try:
        result = verify_versions(args.output)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, indent=2))
        sys.exit(1)
    print(json.dumps(result, indent=2))
    if not result['fully_verified'] and not args.allow_historical:
        sys.exit(2)

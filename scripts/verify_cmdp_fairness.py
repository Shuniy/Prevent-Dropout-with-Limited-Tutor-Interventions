"""Independently reconcile the saved Step 4 grid, actual coverage and resources."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.school.fairness_audit import required_access
from src.utils.constants import DEFAULT_STUDENT_DATA_PATH


def verify(output):
    output = Path(output)
    manifest = json.loads((output / "experiment_config.json").read_text())
    completed = json.loads((output / "COMPLETED.json").read_text())
    def read(name):
        with (output / (name + ".csv")).open(newline="") as source:
            return list(csv.DictReader(source))
    def identity(row):
        return row["partition"], int(row["seed"]), float(row["budget"]), float(row["effect_strength"]), row["policy"]
    episodes = read("episode_results")
    by_id = {identity(row): row for row in episodes}
    expected = {(partition, seed, budget, alpha, label)
                for partition, seeds in manifest["seed_partitions"].items() for seed in seeds
                for budget, alpha, label, *_ in manifest["grid"]}
    assert len(by_id) == len(episodes) == len(expected) == completed["episodes"]
    assert set(by_id) == expected
    monthly = defaultdict(list)
    for row in read("monthly_results"):
        monthly[identity(row)].append(row)
    for key, episode in by_id.items():
        rows = sorted(monthly[key], key=lambda row: int(row["month"]))
        assert [int(r["month"]) for r in rows] == list(range(manifest["config"]["horizon"] + 1))
        assert math.isclose(sum(float(r["spending"]) for r in rows), float(episode["spending"]), abs_tol=1e-8)
        assert sum(int(r["programmes_started"]) for r in rows) == int(episode["programmes"])
        assert all(float(r["remaining_budget"]) >= 0 for r in rows)
        reference = by_id[(*key[:4], "terminal_value")]
        assert episode["initial_state_hash"] == reference["initial_state_hash"]
        if key[-1] == "fairness_q0":
            assert episode["allocation_sha256"] == reference["allocation_sha256"]
        if key[3] == 0:
            assert episode["trajectory_sha256"] == reference["trajectory_sha256"]
        assert float(episode["solver_failures"]) == float(episode["feasibility_validation_failures"]) == 0
    history = defaultdict(list)
    for row in read("window_history"):
        key = (*identity(row), int(row["window_start"]), row["group"], row["condition_at_start"])
        history[key].append(row)
    cells = read("group_access")
    for cell in cells:
        size, admitted = int(cell["eligible_count"]), int(cell["unique_admissions"])
        required = required_access(float(cell["target_coverage"]), size)
        assert int(cell["required_students"]) == required
        assert int(cell["coverage_shortfall"]) == max(0, required - admitted)
        assert 0 <= admitted <= size
        assert bool(cell["access_rate"]) == bool(size)
        if size:
            assert math.isclose(float(cell["access_rate"]), admitted / size, abs_tol=1e-10)
        key = (*identity(cell), int(cell["window_start"]), cell["group"], cell["condition_at_start"])
        rows = sorted(history[key], key=lambda row: int(row["month"]))
        assert len({r["eligible_count"] for r in rows}) == 1
        assert all(int(r["newly_covered"]) >= 0 for r in rows)
        assert sum(int(r["newly_covered"]) for r in rows) == admitted
        assert int(rows[-1]["actual_covered"]) == admitted
    diagnostics = read("solver_diagnostics")
    statuses = Counter(row["status"] for row in diagnostics)
    source_dir = Path(__file__).resolve().parents[1] / "src/school"
    source_matches = all(hashlib.sha256((source_dir / name).read_bytes()).hexdigest() == digest
                         for name, digest in manifest["source_sha256"].items())
    assert source_matches, "experiment code differs from the frozen manifest"
    assert hashlib.sha256(Path(DEFAULT_STUDENT_DATA_PATH).read_bytes()).hexdigest() == manifest["population_sha256"]
    report = {"status": "passed", "episodes": len(episodes), "group_window_cells": len(cells),
              "monthly_decisions": len(diagnostics), "solver_statuses": dict(statuses),
              "incomplete_hierarchies": sum(row["lexicographic_complete"] == "False" for row in diagnostics if row["planner_version"]),
              "checks": ["manifest grid", "budget ledger", "programme totals", "frozen denominators",
                         "unique actual admissions", "integer thresholds and realized shortfalls",
                         "q=0 exact decisions", "alpha=0 exact trajectories", "no allocation validation failures",
                         "source code and population hashes"]}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("results/cmdp_fairness_v1"))
    parser.add_argument("--reference", type=Path, help="Optional previous grid for exact nontiming comparison")
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))
    if args.reference is not None:
        def episodes(path):
            with (path / "episode_results.csv").open(newline="") as source:
                return [{k: v for k, v in row.items() if "runtime" not in k}
                        for row in csv.DictReader(source)]
        current, previous = episodes(args.output), episodes(args.reference)
        assert current == previous, "nontiming episode results differ from reference grid"
        current_manifest = json.loads((args.output / "experiment_config.json").read_text())
        previous_manifest = json.loads((args.reference / "experiment_config.json").read_text())
        changed = [name for name, digest in current_manifest["source_sha256"].items()
                   if previous_manifest["source_sha256"].get(name) != digest]
        result = {"status": "passed", "episodes": len(current),
                  "comparison": "all episode columns except wall-clock runtime fields",
                  "source_files_different_from_reference": changed,
                  "current_source_sha256": current_manifest["source_sha256"],
                  "reference_source_sha256": previous_manifest["source_sha256"]}
        (args.output / "reproducibility.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if "sha256" not in k}, indent=2))


if __name__ == "__main__":
    main()

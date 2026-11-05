"""Independently audit saved Step 3 outputs without rerunning allocation logic.

Usage: .venv/bin/python scripts/verify_cmdp_planner.py RESULT_DIRECTORY [--write]
"""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics

import numpy as np
from scipy.stats import t


def verify(output):
    manifest = json.loads((output / "manifest.json").read_text())
    completed = json.loads((output / "COMPLETED.json").read_text())
    episodes = [json.loads(line) for line in (output / "episodes.jsonl").open()]
    expected = {
        (f"effect_{alpha:g}_budget_{budget:g}", partition, policy, seed)
        for alpha, budget in manifest["variations"]
        for partition in manifest["partitions"]
        for policy in manifest["policies"] for seed in manifest[partition + "_seeds"]
    }
    identities = [(r["scenario"], r["partition"], r["policy"], r["seed"]) for r in episodes]
    assert len(set(identities)) == len(identities) == completed["episodes"]
    assert set(identities) == expected
    by_world = defaultdict(dict)
    monthly_count = 0
    for row in episodes:
        by_world[row["scenario"], row["partition"], row["seed"]][row["policy"]] = row
        months = row["monthly_summaries"]
        assert len(months) == row["horizon"] + 1
        spent = Decimal(0)
        for index, month in enumerate(months):
            assert month["month"] == index
            assert sum(month[c] for c in ("stable", "vulnerable", "disengaged", "withdrawn")) == row["student_count"]
            spent += Decimal(str(month["spending"]))
            assert spent <= Decimal(str(row["budget"]))
            assert Decimal(str(month["remaining_budget"])) == Decimal(str(row["budget"])) - spent
            assert month["appointments_delivered"] == 5 * month["programmes_started"]
            for mentor in month["mentor_utilization"]:
                assert mentor["programmes"] <= mentor["admission_capacity"]
                assert mentor["appointments"] <= mentor["appointment_capacity"]
        assert row["terminal_enrolled"] == months[-1]["enrolled"]
        assert row["programmes"] == row["unique_students_supported"]
        if row["policy"] == "terminal_value":
            assert row["solver_failures"] == row["feasibility_validation_failures"] == 0
            assert all(d["lexicographic_complete"] for d in row["solver_diagnostics"])
            if row["budget"] == 0 or row["effect_strength"] == 0:
                assert row["programmes"] == row["spending"] == 0
        monthly_count += len(months)
    for world in by_world.values():
        assert len({row["initial_state_hash"] for row in world.values()}) == 1
        reference = world["wait"]["monthly_conditions"]
        if world["wait"]["effect_strength"] == 0 or world["wait"]["budget"] == 0:
            assert all(row["monthly_conditions"] == reference for row in world.values())

    summaries = json.loads((output / "summary.json").read_text())
    intervals = 0
    for summary in summaries:
        worlds = [world for (scenario, partition, seed), world in sorted(by_world.items())
                  if scenario == summary["scenario"] and partition == summary["partition"]]
        assert math.isclose(summary["mean_terminal_enrolled"], statistics.mean(
            world[summary["policy"]]["terminal_enrolled"] for world in worlds), abs_tol=1e-12)
        for reference, reported in summary["paired_differences"].items():
            differences = [world[summary["policy"]]["terminal_enrolled"] -
                           world[reference]["terminal_enrolled"] for world in worlds]
            mean = statistics.mean(differences)
            assert math.isclose(mean, reported["mean"], abs_tol=1e-12)
            if len(differences) > 1:
                margin = t.ppf(0.975, len(differences) - 1) * statistics.stdev(differences) / math.sqrt(len(differences))
                assert math.isclose(mean - margin, reported["ci95_low"], abs_tol=1e-12)
                assert math.isclose(mean + margin, reported["ci95_high"], abs_tol=1e-12)
            intervals += 1

    with (output / "solver_diagnostics.csv").open() as source:
        diagnostics = list(csv.DictReader(source))
    assert len(diagnostics) == sum(row["horizon"] for row in episodes if row["policy"] == "terminal_value")
    with (output / "benefit_by_condition.csv").open() as source:
        benefits = list(csv.DictReader(source))
    assert len(benefits) == 4 * 4 * 12
    wait = np.array(manifest["wait_matrix"])
    programme = next(np.array(matrix) for alpha, matrix in manifest["programme_matrices"].items()
                     if float(alpha) == 1)
    conditions = ("stable", "vulnerable", "disengaged", "withdrawn")
    for row in benefits:
        horizon = int(row["months_remaining"])
        expected = float(row["effect_strength"]) * (programme - wait) @ np.linalg.matrix_power(wait, horizon - 1) @ [1, 1, 1, 0]
        assert math.isclose(float(row["incremental_benefit"]), expected[conditions.index(row["condition"])], abs_tol=1e-12)
    tiny = json.loads((output / "tiny_exact_comparison.json").read_text())
    assert len(tiny) >= 5
    assert all(row["objective_gap"] >= -1e-9 for row in tiny)
    reserve = next(row for row in tiny if row["scenario"] == "reserve_budget")
    assert not reserve["exact_first_action"] and reserve["heuristic_first_action"]

    repo = Path(__file__).resolve().parents[1]
    for filename, digest in manifest["source_code_sha256"].items():
        assert hashlib.sha256((repo / filename).read_bytes()).hexdigest() == digest, filename
    return {"status": "passed", "episodes": len(episodes), "monthly_summaries": monthly_count,
            "paired_intervals_recomputed": intervals, "solver_decisions": len(diagnostics),
            "benefit_values_recomputed": len(benefits), "tiny_scenarios": len(tiny),
            "solver_statuses": dict(Counter(row["status"] for row in diagnostics)),
            "source_hashes_verified": len(manifest["source_code_sha256"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = verify(args.output)
    if args.write:
        (args.output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

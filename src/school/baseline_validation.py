"""Fail visibly on incomplete experiments or inconsistent realized ledgers."""

from collections import Counter
import math


def validate_episode(metrics, trajectory, config):
    """Audit recorded resources and metrics independently of policy decisions."""
    if len(trajectory) != config.horizon:
        raise ValueError("episode did not complete the configured horizon")
    seen = set()
    spending = 0.0
    for month, record in enumerate(trajectory, 1):
        if record["month"] != month:
            raise ValueError("missing or repeated monthly record")
        capacities = {mentor: (admissions, slots) for mentor, admissions, slots in record["mentor_capacities"]}
        usage = Counter()
        for item in record["allocation"]["assignments"]:
            if item["student_id"] in seen or item["sessions"] != 5 or item["completed_sessions"] != 5:
                raise ValueError("duplicate programme or incomplete five-session programme")
            seen.add(item["student_id"])
            usage[item["mentor_id"]] += 1
            spending += item["cost_units"]
        if any(count > capacities[mentor][0] or 5 * count > capacities[mentor][1]
               for mentor, count in usage.items()):
            raise ValueError("mentor resource ledger exceeded")
        if record["remaining_budget"] < 0 or not math.isclose(
            record["remaining_budget"], config.budget - spending, abs_tol=1e-7
        ):
            raise ValueError("budget ledger does not reconcile")
        if len(record["conditions"]) != config.num_students:
            raise ValueError("episode cohort size changed")
    if (
        not math.isclose(metrics["spending"], spending, abs_tol=1e-7)
        or metrics["programmes"] != len(seen)
        or metrics["appointments"] != 5 * len(seen)
        or metrics["unique_students_supported"] != len(seen)
        or metrics["terminal_enrolled"] != metrics["monthly_summaries"][-1]["enrolled"]
    ):
        raise ValueError("episode totals do not equal the monthly resource ledger")


def validate_experiment_grid(episodes, manifest, partitions=None):
    """Use the manifest to detect entire missing policies/worlds, not just unequal pairs."""
    partitions = tuple(partitions or manifest.get("partitions", ("development", "evaluation")))
    expected = {
        (f"effect_{alpha:g}_budget_{budget:g}", partition, policy, seed)
        for alpha, budget in manifest["variations"]
        for partition in partitions
        for policy in manifest["policies"]
        for seed in manifest[partition + "_seeds"]
    }
    actual = Counter((row["scenario"], row["partition"], row["policy"], row["seed"]) for row in episodes)
    duplicates = [key for key, count in actual.items() if count != 1]
    missing = expected - actual.keys()
    unexpected = actual.keys() - expected
    if missing or unexpected or duplicates:
        raise ValueError(
            f"incomplete experiment: {len(missing)} missing, {len(unexpected)} unexpected, "
            f"{len(duplicates)} duplicate episodes; examples: "
            f"{sorted(missing)[:2] or sorted(unexpected)[:2] or duplicates[:2]}"
        )

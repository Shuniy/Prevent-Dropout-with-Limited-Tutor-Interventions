"""World-level summaries and paired confidence intervals.

One seed is one independently generated world. Monthly observations and students
must never be treated as independent replicates in these confidence intervals.
"""

import math

import numpy as np
from scipy.stats import t as student_t


def summarize(values, *, confidence=0.95):
    """Return a sample SD and a Student-t interval for finite world values.

    A single world has a mean, but cannot estimate sampling uncertainty. Empty
    samples are allowed for descriptive exports and have no estimated mean.
    """
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    values = np.asarray(list(values), dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("statistics require a one-dimensional finite sample")
    count = len(values)
    mean = float(np.mean(values)) if count else None
    sd = float(np.std(values, ddof=1)) if count > 1 else None
    margin = (float(student_t.ppf((1 + confidence) / 2, count - 1))
              * sd / math.sqrt(count)) if count > 1 else None
    return {
        "n": count, "mean": mean, "sample_sd": sd,
        "ci95_low": mean - margin if margin is not None else None,
        "ci95_high": mean + margin if margin is not None else None,
        "confidence": confidence,
        "status": "ok" if count > 1 else "insufficient_replicates",
    }


def _index_by_seed(rows, metric, seed_key):
    result = {}
    for row in rows:
        if seed_key not in row or row[seed_key] is None:
            raise ValueError("paired comparisons require an explicit seed for every world")
        seed = row[seed_key]
        if seed in result:
            raise ValueError(f"duplicate paired seed: {seed}")
        if metric not in row or row[metric] is None:
            raise ValueError(f"missing paired metric {metric!r} for seed {seed}")
        value = float(row[metric])
        if not math.isfinite(value):
            raise ValueError("paired metrics must be finite")
        result[seed] = value
    return result


def paired_comparison(rows, reference_rows, metric, *, seed_key="seed", confidence=0.95):
    """Compare two cells using seed-matched differences (cell minus reference).

    The caller selects one policy/information/setting cell per argument. Missing
    or duplicate worlds are errors: silently dropping them breaks the design.
    """
    selected = _index_by_seed(rows, metric, seed_key)
    reference = _index_by_seed(reference_rows, metric, seed_key)
    if not selected or selected.keys() != reference.keys():
        raise ValueError("paired comparisons require equal nonempty seed sets")
    seeds = sorted(selected)
    result = summarize((selected[seed] - reference[seed] for seed in seeds),
                       confidence=confidence)
    if metric == "retention_rate":
        result.update({"mean_difference_pp": 100 * result["mean"],
                       "ci95_low_pp": 100 * result["ci95_low"] if result["ci95_low"] is not None else None,
                       "ci95_high_pp": 100 * result["ci95_high"] if result["ci95_high"] is not None else None})
    return {"metric": metric, "direction": "cell_minus_reference",
            "paired_episodes": len(seeds), "seeds": seeds,
            "cell_mean": float(np.mean([selected[seed] for seed in seeds])),
            "reference_mean": float(np.mean([reference[seed] for seed in seeds])), **result}


paired_differences = paired_comparison

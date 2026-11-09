"""Generate a research report and figures strictly from completed executions.

This module is evaluator-only. Individual truth records are read after episodes
finish and never enter a controller, extractor, belief update, or allocation.
"""

from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
import re
import shutil

import numpy as np
from .provenance import active_directory, read_record, verify_manifest
from .report_artifacts import report_generation


def _json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def _csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return [row for row in csv.DictReader(stream) if row.get("status") != "not_executed"]


def _number(value):
    if value in (None, "", "None", "null"):
        return None
    result = float(value)
    return result if np.isfinite(result) else None


def _fmt(value, digits=4):
    value = _number(value)
    return f"{value:.{digits}f}" if value is not None else "unavailable"


def _mean(rows, key):
    values = [_number(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return float(np.mean(values)) if values else None


def _truthy(value):
    return value is True or value == "True" or value == "1" or value == 1


def _primary(row):
    return _truthy(row.get('primary_cell_valid'))


def _write_csv(path, rows):
    if not rows:
        path.write_text("status\nnot_executed\n", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _table(rows, columns):
    if not rows:
        return "This comparison was not executed."
    headers = [label for _, label in columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key)
            if value in (None, "", "None"):
                value = "unavailable"
            elif isinstance(value, float):
                value = _fmt(value)
            values.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _comparison_table(rows):
    prepared = []
    for row in rows:
        retention = row.get("metric") == "retention_rate"
        scale = 100 if retention else 1
        prepared.append({"contrast": row.get("setting", row.get("mode", "")),
            "metric": row.get("metric"), "n": row.get("paired_episodes", row.get("n")),
            "point": _fmt(row.get("reference_mean")), "robust": _fmt(row.get("cell_mean")),
            "difference": _fmt(scale * _number(row["mean"])) if _number(row.get("mean")) is not None else "unavailable",
            "ci": "[" + ", ".join(_fmt(scale * _number(row[key])) if _number(row.get(key)) is not None
                                     else "unavailable" for key in ("ci95_low", "ci95_high")) + "]",
            "units": "percentage points" if retention else "metric units"})
    return _table(prepared, (("contrast", "Contrast/setting"), ("metric", "Metric"), ("n", "Paired worlds"),
        ("point", "Reference mean"), ("robust", "Cell mean"), ("difference", "Cell − reference"),
        ("ci", "95% paired CI"), ("units", "Difference units")))


def _load_gzip(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _episode_directories(output, episodes, primary_seeds=5):
    candidates = []
    active_paths = {row.get('trace_path') for row in episodes if _primary(row)}
    for path in sorted((output / "episodes").glob("*/summary.json")):
        summary = _json(path)
        if summary.get("trace_path") in active_paths:
            candidates.append((summary, (output / summary["trace_path"]).parent))
    seeds = sorted({row["seed"] for row, _ in candidates})[:primary_seeds]
    return [(row, folder) for row, folder in candidates if row["seed"] in seeds]


def _individual_records(directories, name):
    rows = []
    for summary, folder in directories:
        path = folder / f"{name}.json.gz"
        if path.exists():
            labels = {key: summary[key] for key in ("policy", "mode", "seed", "phase", "setting")}
            rows.extend({**labels, **row} for row in _load_gzip(path)
                        if not _truthy(row.get("terminal_diagnostic")))
    return rows


def _extraction_rows(extraction):
    rows = []
    for method in ("gold_reference", "exact_rule", "real_llm"):
        payload = extraction.get(method, {})
        metrics = payload.get("metrics", {})
        for field, counts in metrics.get("per_field", {}).items():
            rows.append({"method": method, "scope": "field", "field": field,
                         "status": payload.get("status"), **counts})
        for scope in ("micro", "macro_over_fields", "unknown_values"):
            if scope in metrics:
                rows.append({"method": method, "scope": scope, "field": "all",
                             "status": payload.get("status"), **metrics[scope]})
        for field, counts in metrics.get("special_semantics", {}).items():
            rows.append({"method": method, "scope": "special_semantics", "field": field,
                         "status": payload.get("status"), **counts})
        if metrics:
            rows.append({"method": method, "scope": "diagnostics", "field": "all",
                "status": payload.get("status"), **metrics.get("diagnostics", {}),
                "schema_valid_rate_all_eligible": metrics.get("schema_valid_rate_all_eligible"),
                "failure_rate_all_eligible": metrics.get("failure_rate_all_eligible")})
    return rows


def _figures(output, episodes, comparisons, extraction_rows, beliefs, risks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    destination = output / "figures"
    destination.mkdir(exist_ok=True)
    generated = []

    def save(name, draw, title):
        fig, axis = plt.subplots(figsize=(7.8, 4.5))
        available = draw(axis)
        if available is False:
            axis.text(.5, .5, "No executed data for this analysis", ha="center", va="center",
                      transform=axis.transAxes)
            axis.set_xticks([])
            axis.set_yticks([])
        status = read_record(output/'aggregation_status.json')
        axis.set_title(title if status['primary_complete'] else 'INCOMPLETE / EXPLORATORY\n'+title)
        fig.tight_layout()
        fig.savefig(destination / f"{name}.png", dpi=160)
        plt.close(fig)
        generated.append(name)

    def extraction_plot(axis):
        rows = [row for row in extraction_rows if row["scope"] == "micro" and row.get("f1") is not None]
        if not rows:
            return False
        axis.bar([row["method"] for row in rows], [row["f1"] for row in rows], color=("#8197a5", "#19798e", "#bd7943")[:len(rows)])
        axis.set(ylabel="Post-validation exact-fact micro F1", ylim=(0, 1.05))
    save("extraction_performance", extraction_plot, "Frozen controlled-grammar extraction benchmark")

    def belief_plot(axis):
        if not beliefs:
            return False
        for policy in sorted({row["policy"] for row in beliefs}):
            selected = [row for row in beliefs if row["policy"] == policy]
            probabilities = np.asarray([[row[f"p_{state}"] for state in
                ("stable", "vulnerable", "disengaged", "withdrawn")] for row in selected])
            confidence = probabilities.max(axis=1)
            correct = np.asarray([row["accuracy"] for row in selected])
            xs, ys = [], []
            for index in range(10):
                mask = np.minimum(9, (confidence * 10).astype(int)) == index
                if mask.any():
                    xs.append(float(confidence[mask].mean()))
                    ys.append(float(correct[mask].mean()))
            axis.plot(xs, ys, marker="o", label=policy)
        axis.plot([0, 1], [0, 1], "--", color="gray", linewidth=1)
        axis.set(xlabel="Mean maximum belief probability", ylabel="Observed MAP accuracy", xlim=(0, 1), ylim=(0, 1))
        axis.legend()
    save("belief_calibration", belief_plot, "Belief confidence reliability: first five primary worlds")

    def risk_plot(axis):
        if not risks:
            return False
        for policy in sorted({row["policy"] for row in risks}):
            selected = [row for row in risks if row["policy"] == policy]
            xs, ys = [], []
            for index in range(10):
                members = [row for row in selected if row["calibration_bin"] == index]
                if members:
                    xs.append(_mean(members, "prediction"))
                    ys.append(_mean(members, "reference_probability"))
            axis.plot(xs, ys, marker="o", label=policy)
        axis.plot([0, 1], [0, 1], "--", color="gray", linewidth=1)
        axis.set(xlabel="Predicted WAIT withdrawal probability", ylabel="True-state WAIT reference probability", xlim=(0, 1), ylim=(0, 1))
        axis.legend()
    save("risk_calibration", risk_plot, "Model-reference risk reliability: first five primary worlds")

    snapshots = _csv(output / "snapshot_assignment_comparison.csv")
    def assignment_plot(axis):
        if not snapshots:
            return False
        modes = sorted({row["mode"] for row in snapshots})
        axis.bar(modes, [_mean([r for r in snapshots if r["mode"] == mode], "selection_disagreement_rate")
                         for mode in modes], color="#19798e")
        axis.set(ylabel="Student selection symmetric difference / cohort", xlabel="Information mode at cutoff 1")
    save("allocation_disagreement", assignment_plot, "Point versus robust assignments on identical snapshots")

    def information_plot(axis):
        selected = [row for row in episodes if (row["phase"] == "secondary" and row["setting"] == "information")
                    or _primary(row)]
        seeds = {r["seed"] for r in selected if r["phase"] == "secondary"}
        selected = [r for r in selected if r["policy"] == "FairPoint" and r["seed"] in seeds]
        if not selected:
            return False
        modes = sorted({r["mode"] for r in selected})
        axis.bar(modes, [100 * _mean([r for r in selected if r["mode"] == mode], "retention_rate") for mode in modes], color="#19798e")
        axis.set(ylabel="Mean terminal retention (%)", xlabel="Information mode, matched secondary world seeds")
    save("retention_by_information_mode", information_plot, "FairPoint retention by information mode")

    def primary_plot(axis):
        selected = [r for r in episodes if _primary(r)]
        indexed = {(r["policy"], r["seed"]): r for r in selected}
        seeds = sorted({r["seed"] for r in selected})
        if not seeds:
            return False
        for seed in seeds:
            if ("FairPoint", seed) in indexed and ("FairRobust", seed) in indexed:
                axis.plot([0, 1], [100 * float(indexed[(p, seed)]["retention_rate"])
                                   for p in ("FairPoint", "FairRobust")], color="#c4cbd0", alpha=.65)
        policies = ('FairPoint', 'FairRobust')
        available = [(i, _mean([r for r in selected if r['policy'] == p], 'retention_rate'))
                     for i, p in enumerate(policies)]
        available = [(i, value) for i, value in available if value is not None]
        axis.scatter([i for i, _ in available], [100*value for _, value in available], color="#19798e", s=70, zorder=4)
        axis.set(xticks=[0, 1], xticklabels=policies, ylabel="Terminal retention (%)")
    save("point_vs_robust", primary_plot, "Primary paired worlds: raw terminal retention")

    def tradeoff_plot(axis):
        selected = [r for r in episodes if _primary(r)]
        if not selected:
            return False
        for policy, marker in (("FairPoint", "o"), ("FairRobust", "^")):
            members = [r for r in selected if r["policy"] == policy]
            axis.scatter([float(r["normalized_shortfall"]) for r in members],
                         [100 * float(r["retention_rate"]) for r in members], alpha=.55, marker=marker, label=policy)
        axis.set(xlabel="Summed normalized frozen-cell access shortfall (lower is better)", ylabel="Terminal retention (%)")
        axis.legend()
    save("fairness_retention_tradeoff", tradeoff_plot, "Primary world-level retention and minimum-access shortfall")

    def missing_plot(axis):
        selected = [r for r in comparisons if r.get("setting", "").startswith("missingness_") and r["metric"] == "retention_rate"]
        if not selected:
            return False
        selected.sort(key=lambda r: float(r["setting"].split("_", 1)[1]))
        x = [float(r["setting"].split("_", 1)[1]) for r in selected]
        y = np.asarray([100 * float(r["mean"]) for r in selected])
        if all(_number(r.get("ci95_low")) is not None for r in selected):
            low = np.asarray([100 * float(r["ci95_low"]) for r in selected])
            high = np.asarray([100 * float(r["ci95_high"]) for r in selected])
            axis.errorbar(x, y, yerr=[np.maximum(0, y-low), np.maximum(0, high-y)], marker="o", capsize=4)
        else:
            axis.plot(x, y, marker="o")
        axis.axhline(0, color="gray", linestyle="--")
        axis.set(xlabel="Note omission probability (additional to observation missingness)", ylabel="FairRobust − FairPoint retention (percentage points)")
    save("missingness_sensitivity", missing_plot, "Exploratory paired missingness sensitivity")

    access = _csv(output / "group_access.csv")
    def group_plot(axis):
        selected = [r for r in access if _primary(r) and _number(r.get("access_rate")) is not None]
        if not selected:
            return False
        groups = sorted({r["group"] for r in selected})
        positions = np.arange(len(groups))
        for index, policy in enumerate(("FairPoint", "FairRobust")):
            values = [_mean([r for r in selected if r["policy"] == policy and r["group"] == group], "access_rate") for group in groups]
            values = [np.nan if value is None else value for value in values]
            axis.bar(positions + (index-.5)*.35, values, width=.35, label=policy)
        axis.set(xticks=positions, xticklabels=groups, xlabel="Authorized disadvantage proxy group",
                 ylabel="Mean nonempty frozen-cell access rate")
        axis.legend()
    save("group_access_comparison", group_plot, "Descriptive access: equal weighting of nonempty cell-world rows")
    return generated


def _case_excerpt(trace, sid, cutoff):
    from ..intervention.observation_extractor import gold_payload
    from ..observations.observable_events import Note

    snapshots = [row for row in trace["snapshots"] if row["month"] == cutoff]
    snapshot = snapshots[0] if snapshots else {}
    decision = next((row for row in trace["decisions"] if row["month"] == cutoff), {})
    truth = {row["month"]: dict(row["conditions"]) for row in trace["truth_evaluator_only"]}
    notes = []
    for record in trace["notes"]:
        if record["student_id"] != sid or record["event_month"] >= cutoff:
            continue
        values = {**record, "source_event_ids": tuple(record["source_event_ids"])}
        notes.append({**record, "available_at_decision": record["available_from_month"] <= cutoff,
                      "note_supported_gold_reference": gold_payload(Note(**values))})
    return {"student_id": sid, "decision_cutoff": cutoff,
        "true_condition_evaluator_only_at_cutoff": truth.get(cutoff-1, {}).get(sid),
        "observable_events": [r for r in trace["observations"] if r["student_id"] == sid and r["event_month"] < cutoff],
        "notes_and_note_supported_gold": notes,
        "extracted_batches": [r for r in trace["extracted"] if r["student_id"] == sid and r["as_of_month"] <= cutoff],
        "student_decision_input": next((r for r in snapshot.get("students", []) if r["student_id"] == sid), None),
        "estimated_state": next((r for r in snapshot.get("estimated_student_states", []) if r["student_id"] == sid), None),
        "risk_estimate": next((r for r in trace["risk_estimates"] if r["student_id"] == sid and r["as_of_month"] == cutoff), None),
        "estimated_incremental_benefit": decision.get("benefits", {}).get(sid),
        "executed_assignment": [r for r in decision.get("allocation", {}).get("assignments", []) if r["student_id"] == sid],
        "allocation_status": decision.get("allocation", {}).get("status"),
        "projected_fairness_shortfall": decision.get("allocation", {}).get("projected_fairness_shortfall"),
        "realized_fairness_shortfall": decision.get("allocation", {}).get("realized_fairness_shortfall"),
        "next_condition_evaluator_only": truth.get(cutoff, {}).get(sid),
        "terminal_condition_evaluator_only": truth[max(truth)].get(sid),
        "true_condition_trajectory_evaluator_only": [{"month": month, "condition": row.get(sid)} for month, row in sorted(truth.items())],
        "interpretation": "Observed trace only. Later withdrawal does not establish that support was unnecessary or causally ineffective."}


def failure_analysis(output, episodes, directories, beliefs, *, source=None):
    """Select actual adverse examples deterministically, without inventing cases."""
    from ..utils.keyed_random import keyed_uniform
    cases, omissions = [], []
    source = output if source is None else source
    primary = [r for r in episodes if _primary(r)]
    indexed = {(r["policy"], str(r["seed"])): r for r in primary}
    negative = []
    for row in primary:
        if row["policy"] != "FairRobust":
            continue
        reference = indexed.get(("FairPoint", str(row["seed"])))
        if reference:
            difference = float(row["retention_rate"]) - float(reference["retention_rate"])
            if difference < 0:
                negative.append((difference, str(row["seed"]), row, reference))
    selected_directories = list(directories)
    if negative:
        difference, seed, robust, point = min(negative, key=lambda r: (r[0], r[1]))
        traces = [_load_gzip(source / row["trace_path"]) for row in (point, robust)]
        cutoff, sid = 1, None
        for a, b in zip(traces[0]["decisions"], traces[1]["decisions"]):
            changed = sorted(set(a["admitted_ids"]) ^ set(b["admitted_ids"]))
            if changed:
                cutoff, sid = a["month"], changed[0]
                break
        if sid is None:
            sid = sorted(dict(traces[0]["truth_evaluator_only"][0]["conditions"]))[0]
        cases.append({"case_type": "largest_negative_primary_robust_difference", "seed": seed,
            "retention_difference_pp": 100*difference, "selection_rule": "minimum paired primary retention difference; seed breaks ties",
            "point_trace": _case_excerpt(traces[0], sid, cutoff), "robust_trace": _case_excerpt(traces[1], sid, cutoff)})
        selected_directories += [(row, (source / row["trace_path"]).parent) for row in (point, robust)]
    else:
        omissions.append("No negative primary robust-minus-point retention difference was observed.")
    if beliefs:
        largest = min(beliefs, key=lambda r: (-float(r["brier"]), str(r["seed"]), r["policy"], r["cutoff"], r["student_id"]))
        folder = next(folder for row, folder in directories if str(row["seed"]) == str(largest["seed"]) and row["policy"] == largest["policy"])
        cases.append({"case_type": "largest_belief_error_in_declared_five_world_diagnostic_sample",
            "seed": largest["seed"], "policy": largest["policy"], "multiclass_brier": largest["brier"],
            "selection_rule": "maximum summed four-class Brier in first five primary world seeds",
            "trace": _case_excerpt(_load_gzip(folder / "trace.json.gz"), largest["student_id"], largest["cutoff"])})
    found = set()
    for summary, folder in sorted(selected_directories, key=lambda r: (str(r[0]["seed"]), r[0]["policy"])):
        if {"note_contradiction", "note_omission", "fairness_shortfall"} <= found:
            break
        trace = _load_gzip(folder / "trace.json.gz")
        for note in trace["notes"]:
            quality = trace.get("note_quality_by_student", {}).get(note["student_id"], trace.get("note_quality", {}))
            omitted = keyed_uniform(trace["configuration"]["seed"], note["student_id"],
                note["event_month"], "note:omission") < quality.get("omission_probability", 0)
            category = ("note_contradiction" if "Reports about participation conflict and remain unresolved." in note["text"]
                        else "note_omission" if omitted else None)
            if category and category not in found and note["available_from_month"] <= trace["configuration"]["horizon"]:
                found.add(category)
                cases.append({"case_type": category, "seed": summary["seed"], "policy": summary["policy"],
                    "selection_rule": "first actual qualifying note in declared diagnostic sample, ordered by seed/policy",
                    "trace": _case_excerpt(trace, note["student_id"], note["available_from_month"])})
        if "fairness_shortfall" not in found:
            for decision in trace["decisions"]:
                allocation = decision["allocation"]
                if (allocation.get("projected_fairness_shortfall") or 0) > 0:
                    snapshot = next(r for r in trace["snapshots"] if r["month"] == decision["month"])
                    sid = next((r["student_id"] for r in snapshot["students"] if r["enrolled"] and not r["programme_months"]), None)
                    if sid:
                        found.add("fairness_shortfall")
                        cases.append({"case_type": "fairness_shortfall", "seed": summary["seed"], "policy": summary["policy"],
                            "selection_rule": "first actual positive projected shortfall in declared diagnostic sample",
                            "observed_status": allocation["status"],
                            "interpretation": "Positive coverage slack, not a hard-resource violation or a proof of strict-model infeasibility.",
                            "trace": _case_excerpt(trace, sid, decision["month"])})
                        break
    for category in sorted({"note_contradiction", "note_omission", "fairness_shortfall"} - found):
        omissions.append(f"No qualifying {category} trace was observed in the declared diagnostic sample.")
    path = output / "failure_cases.jsonl"
    path.write_text("".join(json.dumps(case, allow_nan=False) + "\n" for case in cases), encoding="utf-8")
    (output / "failure_case_selection.json").write_text(json.dumps({"diagnostic_seed_limit": 5,
        "negative_primary_search": "all completed primary pairs", "selected_cases": len(cases),
        "unobserved_categories": omissions}, indent=2), encoding="utf-8")
    return cases, omissions


def _render_report(source, output):
    """Render only from the freshly validated aggregate in private staging."""
    episodes = _csv(output / "episode_results.csv")
    comparisons = _csv(output / "all_policy_comparisons.csv")
    extraction = _json(output/'extraction/metrics.json', {})
    extraction_rows = _extraction_rows(extraction)
    _write_csv(output / "extraction_metrics.csv", extraction_rows)
    directories = _episode_directories(source, episodes)
    beliefs = _individual_records(directories, "belief_records")
    risks = _individual_records(directories, "risk_records")
    figures = _figures(output, episodes, comparisons, extraction_rows, beliefs, risks)
    cases, missing_cases = failure_analysis(output, episodes, directories, beliefs, source=source)
    manifest_path = source / "configuration_manifest.json"
    manifest = _json(manifest_path, {})
    configuration = manifest.get("configuration", {})
    scenario = configuration.get("scenario", {})
    evaluation = configuration.get("evaluation", {})
    primary = [r for r in comparisons if r.get("phase") == "evaluation" and r.get("setting") == "primary"]
    primary = [r for r in primary if r.get('mode') == 'd_matched']
    status = read_record(output/'aggregation_status.json')
    complete = status['primary_complete']
    completion_text = (f"**{'COMPLETE PRIMARY EVALUATION' if complete else 'INCOMPLETE / EXPLORATORY'}**. "
        f"Validated primary episodes: {status['actual_primary_episodes']} / {status['expected_primary_episodes']}; "
        f"paired seeds: {status['completed_paired_seeds']} / {status['expected_paired_seeds']}. "
        f"Evaluation status: {status['evaluation_status']}. "
        f"Missing cells: {json.dumps(status['missing_primary_cells'])}. "
        f"Failed cells: {json.dumps(status['failed_primary_cells'])}. "
        f"Invalid cells: {json.dumps(status['invalid_primary_cells'])}.")
    retention = next((r for r in primary if r["metric"] == "retention_rate"), None)
    if retention and complete:
        low, high = _number(retention.get("ci95_low")), _number(retention.get("ci95_high"))
        estimate = 100 * float(retention["mean"])
        interpretation = ("The interval favors FairRobust on simulated retention." if low is not None and low > 0 else
            "The interval favors FairPoint on simulated retention." if high is not None and high < 0 else
            "The interval includes zero; these executions do not establish a retention difference or equivalence.")
        primary_text = (f"The prespecified primary estimate is **{estimate:+.3f} percentage points** "
            f"(FairRobust minus FairPoint), paired 95% CI [{_fmt(100*low if low is not None else None, 3)}, "
            f"{_fmt(100*high if high is not None else None, 3)}], n={retention.get('paired_episodes', retention.get('n'))} worlds. "
            f"Raw mean retention: FairPoint {_fmt(retention.get('reference_mean'))}; FairRobust {_fmt(retention.get('cell_mean'))}. " + interpretation)
    else:
        primary_text = (completion_text + '\n\nStatistics below are exploratory and conditional on the completed subset. '
            'The preregistered primary result is unavailable; subset confidence intervals do not establish primary completion.')
    primary_episodes = [r for r in episodes if _primary(r)]
    information = _csv(output / "information_mode_comparison.csv")
    sensitivity = [r for r in comparisons if r.get("phase") == "secondary" and r.get("setting", "").split("_")[0] in ("budget", "effect", "uncertainty", "missingness")]
    sensitivity_retention = [r for r in sensitivity if r["metric"] == "retention_rate"]
    live = [r for r in episodes if r.get("phase") == "live"]
    summary_rows = []
    for policy in sorted({r["policy"] for r in primary_episodes}):
        members = [r for r in primary_episodes if r["policy"] == policy]
        summary_rows.append({"policy": policy, "worlds": len(members), **{key: _mean(members, key) for key in
            ("belief_brier", "belief_nll", "risk_expected_brier", "risk_expected_log_loss", "risk_probability_mse",
             "programmes", "spending", "budget_utilization", "mentor_admission_utilization",
             "appointment_slot_utilization", "solver_runtime_seconds", "solver_incomplete_count", "solver_fallback_count")}})
    extraction_summary = []
    for method in ("gold_reference", "exact_rule", "real_llm"):
        payload = extraction.get(method, {})
        metrics = payload.get("metrics", {})
        extraction_summary.append({"method": method, "status": payload.get("status", "not_executed"),
            "micro_f1": metrics.get("micro", {}).get("f1"), "macro_f1": metrics.get("macro_over_fields", {}).get("f1"),
            "schema_valid": metrics.get("schema_valid_rate_all_eligible"),
            "quarantined": metrics.get("diagnostics", {}).get("failed_or_quarantined_notes"),
            "unsupported_raw": metrics.get("diagnostics", {}).get("raw_unsupported_observations")})
    trace_summary = [{"case": case["case_type"], "seed": case.get("seed"), "policy": case.get("policy", "paired"),
                      "rule": case["selection_rule"]} for case in cases]
    generated = set(figures)
    def figure(name, caption):
        return f"![{caption}](figures/{name}.png)\n\n{caption}" if name in generated else ""
    report = f"""# Step 6 research evaluation results

## 1. Research questions and scope

{primary_text}

The study asks how incomplete, delayed, misleading and contradictory observations propagate through beliefs, WAIT-continuation risk, allocation and simulated outcomes, and whether finite-scenario robust fairness improves the retention/access trade-off. The primary experiment uses D-matched exact note-supported facts. It does not estimate the effect of LLM extraction error. Real LLM behavior is separately benchmarked and examined in sparse closed-loop diagnostics.

## 2. Source population and simulator assumptions

The cohort is a fixed enrolled prefix of the existing synthetic/semi-synthetic source data. Seeds change transitions and information mechanisms, not the population. Executable scenario: {json.dumps(scenario, sort_keys=True)}.

Four conditions, WAIT/programme transition matrices, intervention alpha, enrollment registry, observation likelihoods and group-dependent note quality are declared assumptions. Source course failure is not observed school dropout. All support needs share the declared programme transition matrix. No empirical causal or school-withdrawal calibration is claimed.

## 3. Frozen design, replication and execution

Development seeds: {evaluation.get('development_seeds', 'unavailable')}. Frozen primary evaluation seeds: {evaluation.get('evaluation_seeds', 'unavailable')}. Completed episode rows: {len(episodes)}; primary rows: {len(primary_episodes)}; sparse real-LLM rows: {len(live)}. Source/configuration hashes are in [configuration_manifest.json](configuration_manifest.json). The frozen protocol is [available here](research_evaluation_protocol_frozen.md).

One episode seed is one independent simulation replicate. Intervals use paired world differences with Student-t critical values and sample SD (ddof=1). Students and months are not independent replicates. Secondary contrasts are exploratory without multiplicity adjustment. These intervals quantify simulation Monte Carlo uncertainty; they do not cover source-population or causal-model uncertainty.

## 4. Allocation methods and uncertainty assumptions

FairPoint and FairRobust share the original candidate generation, five-appointment programmes, exact episode budget, compatibility, one-programme rule, announced capacity and rolling-window fairness cohorts. Objectives are lexicographic: normalized access shortfall, nominal or worst-scenario aggregate benefit, exact cost, canonical assignment bits. Only current admissions execute.

FairRobust constrains continuous eta below each complete scenario's sum of assignment benefits. The finite set includes nominal and separate optimistic/pessimistic shifts for fresh/documented and missing/stale subsets, at most five scenarios. Mixture parameters: {json.dumps(configuration.get('uncertainty', {}), sort_keys=True)}. The set is a synthetic sensitivity assumption, not a calibrated confidence region or a guarantee that truth lies within it. Risk and treatment benefit remain distinct quantities. Both planners are rolling heuristics, not exact POMDP solvers.

## 5. Independent extraction benchmark

{_table(extraction_summary, (('method','Comparator'),('status','Execution'),('micro_f1','Micro F1'),('macro_f1','Macro field F1'),('schema_valid','Raw schema-valid / eligible'),('quarantined','Failed/quarantined notes'),('unsupported_raw','Raw unsupported observations')))}

The benchmark uses newly declared synthetic note identities and compositions with independently declared semantic gold. Canonical vocabulary and phrase semantics overlap development and the prompt. It has no independent human annotation and does not establish generalization to unrestricted mentor prose. Failed/quarantined outputs remain misses; no gold substitution occurs. Full field/component TP/FP/FN and pre-validation diagnostics are in [extraction_metrics.csv](extraction_metrics.csv), with raw inference records and model digest under [extraction/](extraction/).

{figure('extraction_performance', 'Exact-fact extraction on the executed controlled-grammar benchmark; no population confidence interval is implied.')}

## 6. Belief quality and missing information

{_table(summary_rows, (('policy','Policy'),('worlds','Primary worlds'),('belief_brier','Four-class Brier'),('belief_nll','Clipped NLL')))}

Brier scores sum errors over all four classes (range 0–2). Primary means cover decision cutoffs only; terminal diagnostics are exported separately. [belief_metrics.csv](belief_metrics.csv) records accuracy, confusion, entropy, missingness and freshness by cutoff and authorized group. Reliability figures use individual records from the first five completed primary world seeds and are descriptive; trajectory-dependent rows are not independent trials.

{figure('belief_calibration', 'Maximum-probability confidence versus actual MAP accuracy, excluding terminal diagnostics.')}

## 7. WAIT-continuation risk quality

{_table(summary_rows, (('policy','Policy'),('risk_expected_brier','Expected Bernoulli Brier'),('risk_expected_log_loss','Expected Bernoulli log loss'),('risk_probability_mse','Probability MSE')))}

The reference target is terminal withdrawal under WAIT from the evaluator's current true condition and declared reference matrix. Scores use its conditional probability, not realized treated endpoints. Fractional reference probabilities are not observed dropout labels; no empirical AUC or real-world risk validation is claimed. See [risk_metrics.csv](risk_metrics.csv).

{figure('risk_calibration', 'Binned predicted risk versus conditional true-state WAIT reference probability in the declared five-world diagnostic sample.')}

## 8. Extraction, estimation and assignment propagation

[snapshot_assignment_comparison.csv](snapshot_assignment_comparison.csv) compares fresh point/robust planners on exactly the same first-cutoff input and feasible set. [extraction_snapshot_comparison.csv](extraction_snapshot_comparison.csv) compares matched gold/LLM notes for belief, risk, benefit, eligibility and mentor assignment changes; it is available only when that live stage ran. Rank diagnostics use average ties. Divergent closed-loop trajectories are not presented as identical later snapshots.

{figure('allocation_disagreement', 'Selection disagreement counts the student symmetric difference divided by cohort size; mentor overlap is exported separately.')}

{figure('retention_by_information_mode', 'FairPoint held fixed across information modes, restricted to the same secondary seeds. Oracle is an upper-information diagnostic, not an ordinary-policy comparator.')}

{_comparison_table([r for r in information if r.get('metric') == 'retention_rate'])}

## 9. Primary effectiveness and equity results

{primary_text}

{_comparison_table(primary)}

Fairness outcomes must be read alongside retention. Lower normalized shortfall/access gap/waiting disparity and higher worst-cell access are preferable. An interval containing zero does not demonstrate no harm or equivalence. Access cohorts freeze within each four-month trajectory window; the same reported group/stratum label can contain different students after observations or actions diverge. Membership identities are exported, so cross-mode access differences are not silently treated as a fixed-denominator comparison. A retention increase alone does not establish a superior effectiveness/equity trade-off.

{figure('point_vs_robust', 'Each line is one paired world; points show policy means. All completed primary worlds are included regardless of sign.')}

{figure('fairness_retention_tradeoff', 'World-level retention versus access shortfall, without implying that cells or students are independent replicates.')}

{figure('group_access_comparison', 'Descriptive group access averages nonempty frozen-cell/world rows equally; paired fairness contrasts above are the primary inferential summaries.')}

## 10. Sensitivity, ablations and operational burden

{_comparison_table(sensitivity_retention)}

All sensitivity fairness metrics are retained in [all_policy_comparisons.csv](all_policy_comparisons.csv). [ablation_results.csv](ablation_results.csv) contains zero-radius uncertainty and resource-only fairness controls. Zero treatment effect checks use exact keyed-draw truth equality, rather than a claim from an interval around zero. Missingness changes note omission in addition to the fixed observation model. Budget, effect and radius sweeps use their frozen settings and secondary seed subset.

{figure('missingness_sensitivity', 'Paired exploratory retention differences with world-level 95% intervals; these sweeps are not multiplicity-adjusted confirmatory tests.')}

{_table(summary_rows, (('policy','Policy'),('programmes','Programmes/world'),('spending','Spending/world'),('budget_utilization','Budget utilization'),('mentor_admission_utilization','Admission capacity utilization'),('appointment_slot_utilization','Appointment capacity utilization'),('solver_runtime_seconds','Solver seconds/world'),('solver_incomplete_count','Incomplete stages/world'),('solver_fallback_count','Fallbacks/world')))}

Solver status, timings and constraint checks are retained in [solver_diagnostics.csv](solver_diagnostics.csv); workloads and exact delivery remain in each episode trace. Runtime is descriptive and machine-dependent. Sparse C/D runs use one rotating note per month and only the frozen live seeds; they cannot replace a full-cohort multi-seed LLM evaluation.

## 11. Observed failure cases

{_table(trace_summary, (('case','Observed case'),('seed','Seed'),('policy','Policy'),('rule','Deterministic selection rule')))}

Full selected traces are in [failure_cases.jsonl](failure_cases.jsonl). Each separates evaluator truth, observable events, note text, note-supported reference facts, accepted extraction, belief, risk, estimated benefit, assignment and subsequent outcome. Note-supported reference facts are reconstructed with the existing controlled-grammar adapter for explanation, not fed back to execution. Largest belief-error and note cases use the declared first-five-world diagnostic sample; adverse primary retention searches all completed primary pairs. Positive coverage slack is not a hard-resource violation. Later withdrawal is not evidence that an intervention was unnecessary.

{' '.join(missing_cases) if missing_cases else 'Every declared diagnostic category had an actual qualifying trace.'}

## 12. Validity, reproducibility and acceptance limits

No claim here establishes observed school-dropout prediction, causal programme efficacy, fairness outcome parity or robust-policy superiority outside the declared simulator. Group information-quality differences, transition dynamics and uncertainty radii are assumptions. The fixed prefix excludes source-cohort sampling uncertainty; controlled language favors exact-rule extraction. Oracle consumes present state only, not future draws. Post-action observations belong to each policy's own trajectory. Secondary and subgroup estimates have few worlds and no multiplicity correction.

Real inference is distinguished from deterministic cache replay; temperature zero does not guarantee bitwise model determinism. See [development_gate.json](development_gate.json), [primary_complete.json](primary_complete.json), [live_runtime.json](live_runtime.json), the frozen manifest, per-episode summaries and compressed traces for completed stages and remaining acceptance items. An unavailable table or plot is explicitly labeled and does not count as completed evidence.
"""
    # Preserve the user's requested twelve-section paper structure while keeping
    # extraction, state, risk, action and outcome results separately inspectable.
    bodies = re.split(r"\n## \d+\. [^\n]+\n", report)[1:]
    results = "\n\n".join(f"### 7.{index}. {title}\n\n{bodies[position].strip()}"
        for index, (position, title) in enumerate(((4, "Extraction benchmark"),
            (5, "Belief quality"), (6, "Risk quality"), (7, "Allocation propagation and information modes"),
            (8, "Primary retention and fairness"), (9, "Sensitivity and operational burden")), 1))
    ablations = _csv(output / "ablation_results.csv")
    report = f"""# Step 6 research evaluation results

## 1. Introduction

{primary_text}

This evaluation separates language extraction, state estimation, risk prediction, feasible allocation and simulated outcomes. It reuses the implemented school environment and allocation pipeline.

## 2. Research questions and hypotheses

How do incomplete, delayed, misleading and contradictory observations propagate to beliefs, risk, assignments, retention and comparable-need access? Does the finite-scenario FairRobust policy improve the effectiveness/equity trade-off relative to FairPoint? Which differences reflect missing observations, note corruption, extraction, filtering and optimization? The directional hypothesis allows robustness to help under group-dependent information errors; zero or adverse effects remain reportable findings. No empirical algorithmic novelty or real-world causal claim was prespecified.

## 3. Data and simulator

{bodies[1].strip()}

## 4. Allocation methods

{bodies[3].strip()}

## 5. Language and estimation pipeline

The existing pipeline renders authorized observable events into dated notes, validates exact evidence spans and structured assertions, then replays source-time categorical Bayes updates. Administrative enrollment remains explicit. Delayed evidence may update a current belief but does not rewrite previous decisions. Unknown, negated, conflicting and absent observations remain distinguishable; unresolved events do not become condition labels or treatment effects. The risk estimator propagates the belief under WAIT and the allocator separately computes incremental programme benefit. Unsupported or quarantined extraction supplies missing evidence and never an invented gold replacement.

The primary D-matched comparison uses exact note-supported facts from the corrupted channel, so it isolates the uncertainty/allocation study without claiming LLM extraction effects. Actual Qwen outputs are measured in the independent extraction benchmark and matched sparse C/D propagation controls. Those controls have fewer independent worlds and a different monitoring density.

## 6. Experimental design

{bodies[2].strip()}

## 7. Results

{results}

## 8. Ablation studies

{_comparison_table(ablations)}

Zero radius deliberately removes the uncertainty perturbation while retaining the same robust implementation and feasibility constraints. ResourceOnlyPoint removes the fairness objective and is compared on matched world seeds. These are exploratory controls with the frozen secondary sample. Their complete outcome metrics are retained, including unfavorable changes. Exact null-effect trajectory checks are documented in the development gate and held-out effect sweep.

## 9. Failure analysis

{bodies[10].strip()}

## 10. Limitations

{bodies[11].strip()}

## 11. Research contribution assessment

The implemented contribution is a reproducible, auditable evaluation of an existing language-to-belief-to-allocation system, with a small explicitly assumed robust belief-scenario extension, paired simulation inference and evaluator-only trace diagnostics. Exact-rule extraction is a substantive comparator in this controlled grammar. The evidence does not establish a new general-purpose extraction method, a learned dropout model, an optimal POMDP policy or real-world programme efficacy. Whether the robust extension is useful must be judged from its reported retention and equity estimates together, rather than its name or a favorable isolated example.

## 12. Conclusion

{primary_text}

The observed direction and uncertainty apply to the frozen synthetic setting. Extraction accuracy, state/risk diagnostics, access outcomes, operational cost and negative cases remain part of the result. A positive retention estimate alone does not establish a superior fairness trade-off, and an interval spanning zero is not equivalence.
"""
    path = output / "research_results.md"
    report = report.replace('# Step 6 research evaluation results\n',
        '# Step 6 research evaluation results\n\n'+completion_text+'\n\n'
        + ('Finalized research report: complete frozen primary matrix.\n' if complete else
           'Finalized exploratory snapshot; primary research evaluation remains incomplete.\n'), 1)
    if not complete:
        report = report.replace('95% paired CI', 'Exploratory 95% CI (completed subset)')
    report = report.replace('](configuration_manifest.json)', '](../../configuration_manifest.json)')
    report = report.replace('](research_evaluation_protocol_frozen.md)', '](../../research_evaluation_protocol_frozen.md)')
    path.write_text(report, encoding="utf-8")
    return path


def generate_report(output):
    """Publish an immutable report generation with a fresh validated aggregate."""
    from .research_experiments import _aggregate
    version = active_directory(output)
    verify_manifest(version)
    with report_generation(version, 'report') as staging:
        _aggregate(version, staging)
        # Capture optional diagnostic inputs used by this renderer in its seal.
        for name in ('snapshot_assignment_comparison.csv', 'extraction_snapshot_comparison.csv',
                     'live_runtime.json', 'development_gate.json', 'extraction/metrics.json'):
            source = version/name
            if source.is_file():
                target = staging/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        _render_report(version, staging)
        generation = read_record(staging/'attempt.json')['destination']
    return version/'reports'/generation/'research_results.md'

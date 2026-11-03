"""Paired, resumable live comparison across all recorded support types.

Run from the project root: python scripts/evaluate_intervention_types.py
References are extracted from spoken turns, never supplied to the model.
"""

from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intervention.findings import FINDINGS_SCHEMA, validate_findings
from src.intervention.ollama_client import OllamaClient
from src.intervention.prompts import RAG_SYSTEM_PROMPT, SIMPLE_SYSTEM_PROMPT
from src.intervention.rag import InterventionRAG
from src.intervention.reports import write_report
from src.intervention.session_index import SessionIndex
from src.intervention.simple_llm import SimpleLLM
from src.intervention.semantic_validation import REVIEW_PROMPT, REVIEW_SCHEMA
from src.intervention.transcripts import group_sessions, load_sessions
from src.utils.constants import HISTORIES

OUTPUT = ROOT / "outputs/intervention_type_evaluation"
MODEL = "qwen3.5:latest"
QUESTION = "What barriers remain, what happened to agreed actions, and is there evidence of delivered support or improvement?"
DELIVERY_FIELDS = ("intended_status", "direct_activity_statuses", "external_support_statuses")


def reply(session, question):
    for position, turn in enumerate(session.turns[:-1]):
        if question in turn:
            return session.turns[position + 1]
    raise ValueError(f"Missing reference question: {session.history_id}, {question}")


def references(history):
    entries = []
    for session in history:
        action = next(t for t in session.turns if "A possible between-session step is to " in t)
        entry = {
            "session_number": session.number,
            "new_action_quote": action,
            "new_action_reply": reply(session, "A possible between-session step is to "),
            "session_helpfulness_quote": reply(session, "Which part of that exercise was useful?"),
            "remaining_difficulty_quote": reply(session, "What part remains difficult after that activity?"),
        }
        if session.number > 1:
            entry["prior_action_quote"] = next(t for t in session.turns if "Last time we agreed" in t)
            entry["prior_action_reply"] = reply(session, "Last time we agreed")
            entry["barrier_change_quote"] = reply(session, "Has the main concern changed")
        entries.append(entry)
    return {
        "initial_concern_quote": reply(history[0], "What is the main problem"),
        "sessions": entries,
        "final_reference": {
            "primary_barrier_resolved": ["no", "partial"],
            "attendance_improved": ["unknown"],
            "session_helpful": ["yes"],
        },
        "scoring_note": "Only three narrow final-field checks. Delivery and intervention helpfulness require scope-sensitive review; neither is automatically scored.",
    }


class MeteredClient:
    def __init__(self, destination):
        self.client = OllamaClient(model=MODEL, timeout=600)
        self.destination = destination
        self.calls = []
        self.requests = []

    def generate(self, messages, schema):
        self.requests.append({"messages": messages, "schema": schema})
        write_report(self.destination / "requests.json", self.requests)
        call = {"prompt_chars": len(json.dumps(messages)) + len(json.dumps(schema))}
        self.calls.append(call)
        started = perf_counter()
        try:
            result = self.client.generate(messages, schema)
            write_report(self.destination / f"response_{len(self.calls):02}.json", result)
            return result
        finally:
            call["elapsed_seconds"] = round(perf_counter() - started, 3)
            print(f"  call {len(self.calls)}: {call['elapsed_seconds']} s", flush=True)


def run_method(history, method, destination, reference):
    client = MeteredClient(destination)
    started = perf_counter()
    index = None
    error = None
    report = None
    partial = []
    try:
        if method == "rag":
            index = SessionIndex()
            index.build(history)
            analyser = InterventionRAG(index, client)
        else:
            analyser = SimpleLLM(history, client)

        def save_step(step):
            partial.append(step)
            write_report(destination / "timeline.json", partial)

        report = analyser.analyse(history[0].history_id, history[-1].number,
                                  QUESTION, on_session=save_step)
        for step in report["timeline"]:
            validate_findings(step["findings"])
        assert [s["session_number"] for s in report["timeline"]] == [s.number for s in history]
        assert report["conclusion"] == report["timeline"][-1]["findings"]
        write_report(destination / "conclusion.json", report)
    except (ValueError, RuntimeError, AssertionError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if index is not None:
            index.close()
    result = {
        "method": method, "status": "failed" if error else "completed", "error": error,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "model_calls": len(client.calls), "calls": client.calls,
        "total_prompt_chars": sum(c["prompt_chars"] for c in client.calls),
        "valid_saved_entries": len(partial),
    }
    if report is not None and not error:
        f = report["conclusion"]
        values = {**f["outcome"], "session_helpful": f["session_helpful"],
                  "intended_status": f["intervention"]["intended_intervention"]["status"],
                  "direct_activity_statuses": {c["component_id"]: c["status"]
                                               for c in f["intervention"]["direct_activities"]},
                  "external_support_statuses": {c["component_id"]: c["status"]
                                                for c in f["intervention"]["external_support"]}}
        checks = {key: values[key] in allowed for key, allowed in reference["final_reference"].items()}
        result.update(final_values=values, reference_checks=checks,
                      reference_checks_passed=sum(checks.values()), reference_checks_total=len(checks))
    write_report(destination / "measurement.json", result)
    return result


def summarize_results():
    comparison = json.loads((OUTPUT / "comparison.json").read_text())
    results = comparison["results"]
    planned = comparison["planned_cases"]
    summary = {"planned_cases": planned, "recorded_method_results": len(results), "methods": {}}
    for method in ("rag", "simple"):
        rows = [r for r in results if r["method"] == method]
        good = [r for r in rows if r["status"] == "completed"]
        times = [r["elapsed_seconds"] for r in rows]
        summary["methods"][method] = {
            "completed_cases": len(good), "failed_cases": len(rows) - len(good),
            "unrun_cases": planned - len(rows),
            "total_model_calls": sum(r["model_calls"] for r in rows),
            "total_elapsed_seconds": round(sum(times), 3),
            "mean_elapsed_seconds": round(sum(times) / len(times), 3) if times else None,
            "median_elapsed_seconds": median(times) if times else None,
            "total_prompt_chars": sum(r["total_prompt_chars"] for r in rows),
            "reference_checks_passed": sum(r.get("reference_checks_passed", 0) for r in rows),
            "planned_reference_checks": 3 * planned,
            "final_check_passes": {key: sum(r["reference_checks"][key] for r in good)
                                  for key in ("primary_barrier_resolved", "attendance_improved", "session_helpful")},
        }
    pairs = []
    for key in sorted({r["history_id"] for r in results}):
        pair = {r["method"]: r for r in results if r["history_id"] == key and r["status"] == "completed"}
        if len(pair) == 2:
            pairs.append(pair)
    summary["completed_pairs"] = len(pairs)
    summary["final_field_agreement_counts"] = {
        key: sum(p["rag"]["final_values"][key] == p["simple"]["final_values"][key] for p in pairs)
        # Generated component IDs are local to a method; comparing their raw maps
        # across methods would mistake ID differences for delivery disagreement.
        for key in ("primary_barrier_resolved", "attendance_improved", "intervention_helpful", "intended_status", "session_helpful")
    }
    if pairs:
        rag_time = sum(p["rag"]["elapsed_seconds"] for p in pairs)
        simple_time = sum(p["simple"]["elapsed_seconds"] for p in pairs)
        rag_chars = sum(p["rag"]["total_prompt_chars"] for p in pairs)
        simple_chars = sum(p["simple"]["total_prompt_chars"] for p in pairs)
        summary["simple_elapsed_reduction_percent"] = round(100 * (1 - simple_time / rag_time), 2)
        summary["simple_prompt_char_reduction_percent"] = round(100 * (1 - simple_chars / rag_chars), 2)
        summary["simple_faster_pairs"] = sum(p["simple"]["elapsed_seconds"] < p["rag"]["elapsed_seconds"] for p in pairs)
    write_report(OUTPUT / "summary.json", summary)
    fields = ["history_id", "method", "status", "elapsed_seconds", "model_calls", "total_prompt_chars",
              "reference_checks_passed", "primary_barrier_resolved", "attendance_improved",
              "intervention_helpful", *DELIVERY_FIELDS, "session_helpful"]
    with (OUTPUT / "comparison.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            row = {**result, **result.get("final_values", {})}
            for key in DELIVERY_FIELDS[1:]:
                if key in row:
                    row[key] = json.dumps(row[key], sort_keys=True)
            writer.writerow(row)
    return summary


def main():
    histories = group_sessions(load_sessions(HISTORIES))
    kinds = sorted({key.split("/")[0] for key in histories})
    selected = [next(key for key in sorted(histories)
                     if key.startswith(kind + "/") and len(histories[key]) == 3) for kind in kinds]
    manifest = {
        "model": MODEL, "question": QUESTION, "temperature": 0, "num_ctx": 32768,
        "python_version": platform.python_version(),
        "selection": "Lexicographically first complete exactly-three-session history per support type.",
        "system_prompts": {"rag": RAG_SYSTEM_PROMPT, "simple": SIMPLE_SYSTEM_PROMPT},
        "findings_schema": FINDINGS_SCHEMA,
        "semantic_review": {"prompt": REVIEW_PROMPT, "schema": REVIEW_SCHEMA},
        "cases": [{"history_id": key,
                   "transcript_sha256": hashlib.sha256(json.dumps([
                       {"number": s.number, "turns": s.turns, "metadata": s.metadata}
                       for s in histories[key]], ensure_ascii=False).encode()).hexdigest(),
                   "order": ["rag", "simple"] if i % 2 == 0 else ["simple", "rag"],
                   "reference": references(histories[key])}
                  for i, key in enumerate(selected)],
    }
    path = OUTPUT / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError("Existing run differs from current inputs/settings; use a new output directory")
    else:
        write_report(path, manifest)
    results = []
    for position, case in enumerate(manifest["cases"], 1):
        key = case["history_id"]
        for method in case["order"]:
            destination = OUTPUT / key.split("/")[0] / method
            measurement_path = destination / "measurement.json"
            print(f"[{position}/{len(selected)}] {key} {method}", flush=True)
            if measurement_path.exists():
                result = json.loads(measurement_path.read_text())
                print("  retained existing result", flush=True)
            else:
                result = run_method(histories[key], method, destination, case["reference"])
            results.append({"history_id": key, **result})
            write_report(OUTPUT / "comparison.json", {
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "planned_cases": len(selected), "results": results,
            })
            print(f"  {result['status']}: {result['elapsed_seconds']} s", flush=True)
    summarize_results()
    if any(r["status"] != "completed" for r in results):
        raise SystemExit("Some methods failed; inspect comparison.json")


if __name__ == "__main__":
    main()

"""Run the frozen synthetic extraction benchmark; --live requests real Ollama."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.extraction_evaluation import (
    evaluate_records, freeze_benchmark, make_cached_extractor, run_comparator,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results/research_evaluation/extraction"))
    parser.add_argument("--live", action="store_true", help="Run actual local Ollama inference; never falls back to fixtures")
    args = parser.parse_args(argv)
    manifest = freeze_benchmark(args.output_dir)
    cases = manifest["cases"]
    summary = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
               "protocol_sha256": manifest["protocol_sha256"], "gold_manifest_sha256": manifest["gold_manifest_sha256"],
               "gold_reference": {}, "exact_rule": {}, "real_llm": {"status": "not_requested"}}
    for method in ("gold_reference", "exact_rule"):
        records = run_comparator(cases, method)
        (args.output_dir / (method + "_outputs.jsonl")).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
        summary[method] = {"status": "completed", "metrics": evaluate_records(cases, records)}
    if args.live:
        try:
            extractor = make_cached_extractor(args.output_dir / "cache")
        except (OSError, ValueError, RuntimeError) as exc:
            summary["real_llm"] = {"status": "unavailable", "error": str(exc), "new_inference_calls": 0}
        else:
            (args.output_dir / "runtime_configuration.json").write_text(json.dumps(extractor.configuration, indent=2) + "\n")
            output_path = args.output_dir / "real_llm_outputs.jsonl"
            # Per-case records survive interruptions; prior full-context outputs remain in cache.
            output_path.write_text("")
            records = run_comparator(cases, "real_llm", extractor, record_path=output_path)
            summary["real_llm"] = {"status": "completed", "new_inference_calls": extractor.calls,
                                   "cache_hits": sum(r.get("audit", {}).get("cache_hit", False) for r in records),
                                   "model_digest": extractor.configuration["model_metadata"]["digest"],
                                   "metrics": evaluate_records(cases, records)}
    (args.output_dir / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 1 if args.live and summary["real_llm"]["status"] != "completed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

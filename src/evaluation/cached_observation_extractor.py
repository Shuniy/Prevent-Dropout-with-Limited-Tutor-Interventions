"""Persistent, configuration-complete cache around the existing Step 5 extractor."""

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib.request import urlopen

from src.intervention import observation_extractor, ollama_client
from src.intervention.observation_extractor import (
    EXTRACTION_SCHEMA, LLMObservationExtractor,
    SYSTEM_PROMPT, source_spans, validate_extraction,
)
from src.intervention.ollama_client import OllamaClient


def content_digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class CachedObservationExtractor:
    """Cache real calls only; an unavailable model never becomes a fixture response.

    Cache keys contain complete request context, including model digest and code.
    The existing client's returned structured JSON is retained without repair. Its
    HTTP envelope and malformed response bodies are not exposed by that client.
    """

    def __init__(self, cache_path, *, model="qwen3.5:latest", num_ctx=8192,
                 timeout=300, base_url=None):
        self.client = OllamaClient(model=model, num_ctx=num_ctx, timeout=timeout, base_url=base_url)
        with urlopen(self.client.base_url + "/api/tags", timeout=15) as response:
            tags = json.load(response)
        selected = next((m for m in tags.get("models", []) if m.get("name") == model), None)
        if not selected or not selected.get("digest"):
            raise RuntimeError(f"Ollama model {model} has no installed digest")
        self.configuration = {
            "model": model, "model_metadata": selected, "base_url": self.client.base_url,
            "timeout_seconds": timeout, "options": {"temperature": 0, "num_ctx": num_ctx},
            "think": False, "stream": False, "system_prompt": SYSTEM_PROMPT,
            "schema": EXTRACTION_SCHEMA,
            "extractor_code_sha256": sha256(Path(observation_extractor.__file__).read_bytes()).hexdigest(),
            "client_code_sha256": sha256(Path(ollama_client.__file__).read_bytes()).hexdigest(),
            "cache_adapter_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "raw_output_scope": "Parsed JSON returned by existing OllamaClient; no HTTP envelope or malformed body capture",
        }
        self.cache_path = Path(cache_path)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.audit_records = []
        self.quarantine = []

    def extract(self, note, as_of_time):
        # Reject timing before looking up or populating any model cache.
        if note.available_from_month > as_of_time or note.event_month >= as_of_time:
            raise ValueError("note is not available at this decision cutoff")
        context = {"configuration": self.configuration, "note": asdict(note),
                   "as_of_month": as_of_time, "source_spans": source_spans(note.text)}
        key = content_digest(context)
        path = self.cache_path / (key + ".json")
        cache_hit = path.exists()
        if cache_hit:
            record = json.loads(path.read_text())
            if record.get("cache_key") != key or content_digest(record.get("context")) != key:
                raise ValueError("persistent extraction cache context mismatch")
        else:
            extractor = LLMObservationExtractor(self.client)
            started = time.monotonic()
            try:
                self.calls += 1
                extractor.extract(note, as_of_time)
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                error = str(exc)
            else:
                error = None
            record = {
                "cache_key": key, "context": context, "origin": "real_local_ollama",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
                "status": "accepted" if error is None else "quarantined", "error": error,
                "raw_output": extractor.audit_records[-1].get("raw_output") if extractor.audit_records else None,
                "raw_output_unavailable_reason": None if extractor.audit_records and "raw_output" in extractor.audit_records[-1]
                else "Existing client failed before returning parsed JSON; original HTTP body is not exposed",
            }
            temporary = path.with_suffix(f".{os.getpid()}.tmp")
            temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
            temporary.replace(path)
        audit = {"note_id": note.note_id, "as_of_month": as_of_time, "cache_key": key,
                 "cache_hit": cache_hit, "origin": record["origin"], "status": record["status"],
                 "raw_output": record.get("raw_output"), "reason": record.get("error"),
                 "elapsed_seconds": record["elapsed_seconds"], "cache_file": str(path)}
        self.audit_records.append(audit)
        if record["status"] != "accepted":
            self.quarantine.append(audit)
            raise ValueError(record.get("error") or "cached model failure")
        # Cache hits still pass the current provenance, entailment and timing guards.
        return validate_extraction(record["raw_output"], note, as_of_time)

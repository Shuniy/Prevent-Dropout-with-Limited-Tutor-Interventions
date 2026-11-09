"""Structured JSON generation using local Ollama."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from hashlib import sha256


def endpoint_identity(base_url):
    """Hash canonical routing, excluding URL authentication, query and fragment."""
    parsed = urlsplit(base_url)
    scheme, host = parsed.scheme.lower(), (parsed.hostname or '').lower()
    port = parsed.port or (443 if scheme == 'https' else 80 if scheme == 'http' else None)
    canonical = json.dumps([scheme, host, port, parsed.path.rstrip('/')], separators=(',', ':'))
    return sha256(canonical.encode()).hexdigest()


class OllamaClient:
    def __init__(self, model: str = "qwen3.5:latest", base_url: str | None = None,
                 timeout: int = 300, num_ctx: int = 32768, *, temperature: float = 0,
                 model_digest: str | None = None) -> None:
        self.model = model
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.model_digest = model_digest

    @property
    def execution_configuration(self):
        return {'backend': 'ollama/api/chat', 'endpoint_sha256': endpoint_identity(self.base_url),
            'model': self.model, 'model_digest': self.model_digest,
            'num_ctx': self.num_ctx, 'timeout_seconds': self.timeout,
            'temperature': self.temperature, 'think': False, 'stream': False}

    def generate(self, messages: list[dict], schema: dict) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "think": False, "format": schema,
                   "options": {"temperature": self.temperature, "num_ctx": self.num_ctx}}
        request = Request(f"{self.base_url}/api/chat", json.dumps(payload).encode(),
                          {"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"Ollama HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama unavailable at endpoint {endpoint_identity(self.base_url)}") from exc
        if result.get("done_reason") == "length":
            raise ValueError("Ollama output was truncated; increase context or output budget")
        return json.loads(result["message"]["content"])

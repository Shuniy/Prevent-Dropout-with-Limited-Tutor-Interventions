"""Structured JSON generation using local Ollama."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaClient:
    def __init__(self, model: str = "qwen3.5:latest", base_url: str | None = None,
                 timeout: int = 300, num_ctx: int = 32768) -> None:
        self.model = model
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout
        self.num_ctx = num_ctx

    def generate(self, messages: list[dict], schema: dict) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "think": False, "format": schema,
                   "options": {"temperature": 0, "num_ctx": self.num_ctx}}
        request = Request(f"{self.base_url}/api/chat", json.dumps(payload).encode(),
                          {"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"Ollama HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama unavailable at {self.base_url}; start Ollama and install {self.model}") from exc
        if result.get("done_reason") == "length":
            raise ValueError("Ollama output was truncated; increase context or output budget")
        return json.loads(result["message"]["content"])

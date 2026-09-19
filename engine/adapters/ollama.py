from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import AdapterResult
from ..schemas import ReasoningEffort


class OllamaAdapter:
    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")

    def _json_get(self, path: str, timeout: float = 2.0) -> dict[str, Any]:
        with urllib.request.urlopen(
            self.base_url + path,
            timeout=timeout,
        ) as response:
            raw: object = json.loads(response.read().decode())
        return raw if isinstance(raw, dict) else {}

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(
                self.base_url + "/api/tags",
                timeout=1.0,
            ) as response:
                return int(response.status) == 200
        except (OSError, urllib.error.URLError):
            return False

    def models(self) -> list[str]:
        if not self.available():
            return []
        try:
            data = self._json_get("/api/tags")
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return []
        models = data.get("models", [])
        if not isinstance(models, list):
            return []
        return [
            str(model.get("name"))
            for model in models
            if isinstance(model, dict) and model.get("name")
        ]

    def model_context_length(self, model: str) -> int | None:
        payload = json.dumps({"model": model}).encode()
        request = urllib.request.Request(
            self.base_url + "/api/show",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3.0) as response:
                raw: object = json.loads(response.read().decode())
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ):
            return None
        if not isinstance(raw, dict):
            return None
        info = raw.get("model_info")
        if not isinstance(info, dict):
            return None
        candidates = [
            int(value)
            for key, value in info.items()
            if str(key).endswith(".context_length")
            and isinstance(value, (int, float))
        ]
        return max(candidates) if candidates else None

    def diagnostics(self) -> dict[str, Any]:
        models = self.models()
        return {
            "endpoint": self.base_url,
            "available": bool(models) or self.available(),
            "models": [
                {
                    "id": model,
                    "context_length": self.model_context_length(model),
                }
                for model in models
            ],
            "tool_behavior": "prompt-only evidence consumer",
            "filesystem_tools": False,
            "sandbox_enforced": False,
        }

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        model: str = "auto",
        effort: ReasoningEffort = ReasoningEffort.MEDIUM,
        timeout_seconds: int = 900,
        sandbox_mode: str = "read-only",
    ) -> AdapterResult:
        del cwd, effort, sandbox_mode
        if model == "auto":
            models = self.models()
            if not models:
                return AdapterResult(
                    False,
                    "",
                    error="no Ollama model is available",
                )
            model = models[0]
        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
        ).encode()
        request = urllib.request.Request(
            self.base_url + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                data = json.loads(response.read().decode())
            return AdapterResult(
                True,
                data.get("response", ""),
                usage={
                    "input_tokens": int(
                        data.get("prompt_eval_count", 0)
                    ),
                    "output_tokens": int(
                        data.get("eval_count", 0)
                    ),
                },
            )
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return AdapterResult(False, "", error=str(exc))

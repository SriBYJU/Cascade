from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import AdapterResult
from ..schemas import ReasoningEffort


class VLLMAdapter:
    name = "vllm"

    def __init__(self, base_url: str = "http://127.0.0.1:8000/v1"):
        self.base_url = base_url.rstrip("/")

    def _models_payload(self) -> list[dict[str, Any]]:
        try:
            with urllib.request.urlopen(
                self.base_url + "/models",
                timeout=2.0,
            ) as response:
                raw: object = json.loads(response.read().decode())
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ):
            return []
        if not isinstance(raw, dict):
            return []
        data = raw.get("data", [])
        return [
            item
            for item in data
            if isinstance(item, dict)
        ] if isinstance(data, list) else []

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(
                self.base_url + "/models",
                timeout=1.0,
            ) as response:
                return int(response.status) == 200
        except (OSError, urllib.error.URLError):
            return False

    def models(self) -> list[str]:
        return [
            str(model.get("id"))
            for model in self._models_payload()
            if model.get("id")
        ]

    def diagnostics(self) -> dict[str, Any]:
        models = self._models_payload()
        return {
            "endpoint": self.base_url,
            "available": self.available(),
            "models": [
                {
                    "id": str(model.get("id")),
                    "context_length": (
                        int(model["max_model_len"])
                        if isinstance(model.get("max_model_len"), int)
                        else None
                    ),
                }
                for model in models
                if model.get("id")
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
        models = self.models()
        model = models[0] if model == "auto" and models else model
        if not model or model == "auto":
            return AdapterResult(
                False,
                "",
                error="no vLLM model is available",
            )
        payload = json.dumps(
            {"model": model, "input": prompt}
        ).encode()
        request = urllib.request.Request(
            self.base_url + "/responses",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                data = json.loads(response.read().decode())
            usage_raw = data.get("usage", {})
            usage = (
                {
                    str(key): int(value)
                    for key, value in usage_raw.items()
                    if isinstance(value, int)
                }
                if isinstance(usage_raw, dict)
                else {}
            )
            return AdapterResult(
                True,
                data.get("output_text", ""),
                usage=usage,
            )
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return AdapterResult(False, "", error=str(exc))

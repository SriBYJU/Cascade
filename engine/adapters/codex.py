from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from ..schemas import ReasoningEffort
from .base import AdapterResult


class CodexAdapter:
    name = "codex"
    VALID_SANDBOXES = {"read-only", "workspace-write"}

    def available(self) -> bool:
        return shutil.which("codex") is not None

    def version(self) -> str | None:
        if not self.available():
            return None
        proc = subprocess.run(
            ["codex", "--version"],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        return (
            (proc.stdout or proc.stderr).strip()
            if proc.returncode == 0
            else None
        )

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
        if not self.available():
            return AdapterResult(
                False,
                "",
                error="codex CLI is not installed",
            )
        if sandbox_mode not in self.VALID_SANDBOXES:
            return AdapterResult(
                False,
                "",
                error=f"unsupported Codex sandbox mode: {sandbox_mode}",
            )

        command = [
            "codex",
            "exec",
            "--json",
            "--sandbox",
            sandbox_mode,
        ]
        if model and model != "auto":
            command.extend(["--model", model])
        command.extend(
            [
                "--config",
                f'model_reasoning_effort="{effort.value}"',
                prompt,
            ]
        )
        try:
            proc = subprocess.run(
                command,
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                False,
                "",
                error=f"codex timed out after {timeout_seconds}s",
            )

        events: list[dict[str, Any]] = []
        final = ""
        usage: dict[str, int] = {}
        for line in (proc.stdout or "").splitlines():
            try:
                raw: object = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(raw, dict):
                continue
            event: dict[str, Any] = raw
            events.append(event)
            item = event.get("item")
            if (
                event.get("type") == "item.completed"
                and isinstance(item, dict)
                and item.get("type") == "agent_message"
            ):
                text = item.get("text")
                if isinstance(text, str):
                    final = text
            raw_usage = event.get("usage")
            if (
                event.get("type") == "turn.completed"
                and isinstance(raw_usage, dict)
            ):
                usage = {
                    str(key): int(value)
                    for key, value in raw_usage.items()
                    if isinstance(value, int)
                }

        error = (
            None
            if proc.returncode == 0
            else (proc.stderr or "codex execution failed").strip()
        )
        return AdapterResult(
            proc.returncode == 0,
            final,
            events=events,
            usage=usage,
            error=error,
        )

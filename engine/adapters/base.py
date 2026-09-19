from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..schemas import ReasoningEffort


@dataclass(slots=True)
class AdapterResult:
    ok: bool
    final_message: str
    events: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None


class ModelAdapter(Protocol):
    name: str

    def available(self) -> bool: ...

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        model: str = "auto",
        effort: ReasoningEffort = ReasoningEffort.MEDIUM,
        timeout_seconds: int = 900,
    ) -> AdapterResult: ...

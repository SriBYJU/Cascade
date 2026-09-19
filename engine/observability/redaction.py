from __future__ import annotations

import hashlib
import json
from typing import Any

CONTENT_KEYS = {
    "content",
    "decision",
    "diff",
    "error",
    "final_message",
    "findings",
    "output",
    "prompt",
    "risks",
    "stderr",
    "stdout",
    "summary",
    "text",
    "worker_message",
}


def _digest(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _redacted_value(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        size = len(value)
        kind = "string"
    elif isinstance(value, (list, tuple, set, dict)):
        size = len(value)
        kind = type(value).__name__
    elif value is None:
        size = 0
        kind = "none"
    else:
        size = 1
        kind = type(value).__name__
    return {
        "redacted": True,
        "kind": kind,
        "size": size,
        "sha256": _digest(value),
    }


def metadata_only_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    def visit(value: object, key: str | None = None) -> object:
        if key is not None and key.lower() in CONTENT_KEYS:
            return _redacted_value(value)
        if isinstance(value, dict):
            return {
                str(child_key): visit(child_value, str(child_key))
                for child_key, child_value in value.items()
            }
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    return {
        str(key): visit(value, str(key))
        for key, value in payload.items()
    }

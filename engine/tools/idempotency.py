from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from ..state.db import StateDB


def operation_fingerprint(operation: str, payload: dict[str, Any]) -> str:
    raw = json.dumps({"operation": operation, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class IdempotencyLedger:
    def __init__(self, db: StateDB):
        self.db = db

    def get(self, key: str) -> dict[str, Any] | None:
        rows = self.db.query("SELECT * FROM idempotency WHERE operation_key=?", (key,))
        if not rows:
            return None
        row = rows[0]
        return {"status": row["status"], "result": self.db.loads(row["result_json"])}

    def begin(self, key: str) -> bool:
        if self.get(key):
            return False
        self.db.execute(
            "INSERT INTO idempotency(operation_key,status,result_json) VALUES(?,?,NULL)",
            (key, "running"),
        )
        return True

    def complete(self, key: str, result: Any) -> None:
        self.db.execute(
            "UPDATE idempotency SET status='completed',result_json=?,updated_at=CURRENT_TIMESTAMP WHERE operation_key=?",
            (self.db.dumps(result), key),
        )

    def fail(self, key: str, result: Any) -> None:
        self.db.execute(
            "UPDATE idempotency SET status='failed',result_json=?,updated_at=CURRENT_TIMESTAMP WHERE operation_key=?",
            (self.db.dumps(result), key),
        )

    def execute_once(self, operation: str, payload: dict[str, Any], fn: Callable[[], Any]) -> tuple[Any, bool]:
        key = operation_fingerprint(operation, payload)
        prior = self.get(key)
        if prior and prior["status"] == "completed":
            return prior["result"], True
        if prior and prior["status"] == "running":
            raise RuntimeError(f"operation already running: {key}")
        if not prior:
            self.begin(key)
        try:
            result = fn()
        except Exception as exc:
            self.fail(key, {"error": str(exc)})
            raise
        self.complete(key, result)
        return result, False

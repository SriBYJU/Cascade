from __future__ import annotations

from typing import Any

from .db import StateDB
from ..schemas import Event


class EventStore:
    def __init__(self, db: StateDB):
        self.db = db

    def append(self, event: Event) -> None:
        self.db.execute(
            """INSERT INTO events(run_id,task_id,attempt_id,event,ts,actor,provenance_json,metrics_json,payload_json,payload_redacted)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                event.run_id,
                event.task_id,
                event.attempt_id,
                event.event,
                event.ts,
                event.actor,
                self.db.dumps(event.provenance.model_dump(mode="json")) if event.provenance else None,
                self.db.dumps(event.metrics),
                self.db.dumps(event.payload),
                int(event.payload_redacted),
            ),
        )

    def list_run(self, run_id: str) -> list[Event]:
        rows = self.db.query("SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,))
        return [self._from_row(row) for row in rows]

    def latest(self, limit: int = 100) -> list[Event]:
        rows = self.db.query("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [self._from_row(row) for row in reversed(rows)]

    def _from_row(self, row: dict[str, Any]) -> Event:
        return Event(
            run_id=row["run_id"],
            task_id=row["task_id"],
            attempt_id=row["attempt_id"],
            event=row["event"],
            ts=row["ts"],
            actor=row["actor"],
            provenance=self.db.loads(row["provenance_json"]),
            metrics=self.db.loads(row["metrics_json"]),
            payload=self.db.loads(row["payload_json"]),
            payload_redacted=bool(row["payload_redacted"]),
        )

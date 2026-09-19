from __future__ import annotations

from .db import StateDB


class CheckpointStore:
    VALID_STATES = {
        "PLANNED", "QUEUED", "RUNNING", "VALIDATING", "READY_TO_MERGE",
        "MERGED", "FAILED", "RETRY", "ESCALATE", "BLOCKED", "CANCELLED",
    }

    def __init__(self, db: StateDB):
        self.db = db

    def save(self, run_id: str, task_id: str, state: str, payload: dict | None = None) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"invalid checkpoint state: {state}")
        self.db.execute(
            """INSERT INTO checkpoints(run_id,task_id,state,payload_json,updated_at)
               VALUES(?,?,?,?,CURRENT_TIMESTAMP)
               ON CONFLICT(run_id,task_id) DO UPDATE SET
                 state=excluded.state,payload_json=excluded.payload_json,updated_at=CURRENT_TIMESTAMP""",
            (run_id, task_id, state, self.db.dumps(payload or {})),
        )

    def get(self, run_id: str, task_id: str) -> dict | None:
        rows = self.db.query(
            "SELECT * FROM checkpoints WHERE run_id=? AND task_id=?", (run_id, task_id)
        )
        if not rows:
            return None
        row = rows[0]
        return {"run_id": run_id, "task_id": task_id, "state": row["state"], "payload": self.db.loads(row["payload_json"])}

    def resumable(self) -> list[dict]:
        rows = self.db.query(
            "SELECT * FROM checkpoints WHERE state NOT IN ('MERGED','CANCELLED') ORDER BY updated_at DESC"
        )
        return [
            {"run_id": r["run_id"], "task_id": r["task_id"], "state": r["state"], "payload": self.db.loads(r["payload_json"])}
            for r in rows
        ]

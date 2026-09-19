from __future__ import annotations

import time

from ..state.db import StateDB


class CircuitBreaker:
    def __init__(self, db: StateDB, threshold: int = 3, cooldown_seconds: int = 120):
        self.db = db
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds

    def allow(self, key: str) -> bool:
        rows = self.db.query("SELECT * FROM circuit_breakers WHERE key=?", (key,))
        if not rows:
            return True
        until = rows[0]["opened_until"]
        return until is None or float(until) <= time.time()

    def success(self, key: str) -> None:
        self.db.execute(
            """INSERT INTO circuit_breakers(key,failures,opened_until) VALUES(?,0,NULL)
               ON CONFLICT(key) DO UPDATE SET failures=0,opened_until=NULL,updated_at=CURRENT_TIMESTAMP""",
            (key,),
        )

    def failure(self, key: str) -> None:
        rows = self.db.query("SELECT failures FROM circuit_breakers WHERE key=?", (key,))
        failures = (rows[0]["failures"] if rows else 0) + 1
        opened = time.time() + self.cooldown_seconds if failures >= self.threshold else None
        self.db.execute(
            """INSERT INTO circuit_breakers(key,failures,opened_until) VALUES(?,?,?)
               ON CONFLICT(key) DO UPDATE SET failures=excluded.failures,opened_until=excluded.opened_until,updated_at=CURRENT_TIMESTAMP""",
            (key, failures, opened),
        )

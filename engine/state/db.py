from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  attempt_id INTEGER NOT NULL,
  event TEXT NOT NULL,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  provenance_json TEXT,
  metrics_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_redacted INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, id);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, id);
CREATE TABLE IF NOT EXISTS checkpoints (
  run_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  state TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(run_id, task_id)
);
CREATE TABLE IF NOT EXISTS exact_cache (
  cache_key TEXT PRIMARY KEY,
  repo_fingerprint TEXT NOT NULL,
  value_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  hits INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS prompt_affinity (
  model_id TEXT NOT NULL,
  prefix_key TEXT NOT NULL,
  observations INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  cached_input_tokens INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(model_id, prefix_key)
);
CREATE TABLE IF NOT EXISTS idempotency (
  operation_key TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  result_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admitted_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_class TEXT NOT NULL,
  capability TEXT NOT NULL,
  success INTEGER NOT NULL,
  evaluator TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS circuit_breakers (
  key TEXT PRIMARY KEY,
  failures INTEGER NOT NULL DEFAULT 0,
  opened_until REAL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class StateDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock, self.connection() as conn:
            conn.execute(sql, params)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock, self.connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def loads(value: str | None) -> Any:
        return None if value is None else json.loads(value)

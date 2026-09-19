from __future__ import annotations

import hashlib
import json
from typing import Any

from ..state.db import StateDB


def make_cache_key(
    normalized_task: str,
    relevant_git_tree_fingerprint: str,
    constraints: list[str],
    tool_versions: dict[str, str],
    capability_profile: dict[str, Any],
) -> str:
    payload = {
        "task": " ".join(normalized_task.split()),
        "repo": relevant_git_tree_fingerprint,
        "constraints": sorted(constraints),
        "tool_versions": tool_versions,
        "capability_profile": capability_profile,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ExactCache:
    def __init__(self, db: StateDB):
        self.db = db

    def get(self, key: str, repo_fingerprint: str) -> Any | None:
        rows = self.db.query("SELECT * FROM exact_cache WHERE cache_key=?", (key,))
        if not rows:
            return None
        row = rows[0]
        if row["repo_fingerprint"] != repo_fingerprint:
            self.delete(key)
            return None
        self.db.execute("UPDATE exact_cache SET hits=hits+1 WHERE cache_key=?", (key,))
        return self.db.loads(row["value_json"])

    def put(self, key: str, repo_fingerprint: str, value: Any) -> None:
        self.db.execute(
            """INSERT INTO exact_cache(cache_key,repo_fingerprint,value_json,hits) VALUES(?,?,?,0)
               ON CONFLICT(cache_key) DO UPDATE SET repo_fingerprint=excluded.repo_fingerprint,value_json=excluded.value_json""",
            (key, repo_fingerprint, self.db.dumps(value)),
        )

    def delete(self, key: str) -> None:
        self.db.execute("DELETE FROM exact_cache WHERE cache_key=?", (key,))

    def clear(self) -> None:
        self.db.execute("DELETE FROM exact_cache")

    def stats(self) -> dict[str, int]:
        rows = self.db.query("SELECT COUNT(*) entries,COALESCE(SUM(hits),0) hits FROM exact_cache")
        return {"entries": int(rows[0]["entries"]), "hits": int(rows[0]["hits"])}

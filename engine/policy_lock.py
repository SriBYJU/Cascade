from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schemas import PolicyLock


def load_policy(path: str | Path) -> PolicyLock:
    return PolicyLock.model_validate(json.loads(Path(path).read_text()))


def policy_digest(policy: PolicyLock) -> str:
    raw = json.dumps(
        policy.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def write_proposal(policy: PolicyLock, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(
        json.dumps(policy.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    )
    temp.replace(target)

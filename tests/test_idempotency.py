from pathlib import Path

from engine.state.db import StateDB
from engine.tools.idempotency import IdempotencyLedger


def test_replay_returns_prior_result(tmp_path: Path):
    ledger = IdempotencyLedger(StateDB(tmp_path / "state.db"))
    calls = {"n": 0}
    def action():
        calls["n"] += 1
        return {"ok": True}
    first, replay1 = ledger.execute_once("send", {"id": 1}, action)
    second, replay2 = ledger.execute_once("send", {"id": 1}, action)
    assert first == second == {"ok": True}
    assert replay1 is False and replay2 is True
    assert calls["n"] == 1

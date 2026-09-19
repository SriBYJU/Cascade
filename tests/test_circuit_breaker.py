from pathlib import Path

from engine.scheduler.circuit_breaker import CircuitBreaker
from engine.state.db import StateDB


def test_circuit_opens_after_threshold_and_success_resets(
    tmp_path: Path,
):
    breaker = CircuitBreaker(
        StateDB(tmp_path / "state.db"),
        threshold=2,
        cooldown_seconds=60,
    )
    key = "codex:build"

    assert breaker.allow(key) is True
    breaker.failure(key)
    assert breaker.allow(key) is True
    breaker.failure(key)
    assert breaker.allow(key) is False

    breaker.success(key)
    assert breaker.allow(key) is True


def test_circuit_reopens_after_cooldown(monkeypatch, tmp_path: Path):
    now = 1_000.0
    monkeypatch.setattr(
        "engine.scheduler.circuit_breaker.time.time",
        lambda: now,
    )
    breaker = CircuitBreaker(
        StateDB(tmp_path / "state.db"),
        threshold=1,
        cooldown_seconds=5,
    )
    breaker.failure("provider:model")
    assert breaker.allow("provider:model") is False

    now = 1_006.0
    assert breaker.allow("provider:model") is True

from pathlib import Path

from engine.runtime import CascadeRuntime
from engine.schemas import (
    BudgetReservation,
    Capability,
    ReasoningEffort,
    RiskLevel,
    RouteDecision,
    StepType,
)


def _route(capability: Capability) -> RouteDecision:
    return RouteDecision(
        task_id="t",
        step_type=StepType.BUILD,
        capability=capability,
        reasoning_effort=ReasoningEffort.MEDIUM,
        model_target="auto",
        risk=RiskLevel.LOW,
        budget_reserved=BudgetReservation(tokens=1),
    )


def test_local_only_mode_never_falls_back_to_codex_for_writer(
    tmp_path: Path,
):
    runtime = CascadeRuntime(tmp_path)
    runtime.config.local_mode = True
    runtime.config.cloud_fallback = False

    adapter, model = runtime._select_adapter(
        _route(Capability.BUILD)
    )

    assert adapter is None
    assert model == "auto"


def test_local_only_mode_fails_closed_when_no_local_reader(
    monkeypatch,
    tmp_path: Path,
):
    runtime = CascadeRuntime(tmp_path)
    runtime.config.local_mode = True
    runtime.config.cloud_fallback = False
    monkeypatch.setattr(runtime.ollama, "available", lambda: False)
    monkeypatch.setattr(runtime.vllm, "available", lambda: False)

    adapter, model = runtime._select_adapter(
        _route(Capability.EXPLORE)
    )

    assert adapter is None
    assert model == "auto"


def test_cloud_fallback_can_remain_enabled_explicitly(
    monkeypatch,
    tmp_path: Path,
):
    runtime = CascadeRuntime(tmp_path)
    runtime.config.local_mode = True
    runtime.config.cloud_fallback = True
    monkeypatch.setattr(runtime.ollama, "available", lambda: False)
    monkeypatch.setattr(runtime.vllm, "available", lambda: False)

    adapter, _ = runtime._select_adapter(
        _route(Capability.BUILD)
    )

    assert adapter is runtime.codex

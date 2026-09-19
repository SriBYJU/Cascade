from pathlib import Path

from engine.adapters.base import AdapterResult
from engine.evaluation.harness import EvaluationHarness
from engine.evaluation.model_pool import EvaluationModelPool
from engine.evaluation.models import BenchmarkCase
from engine.schemas import (
    Capability,
    ModelProfile,
    ReasoningEffort,
)


def _profiles() -> dict[Capability, ModelProfile]:
    return {
        Capability.QUICK: ModelProfile(
            model_id="cheap-local",
            capability=Capability.QUICK,
            reasoning_efforts=[ReasoningEffort.LOW],
            local=True,
            cost_weight=0.1,
            latency_weight=0.2,
        ),
        Capability.BUILD: ModelProfile(
            model_id="balanced",
            capability=Capability.BUILD,
            reasoning_efforts=[ReasoningEffort.MEDIUM],
            cost_weight=0.5,
            latency_weight=0.6,
        ),
        Capability.CRITICAL: ModelProfile(
            model_id="frontier",
            capability=Capability.CRITICAL,
            reasoning_efforts=[ReasoningEffort.XHIGH],
            cost_weight=1.0,
            latency_weight=1.2,
        ),
    }


class CapturingAdapter:
    name = "capture"

    def __init__(self) -> None:
        self.models: list[str] = []

    def available(self) -> bool:
        return True

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        model: str = "auto",
        effort: ReasoningEffort = ReasoningEffort.MEDIUM,
        timeout_seconds: int = 900,
        sandbox_mode: str = "read-only",
    ) -> AdapterResult:
        del prompt, cwd, effort, timeout_seconds, sandbox_mode
        self.models.append(model)
        return AdapterResult(
            True,
            "answer config.py",
            usage={"input_tokens": 10, "output_tokens": 2},
        )


def test_model_pool_selects_provider_neutral_extremes():
    pool = EvaluationModelPool(_profiles())
    assert pool.strongest().model_id == "frontier"
    assert pool.efficient().model_id == "cheap-local"
    assert pool.local().model_id == "cheap-local"


def test_direct_baselines_use_model_pool_models(tmp_path: Path):
    adapter = CapturingAdapter()
    case = BenchmarkCase(
        case_id="read",
        category="search",
        task="find config",
        files={"config.py": "VALUE=1\n"},
        write_paths=[],
        acceptance=[],
        answer_contains=["config.py"],
    )
    report = EvaluationHarness(
        tmp_path,
        adapter=adapter,
        profiles=_profiles(),
    ).run(
        [case],
        configs=["strongest", "efficient", "local"],
        repeats=1,
        output_dir=tmp_path / "results",
    )
    assert report["measured"] is True
    assert adapter.models == [
        "frontier",
        "cheap-local",
        "cheap-local",
    ]
    assert report["model_pool"] is not None

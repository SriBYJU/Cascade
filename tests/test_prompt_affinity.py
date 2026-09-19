from pathlib import Path

from engine.cache.affinity_store import PromptAffinityStore, WORKER_STABLE_PREFIX
from engine.cache.prompt_affinity import stable_prefix_key
from engine.router.scorer import route_score
from engine.schemas import (
    Capability,
    ModelProfile,
    ReasoningEffort,
    RiskLevel,
    RouteFeatures,
    StepType,
)
from engine.state.db import StateDB


def test_prompt_affinity_uses_only_measured_cached_tokens(tmp_path: Path):
    store = PromptAffinityStore(StateDB(tmp_path / "state.db"))
    prefix = stable_prefix_key(WORKER_STABLE_PREFIX)
    store.observe(
        model_id="warm-model",
        prefix_key=prefix,
        input_tokens=1000,
        cached_input_tokens=600,
    )
    store.observe(
        model_id="warm-model",
        prefix_key=prefix,
        input_tokens=500,
        cached_input_tokens=300,
    )
    assert store.scores(prefix)["warm-model"] == 0.6


def test_zero_cache_evidence_does_not_create_fake_affinity(tmp_path: Path):
    store = PromptAffinityStore(StateDB(tmp_path / "state.db"))
    prefix = stable_prefix_key(WORKER_STABLE_PREFIX)
    store.observe(
        model_id="cold-model",
        prefix_key=prefix,
        input_tokens=1000,
        cached_input_tokens=0,
    )
    assert store.scores(prefix)["cold-model"] == 0.0


def test_candidate_specific_affinity_changes_score():
    warm = ModelProfile(
        model_id="warm",
        capability=Capability.BUILD,
        reasoning_efforts=[ReasoningEffort.MEDIUM],
        cost_weight=0.5,
        latency_weight=1.0,
    )
    cold = warm.model_copy(update={"model_id": "cold"})
    features = RouteFeatures(
        step_type=StepType.BUILD,
        task_text="bounded build",
        risk=RiskLevel.LOW,
        prompt_cache_affinity_by_model={"warm": 1.0, "cold": 0.0},
    )
    assert route_score(warm, features) > route_score(cold, features)

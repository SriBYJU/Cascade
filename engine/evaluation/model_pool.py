from __future__ import annotations

from dataclasses import dataclass

from ..router.capability_registry import CapabilityRegistry
from ..schemas import Capability, ModelProfile


@dataclass(frozen=True, slots=True)
class EvaluationModelPool:
    profiles: dict[Capability, ModelProfile]

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError("evaluation model pool cannot be empty")
        if Capability.NO_MODEL in self.profiles:
            raise ValueError("evaluation model pool cannot redefine no-model")

    def strongest(self) -> ModelProfile:
        available = [
            profile
            for profile in self.profiles.values()
            if profile.available
        ]
        if not available:
            raise ValueError("evaluation model pool has no available models")
        return max(
            available,
            key=lambda profile: CapabilityRegistry.order(
                profile.capability
            ),
        )

    def efficient(self) -> ModelProfile:
        available = [
            profile
            for profile in self.profiles.values()
            if profile.available
        ]
        if not available:
            raise ValueError("evaluation model pool has no available models")
        return min(
            available,
            key=lambda profile: (
                profile.cost_weight,
                CapabilityRegistry.order(profile.capability),
            ),
        )

    def local(self) -> ModelProfile:
        available = [
            profile
            for profile in self.profiles.values()
            if profile.available and profile.local
        ]
        if not available:
            raise ValueError("evaluation model pool has no local model")
        return min(
            available,
            key=lambda profile: (
                profile.cost_weight,
                CapabilityRegistry.order(profile.capability),
            ),
        )

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "model_id": profile.model_id,
                "capability": profile.capability.value,
                "reasoning_efforts": [
                    effort.value for effort in profile.reasoning_efforts
                ],
                "local": profile.local,
                "available": profile.available,
                "cost_weight": profile.cost_weight,
                "latency_weight": profile.latency_weight,
            }
            for profile in sorted(
                self.profiles.values(),
                key=lambda item: CapabilityRegistry.order(
                    item.capability
                ),
            )
        ]

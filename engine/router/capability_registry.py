from __future__ import annotations

import os
from collections.abc import Iterable

from ..schemas import (
    Capability,
    ModelProfile,
    ReasoningEffort,
)

_CAPABILITY_ORDER = [
    Capability.NO_MODEL,
    Capability.QUICK,
    Capability.EXPLORE,
    Capability.BUILD,
    Capability.DEBUG,
    Capability.DEEP,
    Capability.CRITICAL,
]
_DEFAULT_COST_WEIGHT = {
    Capability.NO_MODEL: 0.0,
    Capability.QUICK: 0.20,
    Capability.EXPLORE: 0.25,
    Capability.BUILD: 0.50,
    Capability.DEBUG: 0.70,
    Capability.DEEP: 0.85,
    Capability.CRITICAL: 1.00,
}


class CapabilityRegistry:
    def __init__(
        self,
        overrides: dict[Capability, str] | None = None,
        profiles: dict[Capability, ModelProfile] | None = None,
    ):
        self.overrides = overrides or {}
        self.custom_profiles = profiles or {}
        self._profiles = self._build_profiles()

    @staticmethod
    def _default_efforts(
        capability: Capability,
    ) -> list[ReasoningEffort]:
        if capability in {Capability.QUICK, Capability.EXPLORE}:
            return [
                ReasoningEffort.LOW,
                ReasoningEffort.MEDIUM,
            ]
        if capability == Capability.BUILD:
            return [
                ReasoningEffort.LOW,
                ReasoningEffort.MEDIUM,
                ReasoningEffort.HIGH,
            ]
        return [
            ReasoningEffort.MEDIUM,
            ReasoningEffort.HIGH,
            ReasoningEffort.XHIGH,
            ReasoningEffort.MAX,
        ]

    def _build_profiles(self) -> dict[Capability, ModelProfile]:
        profiles: dict[Capability, ModelProfile] = {}
        for capability in _CAPABILITY_ORDER:
            if capability == Capability.NO_MODEL:
                profiles[capability] = ModelProfile(
                    model_id="deterministic",
                    capability=capability,
                    reasoning_efforts=[ReasoningEffort.MINIMAL],
                    local=True,
                    cost_weight=0.0001,
                    latency_weight=0.1,
                )
                continue

            custom = self.custom_profiles.get(capability)
            if custom is not None:
                if custom.capability != capability:
                    raise ValueError(
                        "custom profile capability key mismatch: "
                        f"{capability.value} vs {custom.capability.value}"
                    )
                profile = custom
            else:
                profile = ModelProfile(
                    model_id="auto",
                    capability=capability,
                    reasoning_efforts=self._default_efforts(capability),
                    cost_weight=_DEFAULT_COST_WEIGHT[capability],
                    latency_weight=(
                        0.5
                        + _CAPABILITY_ORDER.index(capability) * 0.15
                    ),
                )

            override = (
                self.overrides.get(capability)
                or os.getenv(
                    "CASCADE_MODEL_"
                    + capability.value.upper().replace("-", "_")
                )
            )
            if override:
                profile = profile.model_copy(
                    update={"model_id": override}
                )
            profiles[capability] = profile
        return profiles

    def resolve(self, capability: Capability) -> ModelProfile:
        return self._profiles[capability]

    def available(
        self,
        minimum: Capability = Capability.QUICK,
    ) -> list[ModelProfile]:
        start = _CAPABILITY_ORDER.index(minimum)
        return [
            self._profiles[capability]
            for capability in _CAPABILITY_ORDER[start:]
            if self._profiles[capability].available
        ]

    def all(self) -> Iterable[ModelProfile]:
        return self._profiles.values()

    @staticmethod
    def order(capability: Capability) -> int:
        return _CAPABILITY_ORDER.index(capability)

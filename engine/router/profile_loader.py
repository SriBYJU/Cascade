from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..schemas import Capability, ModelProfile, ReasoningEffort


def _validate_profile(profile: ModelProfile) -> None:
    if profile.capability == Capability.NO_MODEL:
        raise ValueError(
            "no-model is reserved for Cascade's deterministic execution tier"
        )
    if not profile.reasoning_efforts:
        raise ValueError(
            f"{profile.capability.value} profile must declare reasoning efforts"
        )
    if len(set(profile.reasoning_efforts)) != len(
        profile.reasoning_efforts
    ):
        raise ValueError(
            f"{profile.capability.value} profile has duplicate reasoning efforts"
        )
    if ReasoningEffort.MINIMAL in profile.reasoning_efforts:
        raise ValueError(
            "minimal reasoning is reserved for deterministic/no-model work"
        )


def parse_profiles(
    raw: object,
) -> dict[Capability, ModelProfile]:
    if not isinstance(raw, list):
        raise ValueError("model_profiles must be a JSON list")

    profiles: dict[Capability, ModelProfile] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each model profile must be a JSON object")
        profile = ModelProfile.model_validate(dict(item))
        _validate_profile(profile)
        if profile.capability in profiles:
            raise ValueError(
                "duplicate model profile for capability: "
                f"{profile.capability.value}"
            )
        profiles[profile.capability] = profile
    return profiles


def load_profiles(
    path: str | Path,
) -> dict[Capability, ModelProfile]:
    source = Path(path)
    try:
        raw: Any = json.loads(source.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid model profile JSON: {source}"
        ) from exc
    return parse_profiles(raw)

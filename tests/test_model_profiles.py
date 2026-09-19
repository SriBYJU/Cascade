import json
from pathlib import Path

import pytest

from engine.config import CascadeConfig
from engine.router.capability_registry import CapabilityRegistry
from engine.router.profile_loader import parse_profiles
from engine.schemas import Capability


def test_example_model_profiles_load():
    root = Path(__file__).parents[1]
    raw = json.loads(
        (root / "examples" / "model-profiles.example.json").read_text()
    )
    profiles = parse_profiles(raw)
    assert profiles[Capability.QUICK].local is True
    assert profiles[Capability.CRITICAL].cost_weight == 1.0


def test_invalid_duplicate_capability_fails_closed():
    with pytest.raises(ValueError):
        parse_profiles(
            [
                {
                    "model_id": "one",
                    "capability": "build",
                    "reasoning_efforts": ["medium"],
                },
                {
                    "model_id": "two",
                    "capability": "build",
                    "reasoning_efforts": ["high"],
                },
            ]
        )


def test_no_model_profile_is_reserved():
    with pytest.raises(ValueError):
        parse_profiles(
            [
                {
                    "model_id": "fake",
                    "capability": "no-model",
                    "reasoning_efforts": ["low"],
                }
            ]
        )


def test_override_changes_model_not_capability():
    profiles = parse_profiles(
        [
            {
                "model_id": "balanced",
                "capability": "build",
                "reasoning_efforts": ["medium"],
            }
        ]
    )
    registry = CapabilityRegistry(
        overrides={Capability.BUILD: "override-model"},
        profiles=profiles,
    )
    resolved = registry.resolve(Capability.BUILD)
    assert resolved.model_id == "override-model"
    assert resolved.capability == Capability.BUILD


def test_config_can_load_inline_model_profiles(tmp_path: Path):
    (tmp_path / ".cascade.json").write_text(
        json.dumps(
            {
                "model_profiles": [
                    {
                        "model_id": "fast",
                        "capability": "quick",
                        "reasoning_efforts": ["low"],
                        "local": True,
                    }
                ]
            }
        )
    )
    config = CascadeConfig.load(tmp_path)
    assert config.model_profiles[Capability.QUICK].model_id == "fast"


def test_profile_file_cannot_escape_repo(tmp_path: Path):
    (tmp_path / ".cascade.json").write_text(
        json.dumps({"model_profiles_file": "../outside.json"})
    )
    with pytest.raises(ValueError):
        CascadeConfig.load(tmp_path)

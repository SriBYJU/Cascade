from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .router.profile_loader import parse_profiles
from .schemas import Capability, ModelProfile


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(slots=True)
class CascadeConfig:
    repo_root: Path
    state_dir: Path
    db_path: Path
    max_concurrent_workers: int = 3
    attempts_per_task: int = 2
    escalations_per_task: int = 2
    command_timeout_seconds: int = 120
    output_cap_chars: int = 20000
    head_token_budget: int = 50000
    total_token_budget: int = 150000
    context_token_budget: int = 30000
    capability_map: dict[Capability, str] = field(default_factory=dict)
    model_profiles: dict[Capability, ModelProfile] = field(
        default_factory=dict
    )
    local_mode: bool = False
    cloud_fallback: bool = True
    trace_content: str = "metadata_only"
    enable_context_firewall: bool = True
    enable_prompt_cache_affinity: bool = True
    enable_parallel_dag: bool = True

    @classmethod
    def load(cls, repo_root: str | Path = ".") -> "CascadeConfig":
        root = Path(repo_root).resolve()
        state_dir = root / ".cascade"
        state_dir.mkdir(parents=True, exist_ok=True)
        mapping: dict[Capability, str] = {}
        for capability in Capability:
            env = os.getenv(
                f"CASCADE_MODEL_{capability.value.upper().replace('-', '_')}"
            )
            if env:
                mapping[capability] = env

        config = cls(
            repo_root=root,
            state_dir=state_dir,
            db_path=state_dir / "cascade.sqlite3",
            max_concurrent_workers=int(os.getenv("CASCADE_MAX_WORKERS", "3")),
            capability_map=mapping,
            local_mode=_env_flag("CASCADE_LOCAL_MODE", False),
            cloud_fallback=_env_flag("CASCADE_CLOUD_FALLBACK", True),
            enable_context_firewall=_env_flag(
                "CASCADE_CONTEXT_FIREWALL", True
            ),
            enable_prompt_cache_affinity=_env_flag(
                "CASCADE_PROMPT_CACHE_AFFINITY", True
            ),
            enable_parallel_dag=_env_flag("CASCADE_PARALLEL_DAG", True),
        )

        path = root / ".cascade.json"
        if not path.exists():
            return config
        raw: object = json.loads(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError(".cascade.json must contain a JSON object")
        data: dict[str, Any] = raw
        scalar_keys = (
            "max_concurrent_workers",
            "attempts_per_task",
            "escalations_per_task",
            "command_timeout_seconds",
            "output_cap_chars",
            "head_token_budget",
            "total_token_budget",
            "context_token_budget",
            "local_mode",
            "cloud_fallback",
            "trace_content",
            "enable_context_firewall",
            "enable_prompt_cache_affinity",
            "enable_parallel_dag",
        )
        for key in scalar_keys:
            if key in data:
                setattr(config, key, data[key])

        if config.trace_content not in {"metadata_only", "full"}:
            raise ValueError(
                "trace_content must be 'metadata_only' or 'full'"
            )

        capability_map = data.get("capability_map", {})
        if not isinstance(capability_map, dict):
            raise ValueError("capability_map must be an object")
        for key, value in capability_map.items():
            config.capability_map[Capability(str(key))] = str(value)

        model_profiles = data.get("model_profiles")
        profiles_file = data.get("model_profiles_file")
        if model_profiles is not None and profiles_file is not None:
            raise ValueError(
                "use model_profiles or model_profiles_file, not both"
            )
        if model_profiles is not None:
            config.model_profiles = parse_profiles(model_profiles)
        if profiles_file is not None:
            rel = Path(str(profiles_file))
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(
                    "model_profiles_file must remain inside the repository"
                )
            profile_path = (root / rel).resolve()
            if not profile_path.is_relative_to(root):
                raise ValueError(
                    "model_profiles_file escaped repository root"
                )
            raw_profiles: object = json.loads(profile_path.read_text())
            config.model_profiles = parse_profiles(raw_profiles)
        return config

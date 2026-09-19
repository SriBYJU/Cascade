from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .adapters.codex import CodexAdapter
from .adapters.hardware import detect_hardware
from .adapters.ollama import OllamaAdapter
from .adapters.vllm import VLLMAdapter
from .validation.discover import discover_validators


def _capture(command: list[str], timeout: int = 10) -> tuple[int, str]:
    if not shutil.which(command[0]):
        return 127, ""
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 126, ""
    return proc.returncode, (proc.stdout or proc.stderr)


def _version(command: list[str]) -> str | None:
    code, output = _capture(command)
    if code != 0:
        return None
    lines = output.strip().splitlines()
    return lines[0] if lines else None


def _codex_exec_probe() -> dict[str, Any]:
    if not shutil.which("codex"):
        return {
            "available": False,
            "compatible": False,
            "flags": {},
        }

    code, output = _capture(["codex", "exec", "--help"])
    flags = {
        "json": "--json" in output,
        "sandbox": "--sandbox" in output,
        "model": "--model" in output,
        "config": "--config" in output,
    }
    compatible = code == 0 and all(flags.values())
    return {
        "available": True,
        "compatible": compatible,
        "flags": flags,
        "help_exit_code": code,
    }


def _plugin_probe(root: Path) -> dict[str, Any]:
    portable_path = root / "plugin.json"
    compat_path = root / ".codex-plugin" / "plugin.json"
    result: dict[str, Any] = {
        "portable_manifest": str(portable_path)
        if portable_path.exists()
        else None,
        "compat_manifest": str(compat_path)
        if compat_path.exists()
        else None,
        "portable_valid": False,
        "compat_valid": False,
        "identity_match": False,
    }

    portable: dict[str, Any] | None = None
    compat: dict[str, Any] | None = None
    try:
        if portable_path.exists():
            raw = json.loads(portable_path.read_text())
            if isinstance(raw, dict):
                portable = raw
                result["portable_valid"] = (
                    raw.get("$schema")
                    == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
                    and raw.get("name") == "cascade"
                    and isinstance(raw.get("version"), str)
                )
    except (OSError, json.JSONDecodeError):
        pass

    try:
        if compat_path.exists():
            raw = json.loads(compat_path.read_text())
            if isinstance(raw, dict):
                compat = raw
                result["compat_valid"] = (
                    raw.get("name") == "cascade"
                    and isinstance(raw.get("version"), str)
                )
    except (OSError, json.JSONDecodeError):
        pass

    if portable and compat:
        result["identity_match"] = (
            portable.get("name") == compat.get("name")
            and portable.get("version") == compat.get("version")
            and portable.get("description") == compat.get("description")
        )
    return result


def _agent_probe(root: Path) -> dict[str, Any]:
    agent_dir = root / ".codex" / "agents"
    names = sorted(path.stem for path in agent_dir.glob("*.toml"))
    required = {
        "scout",
        "builder",
        "debugger",
        "reviewer",
        "architect",
        "integrator",
    }
    return {
        "directory": str(agent_dir) if agent_dir.exists() else None,
        "agents": names,
        "required_agents_present": required <= set(names),
        "missing_agents": sorted(required - set(names)),
    }


def doctor(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    codex = CodexAdapter()
    ollama = OllamaAdapter()
    vllm = VLLMAdapter()
    validators = discover_validators(root)

    codex_probe = _codex_exec_probe()
    plugin_probe = _plugin_probe(root)
    agent_probe = _agent_probe(root)
    warnings: list[str] = []

    if codex.available() and not codex_probe["compatible"]:
        warnings.append(
            "Codex is installed but required exec flags were not all detected."
        )
    if not plugin_probe["portable_valid"]:
        warnings.append("portable plugin.json is missing or invalid")
    if not plugin_probe["compat_valid"]:
        warnings.append(
            ".codex-plugin/plugin.json compatibility manifest is missing or invalid"
        )
    if not plugin_probe["identity_match"]:
        warnings.append("portable and compatibility plugin identities differ")
    if not agent_probe["required_agents_present"]:
        warnings.append("one or more required Cascade agents are missing")

    local_ready = ollama.available() or vllm.available()
    return {
        "repo_root": str(root),
        "python": platform.python_version(),
        "git": _version(["git", "--version"]),
        "codex": codex.version(),
        "codex_available": codex.available(),
        "codex_exec": codex_probe,
        "ollama_available": ollama.available(),
        "ollama_models": ollama.models() if ollama.available() else [],
        "ollama_diagnostics": (
            ollama.diagnostics() if ollama.available() else None
        ),
        "vllm_available": vllm.available(),
        "vllm_models": vllm.models() if vllm.available() else [],
        "vllm_diagnostics": (
            vllm.diagnostics() if vllm.available() else None
        ),
        "local_model_ready": local_ready,
        "hardware": detect_hardware().to_dict(),
        "validators": [
            {
                "name": validator.name,
                "command": list(validator.command),
                "category": validator.category,
                "cwd": validator.cwd,
            }
            for validator in validators
        ],
        "project_codex_config": (
            str(root / ".codex" / "config.toml")
            if (root / ".codex" / "config.toml").exists()
            else None
        ),
        "plugin": plugin_probe,
        "agents": agent_probe,
        "release_preflight": {
            "python_3_11_plus": tuple(
                int(part)
                for part in platform.python_version_tuple()[:2]
            )
            >= (3, 11),
            "git_available": _version(["git", "--version"]) is not None,
            "plugin_layout_ready": bool(
                plugin_probe["portable_valid"]
                and plugin_probe["compat_valid"]
                and plugin_probe["identity_match"]
            ),
            "agents_ready": bool(agent_probe["required_agents_present"]),
            "codex_runtime_ready": bool(codex_probe["compatible"]),
        },
        "warnings": warnings,
    }

from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_AGENTS = {
    "scout",
    "builder",
    "debugger",
    "reviewer",
    "architect",
    "integrator",
}


def load_json(path: Path) -> dict:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return raw


def main() -> int:
    portable = load_json(ROOT / "plugin.json")
    compat = load_json(ROOT / ".codex-plugin" / "plugin.json")

    assert portable["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    assert portable["name"] == compat["name"] == "cascade"
    assert portable["version"] == compat["version"]
    assert portable["description"] == compat["description"]

    skills_root = ROOT / "skills"
    skills = sorted(skills_root.glob("*/SKILL.md"))
    assert skills, "portable plugin must expose at least one skill"

    agent_dir = ROOT / ".codex" / "agents"
    found: set[str] = set()
    for path in agent_dir.glob("*.toml"):
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        for key in ("name", "description", "developer_instructions"):
            value = data.get(key)
            assert isinstance(value, str) and value.strip(), (
                f"{path}: missing required {key}"
            )
        found.add(str(data["name"]))
    assert REQUIRED_AGENTS <= found, (
        f"missing Cascade agents: {sorted(REQUIRED_AGENTS - found)}"
    )

    marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text())
    assert marketplace["name"] == "cascade-local"
    assert marketplace["interface"]["displayName"] == "Cascade Local"
    entries = marketplace.get("plugins", [])
    assert isinstance(entries, list) and len(entries) == 1
    entry = entries[0]
    assert entry["name"] == "cascade"
    assert entry["source"] == {"source": "local", "path": "./"}
    assert entry["policy"]["installation"] in {
        "AVAILABLE",
        "INSTALLED_BY_DEFAULT",
        "NOT_AVAILABLE",
    }
    assert entry["policy"]["authentication"]
    assert entry["category"] == "Productivity"

    config_path = ROOT / ".codex" / "config.toml"
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    assert config.get("agents", {}).get("enabled") is True
    assert (
        config.get("agents", {}).get(
            "max_concurrent_threads_per_session"
        )
        == 3
    )
    assert config.get("features", {}).get("goals") is True
    assert "goals" not in {
        key
        for key in config
        if key != "features"
    }, "undocumented top-level [goals] section must not return"

    print(
        "Cascade plugin layout OK: "
        f"{len(skills)} skill(s), {len(found)} agent(s), marketplace OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

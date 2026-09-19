import json
from pathlib import Path


def test_portable_plugin_manifest_is_canonical():
    root = Path(__file__).parents[1]
    data = json.loads((root / "plugin.json").read_text())
    assert data["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    assert data["name"] == "cascade"
    assert data["version"].count(".") == 2
    assert data["author"]["name"]
    interface = data["extensions"]["com.openai"]["interface"]
    assert interface["displayName"] == "Cascade"
    assert (root / "skills").exists()


def test_compatibility_manifest_matches_portable_identity():
    root = Path(__file__).parents[1]
    portable = json.loads((root / "plugin.json").read_text())
    compat = json.loads((root / ".codex-plugin" / "plugin.json").read_text())
    assert compat["name"] == portable["name"]
    assert compat["version"] == portable["version"]
    assert compat["description"] == portable["description"]
    assert compat["interface"]["displayName"] == (
        portable["extensions"]["com.openai"]["interface"]["displayName"]
    )
    assert (root / compat["skills"].removeprefix("./")).exists()

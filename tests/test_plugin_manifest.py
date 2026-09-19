import json
from pathlib import Path


def test_plugin_manifest_has_current_required_basics():
    root = Path(__file__).parents[1]
    data = json.loads((root / ".codex-plugin" / "plugin.json").read_text())
    assert data["name"] == "cascade"
    assert data["version"].count(".") == 2
    assert data["author"]["name"]
    assert data["interface"]["displayName"] == "Cascade"
    assert (root / data["skills"].removeprefix("./")).exists()

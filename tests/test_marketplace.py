import json
from pathlib import Path


def test_repository_marketplace_points_to_plugin_root():
    root = Path(__file__).parents[1]
    data = json.loads(
        (root / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    assert data["name"] == "cascade-local"
    assert data["interface"]["displayName"] == "Cascade Local"
    assert len(data["plugins"]) == 1
    entry = data["plugins"][0]
    assert entry["name"] == "cascade-codex"
    assert entry["source"] == {
        "source": "local",
        "path": "./",
    }
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"
    assert (root / "plugin.json").exists()
    assert (root / "skills" / "optimizer" / "SKILL.md").exists()

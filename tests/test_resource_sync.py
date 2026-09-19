from pathlib import Path


def test_packaged_agents_match_repository_agents():
    root = Path(__file__).parents[1]
    packaged = root / "engine" / "resources" / "agents"
    source = root / ".codex" / "agents"
    for path in source.glob("*.toml"):
        assert (packaged / path.name).read_text() == path.read_text()


def test_packaged_skill_matches_plugin_skill():
    root = Path(__file__).parents[1]
    packaged = root / "engine" / "resources" / "skill"
    source = root / "skills" / "optimizer"
    assert (packaged / "SKILL.md").read_text() == (
        source / "SKILL.md"
    ).read_text()
    for path in (source / "references").glob("*.md"):
        assert (
            packaged / "references" / path.name
        ).read_text() == path.read_text()

import json
from pathlib import Path

import pytest

from engine.project_install import (
    install_project,
    project_status,
    uninstall_project,
)


def test_project_install_and_clean_uninstall(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    installed = install_project(repo)
    assert installed["status"] == "installed"
    assert (
        repo
        / ".agents"
        / "skills"
        / "cascade-optimizer"
        / "SKILL.md"
    ).exists()
    agents = sorted((repo / ".codex" / "agents").glob("*.toml"))
    assert len(agents) == 6
    assert project_status(repo)["status"] == "installed"

    removed = uninstall_project(repo)
    assert removed["status"] == "uninstalled"
    assert not (
        repo
        / ".agents"
        / "skills"
        / "cascade-optimizer"
        / "SKILL.md"
    ).exists()
    assert not any((repo / ".codex" / "agents").glob("*.toml"))


def test_install_refuses_to_overwrite_project_files(tmp_path: Path):
    repo = tmp_path / "repo"
    destination = repo / ".codex" / "agents" / "scout.toml"
    destination.parent.mkdir(parents=True)
    destination.write_text("user-owned\n")

    try:
        install_project(repo)
    except FileExistsError as exc:
        assert "scout.toml" in str(exc)
    else:
        raise AssertionError("installer overwrote a user-owned file")

    # The conflict is intentionally late in the resource list. Preflight
    # must prevent earlier managed files from being partially installed.
    assert not (
        repo / ".codex" / "agents" / "architect.toml"
    ).exists()
    assert not (
        repo / ".agents" / "skills" / "cascade-optimizer"
    ).exists()


def test_overwrite_restores_backup_on_uninstall(tmp_path: Path):
    repo = tmp_path / "repo"
    destination = repo / ".codex" / "agents" / "scout.toml"
    destination.parent.mkdir(parents=True)
    destination.write_text("user-owned\n")

    install_project(repo, overwrite=True)
    assert destination.read_text() != "user-owned\n"
    uninstall_project(repo)
    assert destination.read_text() == "user-owned\n"


def test_uninstall_preserves_modified_managed_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    install_project(repo)
    destination = repo / ".codex" / "agents" / "builder.toml"
    destination.write_text("locally modified\n")

    result = uninstall_project(repo)
    assert result["status"] == "partial"
    assert destination.read_text() == "locally modified\n"
    assert project_status(repo)["status"] == "drifted"


def test_dry_run_makes_no_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = install_project(repo, dry_run=True)
    assert result["status"] == "dry-run"
    assert not (repo / ".codex").exists()
    assert not (repo / ".agents").exists()
    assert not (repo / ".cascade").exists()



def test_receipt_path_traversal_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep\n")
    state = repo / ".cascade"
    state.mkdir()
    (state / "project-install.json").write_text(
        json.dumps(
            {
                "version": 1,
                "files": [
                    {
                        "path": "../outside.txt",
                        "sha256": "0" * 64,
                        "created": True,
                        "backup": None,
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError):
        uninstall_project(repo)

    assert outside.read_text() == "keep\n"


def test_receipt_backup_escape_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    state = repo / ".cascade"
    state.mkdir()
    (state / "project-install.json").write_text(
        json.dumps(
            {
                "version": 1,
                "files": [
                    {
                        "path": ".codex/agents/scout.toml",
                        "sha256": "0" * 64,
                        "created": True,
                        "backup": "../outside.bak",
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError):
        project_status(repo)


def test_install_rejects_symlinked_managed_directory(tmp_path: Path):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    try:
        (repo / ".codex").symlink_to(
            outside,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("symlink creation unavailable on this platform")

    with pytest.raises(ValueError):
        install_project(repo)

    assert list(outside.iterdir()) == []

import subprocess
from pathlib import Path

from engine.workspace.scope import enforce_scope
from engine.workspace.worktree import WorktreeManager


def _git(repo: Path, *args: str):
    return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def test_two_writers_get_isolated_worktrees(tmp_path: Path):
    repo = _repo(tmp_path)
    m = WorktreeManager(repo, state_dir=tmp_path / "state")
    a = m.create("a")
    b = m.create("b")
    try:
        assert a.path != b.path
        (a.path / "a.txt").write_text("writer-a\n")
        assert (b.path / "a.txt").read_text() == "base\n"
    finally:
        m.cleanup(a, force=True)
        m.cleanup(b, force=True)


def test_forbidden_path_scope_is_blocked():
    unexpected = enforce_scope(["src/a.py", "migrations/001.sql"], ["src/**"], ["migrations/**"])
    assert unexpected == ["migrations/001.sql"]

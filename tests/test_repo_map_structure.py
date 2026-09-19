from pathlib import Path
import subprocess

from engine.context.repo_map import build_repo_map
from engine.context.retrieval import rank_files


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth").mkdir()
    (repo / "tests").mkdir()
    (repo / "auth" / "__init__.py").write_text("")
    (repo / "auth" / "session.py").write_text(
        "def refresh_session():\n    return 'ok'\n"
    )
    (repo / "service.py").write_text(
        "from auth.session import refresh_session\n\n"
        "def run():\n    return refresh_session()\n"
    )
    (repo / "tests" / "test_session.py").write_text(
        "from auth.session import refresh_session\n\n"
        "def test_refresh():\n    assert refresh_session() == 'ok'\n"
    )
    _git(repo, "init")
    _git(repo, "config", "user.email", "map@example.com")
    _git(repo, "config", "user.name", "Map")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "fixture")
    return repo


def test_repo_map_links_imports_tests_and_reverse_edges(tmp_path: Path):
    repo = _repo(tmp_path)
    mapped = build_repo_map(repo, use_cache=False)
    by_path = {file.path: file for file in mapped.files}

    session = by_path["auth/session.py"]
    service = by_path["service.py"]
    test = by_path["tests/test_session.py"]

    assert service.references == ["auth/session.py"]
    assert test.references == ["auth/session.py"]
    assert test.test_targets == ["auth/session.py"]
    assert set(session.referenced_by) == {
        "service.py",
        "tests/test_session.py",
    }
    assert session.package == "auth"


def test_repo_map_cache_reuses_same_fingerprint(tmp_path: Path):
    repo = _repo(tmp_path)
    first = build_repo_map(repo, use_cache=True)
    cache = repo / ".cascade" / "repo-map.json"
    assert cache.exists()
    second = build_repo_map(repo, use_cache=True)
    assert second.fingerprint == first.fingerprint
    assert [file.path for file in second.files] == [
        file.path for file in first.files
    ]


def test_structural_ranking_can_surface_related_implementation(
    tmp_path: Path,
):
    repo = _repo(tmp_path)
    mapped = build_repo_map(repo, use_cache=False)
    ranked = rank_files(mapped, "test session bug", limit=3)
    paths = {file.path for file in ranked}
    assert "auth/session.py" in paths
    assert "tests/test_session.py" in paths

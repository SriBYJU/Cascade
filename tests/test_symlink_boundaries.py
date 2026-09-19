from pathlib import Path

import pytest

from engine.context.repo_map import build_repo_map
from engine.context.retrieval import collect_broad_evidence, collect_evidence
from engine.context.safe_path import safe_repo_path
from engine.validation.security import scan_files


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")


def test_repo_map_never_indexes_symlinked_external_file(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET_OUTSIDE_VALUE = 'do-not-read'\n")
    _symlink(repo / "leak.py", outside)

    mapped = build_repo_map(repo, use_cache=False)

    assert "leak.py" not in {file.path for file in mapped.files}
    assert safe_repo_path(repo, "leak.py", require_file=True) is None


def test_context_retrieval_never_reads_external_symlink(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "safe.py").write_text("def safe():\n    return True\n")
    outside = tmp_path / "outside.md"
    outside.write_text("private-token-never-forward\n")
    _symlink(repo / "private.md", outside)

    mapped = build_repo_map(repo, use_cache=False)
    narrow = collect_evidence(mapped, "private token")
    broad = collect_broad_evidence(mapped, "private token")

    assert all(ref.file != "private.md" for ref in [*narrow, *broad])


def test_secret_scanner_refuses_external_symlink(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text('api_key="12345678901234567890"\n')
    _symlink(repo / "linked.txt", outside)

    assert scan_files(repo, ["linked.txt"]) == {}

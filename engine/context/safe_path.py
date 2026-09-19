from __future__ import annotations

from pathlib import Path


def safe_repo_path(
    root: str | Path,
    relative: str | Path,
    *,
    require_file: bool = False,
) -> Path | None:
    """Return a repository-contained non-symlink path, or None."""

    repo = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    candidate = repo / rel

    current = repo
    for part in rel.parts:
        current = current / part
        try:
            if current.is_symlink():
                return None
        except OSError:
            return None

    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    if not resolved.is_relative_to(repo):
        return None
    if require_file:
        try:
            if not candidate.is_file():
                return None
        except OSError:
            return None
    return candidate

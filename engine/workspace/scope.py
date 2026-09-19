from __future__ import annotations

import fnmatch
from pathlib import Path

from ..tools.runner import run_command

TRANSIENT_PATTERNS = (
    ".pytest_cache/**",
    "**/.pytest_cache/**",
    "__pycache__/**",
    "**/__pycache__/**",
    ".mypy_cache/**",
    "**/.mypy_cache/**",
    ".ruff_cache/**",
    "**/.ruff_cache/**",
    ".coverage",
    "htmlcov/**",
)


def _transient(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        fnmatch.fnmatch(normalized, pattern)
        for pattern in TRANSIENT_PATTERNS
    )


def list_changed_files(
    repo_root: str | Path,
    base_ref: str = "HEAD",
) -> list[str]:
    result = run_command(
        ["git", "diff", "--name-only", base_ref],
        repo_root,
    )
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or result.stdout)
    untracked = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"],
        repo_root,
    )
    files = {
        item.strip()
        for item in result.stdout.splitlines()
        if item.strip() and not _transient(item.strip())
    }
    if untracked.exit_code == 0:
        files.update(
            item.strip()
            for item in untracked.stdout.splitlines()
            if item.strip() and not _transient(item.strip())
        )
    return sorted(files)


def is_allowed(
    path: str,
    allowed_patterns: list[str],
    forbidden_patterns: list[str],
) -> bool:
    if any(
        fnmatch.fnmatch(path, pattern)
        for pattern in forbidden_patterns
    ):
        return False
    return any(
        pattern == "**" or fnmatch.fnmatch(path, pattern)
        for pattern in allowed_patterns
    )


def enforce_scope(
    changed: list[str],
    allowed_patterns: list[str],
    forbidden_patterns: list[str],
) -> list[str]:
    return [
        path
        for path in changed
        if not is_allowed(
            path,
            allowed_patterns,
            forbidden_patterns,
        )
    ]

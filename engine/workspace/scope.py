from __future__ import annotations

import fnmatch
from pathlib import Path

from ..tools.runner import run_command


def list_changed_files(repo_root: str | Path, base_ref: str = "HEAD") -> list[str]:
    result = run_command(["git", "diff", "--name-only", base_ref], repo_root)
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or result.stdout)
    untracked = run_command(["git", "ls-files", "--others", "--exclude-standard"], repo_root)
    files = {x.strip() for x in result.stdout.splitlines() if x.strip()}
    if untracked.exit_code == 0:
        files.update(x.strip() for x in untracked.stdout.splitlines() if x.strip())
    return sorted(files)


def is_allowed(path: str, allowed_patterns: list[str], forbidden_patterns: list[str]) -> bool:
    if any(fnmatch.fnmatch(path, pat) for pat in forbidden_patterns):
        return False
    return any(pat == "**" or fnmatch.fnmatch(path, pat) for pat in allowed_patterns)


def enforce_scope(changed: list[str], allowed_patterns: list[str], forbidden_patterns: list[str]) -> list[str]:
    return [path for path in changed if not is_allowed(path, allowed_patterns, forbidden_patterns)]

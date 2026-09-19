from __future__ import annotations

from pathlib import Path

from ..tools.runner import run_command


def merge_base(repo_root: str | Path, left: str, right: str) -> str | None:
    result = run_command(["git", "merge-base", left, right], repo_root)
    return result.stdout.strip() if result.exit_code == 0 else None


def changed_files(repo_root: str | Path, base: str, head: str) -> list[str]:
    result = run_command(["git", "diff", "--name-only", f"{base}...{head}"], repo_root)
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def dry_run_conflict(repo_root: str | Path, left: str, right: str) -> tuple[bool, str]:
    base = merge_base(repo_root, left, right)
    if not base:
        return True, "unable to determine merge base"
    result = run_command(["git", "merge-tree", base, left, right], repo_root, timeout_seconds=60)
    text = f"{result.stdout}\n{result.stderr}"
    conflict_markers = ["<<<<<<<", "changed in both", "CONFLICT"]
    has_conflict = result.exit_code not in (0, None) or any(marker in text for marker in conflict_markers)
    return has_conflict, text

from __future__ import annotations

from pathlib import Path

from ..tools.runner import run_command


def rollback_worktree(path: str | Path, base_ref: str = "HEAD") -> None:
    reset = run_command(["git", "reset", "--hard", base_ref], path, timeout_seconds=30)
    if reset.exit_code != 0:
        raise RuntimeError(reset.stderr or reset.stdout)
    clean = run_command(["git", "clean", "-fd"], path, timeout_seconds=30)
    if clean.exit_code != 0:
        raise RuntimeError(clean.stderr or clean.stdout)

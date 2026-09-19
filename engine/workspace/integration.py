from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..schemas import ValidationResult
from ..tools.runner import run_command
from ..validation.pipeline import validate_progressively
from .conflicts import dry_run_conflict
from .worktree import Worktree


@dataclass(slots=True)
class IntegrationResult:
    passed: bool
    merged: bool
    commit_sha: str | None
    validation: ValidationResult | None
    reason: str


def _git(root: str | Path, *args: str) -> str:
    result = run_command(["git", *args], root, timeout_seconds=90)
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def integrate_verified_worktree(
    repo_root: str | Path,
    worktree: Worktree,
    *,
    task_id: str,
    risk: str,
) -> IntegrationResult:
    """Commit a gated worktree and cherry-pick it into a clean integration checkout.

    This is deliberately opt-in. The caller must have already run the merge/scope gate.
    The integration checkout must be clean so rollback can safely restore the exact prior
    HEAD without destroying unrelated user work.
    """
    repo_root = Path(repo_root).resolve()
    dirty = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        return IntegrationResult(False, False, None, None, "integration checkout is dirty")

    original_head = _git(repo_root, "rev-parse", "HEAD")
    worktree_status = _git(worktree.path, "status", "--porcelain=v1", "--untracked-files=all")
    if not worktree_status:
        validation = validate_progressively(repo_root, risk=risk, changed_files=[])
        return IntegrationResult(validation.passed, False, original_head, validation, "no changes to integrate")

    _git(worktree.path, "add", "-A")
    commit = run_command(
        [
            "git", "-c", "user.name=Cascade", "-c", "user.email=cascade@local",
            "commit", "-m", f"Cascade: {task_id}",
        ],
        worktree.path,
        timeout_seconds=90,
    )
    if commit.exit_code != 0:
        return IntegrationResult(False, False, None, None, commit.stderr or commit.stdout)
    commit_sha = _git(worktree.path, "rev-parse", "HEAD")

    has_conflict, details = dry_run_conflict(repo_root, original_head, commit_sha)
    if has_conflict:
        return IntegrationResult(False, False, commit_sha, None, f"dry-run merge conflict: {details[-2000:]}")

    cherry = run_command(["git", "cherry-pick", commit_sha], repo_root, timeout_seconds=120)
    if cherry.exit_code != 0:
        run_command(["git", "cherry-pick", "--abort"], repo_root, timeout_seconds=30)
        return IntegrationResult(False, False, commit_sha, None, cherry.stderr or cherry.stdout)

    validation = validate_progressively(repo_root, risk=risk)
    if not validation.passed:
        run_command(["git", "reset", "--hard", original_head], repo_root, timeout_seconds=60)
        return IntegrationResult(False, False, commit_sha, validation, "integration validation failed; rolled back")
    return IntegrationResult(True, True, commit_sha, validation, "merged and integration validation passed")

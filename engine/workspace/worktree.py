from __future__ import annotations

import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from ..schemas import CommandResult
from ..tools.runner import run_command


@dataclass(slots=True)
class Worktree:
    task_id: str
    path: Path
    branch: str
    base_ref: str


_LOCKS_GUARD = threading.Lock()
_REPO_LOCKS: dict[str, threading.RLock] = {}


def _repo_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _REPO_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _REPO_LOCKS[key] = lock
        return lock


class WorktreeManager:
    def __init__(self, repo_root: str | Path, *, state_dir: str | Path | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.state_dir = Path(state_dir).resolve() if state_dir else self.repo_root / ".cascade"
        if self.state_dir.is_relative_to(self.repo_root):
            self.worktrees_dir = (
                self.repo_root.parent
                / f".{self.repo_root.name}.cascade-worktrees"
            )
        else:
            self.worktrees_dir = self.state_dir / "worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
        return value[:80] or "task"

    def create(self, task_id: str, base_ref: str = "HEAD") -> Worktree:
        slug = self._slug(task_id)
        path = self.worktrees_dir / slug
        branch = f"cascade/{slug}"
        if path.exists():
            raise FileExistsError(f"worktree already exists: {path}")
        with _repo_lock(self.repo_root):
            result = run_command(
                ["git", "worktree", "add", "-b", branch, str(path), base_ref],
                self.repo_root,
                timeout_seconds=60,
            )
            if result.exit_code != 0:
                raise RuntimeError(
                    "failed to create worktree: "
                    f"{result.stderr or result.stdout}"
                )
            self._verify(path, branch)
        return Worktree(task_id=task_id, path=path, branch=branch, base_ref=base_ref)

    def _verify(self, path: Path, expected_branch: str) -> None:
        top = run_command(["git", "rev-parse", "--show-toplevel"], path)
        branch = run_command(["git", "branch", "--show-current"], path)
        if top.exit_code != 0 or Path(top.stdout.strip()).resolve() != path.resolve():
            raise RuntimeError("worktree start gate failed: unexpected git root")
        if branch.exit_code != 0 or branch.stdout.strip() != expected_branch:
            raise RuntimeError("worktree start gate failed: unexpected branch")

    def status(self, worktree: Worktree) -> CommandResult:
        return run_command(["git", "status", "--porcelain=v1", "--untracked-files=all"], worktree.path)

    def cleanup(self, worktree: Worktree, *, delete_branch: bool = True, force: bool = False) -> None:
        args = ["git", "worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree.path))
        with _repo_lock(self.repo_root):
            result = run_command(
                args,
                self.repo_root,
                timeout_seconds=60,
            )
            if result.exit_code != 0 and worktree.path.exists():
                raise RuntimeError(
                    "failed to remove worktree: "
                    f"{result.stderr or result.stdout}"
                )
            if delete_branch:
                run_command(
                    ["git", "branch", "-D", worktree.branch],
                    self.repo_root,
                    timeout_seconds=30,
                )

    def prune(self) -> None:
        with _repo_lock(self.repo_root):
            run_command(["git", "worktree", "prune"], self.repo_root)
            children = (
                list(self.worktrees_dir.iterdir())
                if self.worktrees_dir.exists()
                else []
            )
            for child in children:
                if child.is_dir() and not (child / ".git").exists():
                    shutil.rmtree(child, ignore_errors=True)

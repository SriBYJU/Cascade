from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..schemas import ValidationResult
from ..validation.pipeline import validate_progressively
from .scope import enforce_scope, list_changed_files


@dataclass(slots=True)
class MergeGateResult:
    passed: bool
    validation: ValidationResult
    changed_files: list[str]
    unexpected_files: list[str]
    reason: str


def merge_gate(
    worktree_path: str | Path,
    *,
    base_ref: str,
    allowed_paths: list[str],
    forbidden_paths: list[str],
    risk: str = "medium",
) -> MergeGateResult:
    changed = list_changed_files(worktree_path, base_ref)
    unexpected = enforce_scope(changed, allowed_paths, forbidden_paths)
    validation = validate_progressively(worktree_path, risk=risk, changed_files=changed)
    passed = not unexpected and validation.passed
    reason = "pass" if passed else ("scope violation" if unexpected else "validation failed")
    return MergeGateResult(passed, validation, changed, unexpected, reason)

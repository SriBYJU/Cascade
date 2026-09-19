from __future__ import annotations

from pathlib import Path

from ..schemas import ValidationCheck
from .discover import discover_validators
from .tests import run_validator


def run_lint(root: str | Path) -> list[ValidationCheck]:
    return [run_validator(v, root) for v in discover_validators(root) if v.category == "lint"]

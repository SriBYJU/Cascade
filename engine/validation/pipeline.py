from __future__ import annotations

from pathlib import Path

from ..schemas import RiskLevel, ValidationCheck, ValidationResult
from .discover import discover_validators
from .security import scan_files
from .tests import run_validator

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _selected_categories(risk: str) -> set[str]:
    level = RISK_ORDER.get(risk, 1)
    cats = {"parser", "tests"}
    if level >= 1:
        cats |= {"lint", "types"}
    return cats


def validate_progressively(root: str | Path, *, risk: str = "medium", changed_files: list[str] | None = None) -> ValidationResult:
    root = Path(root)
    specs = discover_validators(root)
    categories = _selected_categories(risk)
    checks: list[ValidationCheck] = []
    priority = {"parser": 0, "types": 1, "lint": 2, "tests": 3}
    for spec in sorted((s for s in specs if s.category in categories), key=lambda s: priority.get(s.category, 9)):
        check = run_validator(spec, root)
        checks.append(check)
        if not check.passed and spec.category == "parser":
            break
    changed_files = changed_files or []
    secret_findings = scan_files(root, changed_files)
    if secret_findings:
        checks.append(ValidationCheck(
            name="secret-scan", command=[], passed=False, stdout="",
            stderr=f"potential secret patterns in: {sorted(secret_findings)}",
        ))
    passed = bool(checks) and all(c.passed for c in checks)
    if not specs:
        passed = False
        checks.append(ValidationCheck(name="validator-discovery", command=[], passed=False, stderr="no deterministic validators discovered"))
    return ValidationResult(
        passed=passed,
        risk=RiskLevel(risk if risk in RISK_ORDER else "medium"),
        checks=checks,
        changed_files=changed_files,
    )

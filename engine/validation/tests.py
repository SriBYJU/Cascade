from __future__ import annotations

from pathlib import Path

from ..schemas import ValidationCheck
from ..tools.runner import run_command
from .discover import ValidatorSpec


def run_validator(spec: ValidatorSpec, root: str | Path, *, timeout_seconds: int = 180, output_cap_chars: int = 12000) -> ValidationCheck:
    cwd = Path(root) / spec.cwd
    result = run_command(
        spec.command,
        cwd,
        timeout_seconds=timeout_seconds,
        output_cap_chars=output_cap_chars,
    )
    return ValidationCheck(
        name=spec.name,
        command=list(spec.command),
        passed=result.exit_code == 0 and not result.timed_out,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
    )

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

from ..schemas import CommandResult


def _cap(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    half = max(1, limit // 2)
    return text[:half] + "\n...<truncated>...\n" + text[-half:], True


def _resolve_command(command: Sequence[str]) -> list[str]:
    resolved = list(command)
    if (
        resolved[0] in {"python", "python3"}
        and Path(sys.executable).is_file()
    ):
        resolved[0] = sys.executable
    return resolved


def run_command(
    command: Sequence[str],
    cwd: str | Path,
    *,
    timeout_seconds: float = 120,
    output_cap_chars: int = 20000,
    env: Mapping[str, str] | None = None,
    inherit_env: bool = True,
) -> CommandResult:
    if not command:
        raise ValueError("command must not be empty")
    resolved_command = _resolve_command(command)
    start = time.monotonic()
    merged_env = os.environ.copy() if inherit_env else {}
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            resolved_command,
            cwd=str(cwd),
            env=merged_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        out, trunc1 = _cap(proc.stdout or "", output_cap_chars)
        err, trunc2 = _cap(proc.stderr or "", output_cap_chars)
        return CommandResult(
            command=resolved_command,
            cwd=str(Path(cwd).resolve()),
            exit_code=proc.returncode,
            stdout=out,
            stderr=err,
            duration_ms=int((time.monotonic() - start) * 1000),
            timed_out=False,
            truncated=trunc1 or trunc2,
        )
    except subprocess.TimeoutExpired as exc:
        out, trunc1 = _cap((exc.stdout or "") if isinstance(exc.stdout, str) else "", output_cap_chars)
        err, trunc2 = _cap((exc.stderr or "") if isinstance(exc.stderr, str) else "", output_cap_chars)
        return CommandResult(
            command=resolved_command,
            cwd=str(Path(cwd).resolve()),
            exit_code=None,
            stdout=out,
            stderr=err,
            duration_ms=int((time.monotonic() - start) * 1000),
            timed_out=True,
            truncated=trunc1 or trunc2,
        )

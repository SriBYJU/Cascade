from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Mapping, Sequence

from ..schemas import CommandResult


def _cap(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    half = max(1, limit // 2)
    return text[:half] + "\n...<truncated>...\n" + text[-half:], True


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
    start = time.monotonic()
    merged_env = os.environ.copy() if inherit_env else {}
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            list(command),
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
            command=list(command),
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
            command=list(command),
            cwd=str(Path(cwd).resolve()),
            exit_code=None,
            stdout=out,
            stderr=err,
            duration_ms=int((time.monotonic() - start) * 1000),
            timed_out=True,
            truncated=trunc1 or trunc2,
        )

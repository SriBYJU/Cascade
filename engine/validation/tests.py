from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..schemas import ValidationCheck
from ..tools.runner import run_command
from .discover import ValidatorSpec


_SAFE_ENV_KEYS = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LANGUAGE",
    "CI",
    "RUSTUP_HOME",
    "CARGO_HOME",
    "GOPATH",
    "GOROOT",
    "JAVA_HOME",
    "NODE_PATH",
    "NVM_BIN",
    "NVM_DIR",
    "VOLTA_HOME",
    "PYENV_ROOT",
    "VIRTUAL_ENV",
}


def _validator_environment(home: Path) -> dict[str, str]:
    """Build a minimal toolchain environment without provider/user secrets."""

    env: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in _SAFE_ENV_KEYS or upper.startswith("LC_"):
            env[key] = value

    home_text = str(home)
    env.update(
        {
            "HOME": home_text,
            "USERPROFILE": home_text,
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "PYTHONNOUSERSITE": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "PIP_NO_INPUT": "1",
            "NPM_CONFIG_AUDIT": "false",
            "NPM_CONFIG_FUND": "false",
        }
    )
    return env


def run_validator(
    spec: ValidatorSpec,
    root: str | Path,
    *,
    timeout_seconds: int = 180,
    output_cap_chars: int = 12000,
) -> ValidationCheck:
    cwd = Path(root) / spec.cwd
    with tempfile.TemporaryDirectory(
        prefix="cascade-validator-home-"
    ) as temp_home:
        result = run_command(
            spec.command,
            cwd,
            timeout_seconds=timeout_seconds,
            output_cap_chars=output_cap_chars,
            env=_validator_environment(Path(temp_home)),
            inherit_env=False,
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

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ValidatorSpec:
    name: str
    command: tuple[str, ...]
    category: str


def _package_scripts(root: Path) -> dict[str, str]:
    path = root / "package.json"
    if not path.exists():
        return {}
    try:
        data: object = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return {}
    return {
        key: value
        for key, value in scripts.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _pyproject_has_tool(root: Path, tool: str) -> bool:
    path = root / "pyproject.toml"
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return f"[tool.{tool}]" in text or f"[tool.{tool}." in text


def _uses_pytest(root: Path) -> bool:
    return (
        (root / "tests").is_dir()
        or (root / "pytest.ini").exists()
        or (root / "tox.ini").exists()
        or _pyproject_has_tool(root, "pytest")
    )


def _uses_ruff(root: Path) -> bool:
    return (
        (root / "ruff.toml").exists()
        or (root / ".ruff.toml").exists()
        or _pyproject_has_tool(root, "ruff")
    )


def _uses_mypy(root: Path) -> bool:
    return (
        (root / "mypy.ini").exists()
        or (root / ".mypy.ini").exists()
        or _pyproject_has_tool(root, "mypy")
    )


def discover_validators(root: str | Path) -> list[ValidatorSpec]:
    root = Path(root)
    specs: list[ValidatorSpec] = []
    python_project = (
        (root / "pyproject.toml").exists()
        or (root / "setup.py").exists()
        or (root / "setup.cfg").exists()
    )
    if python_project:
        if shutil.which("python"):
            specs.append(
                ValidatorSpec(
                    "python-compile",
                    ("python", "-m", "compileall", "-q", "."),
                    "parser",
                )
            )
        if _uses_pytest(root) and shutil.which("python"):
            specs.append(
                ValidatorSpec(
                    "pytest",
                    ("python", "-m", "pytest", "-q"),
                    "tests",
                )
            )
        if _uses_ruff(root) and shutil.which("ruff"):
            specs.append(
                ValidatorSpec(
                    "ruff",
                    ("ruff", "check", "."),
                    "lint",
                )
            )
        if _uses_mypy(root) and shutil.which("mypy"):
            specs.append(
                ValidatorSpec(
                    "mypy",
                    ("mypy", "."),
                    "types",
                )
            )

    scripts = _package_scripts(root)
    package_manager = (
        "pnpm"
        if (root / "pnpm-lock.yaml").exists()
        and shutil.which("pnpm")
        else "npm"
    )
    if (root / "package.json").exists() and shutil.which(package_manager):
        for script, category in (
            ("test", "tests"),
            ("lint", "lint"),
            ("typecheck", "types"),
            ("check", "types"),
        ):
            if script in scripts:
                command = (
                    (package_manager, "run", script, "--if-present")
                    if package_manager == "npm"
                    else (package_manager, script)
                )
                specs.append(
                    ValidatorSpec(
                        f"js-{script}",
                        command,
                        category,
                    )
                )

    if (root / "Cargo.toml").exists() and shutil.which("cargo"):
        specs.extend(
            [
                ValidatorSpec(
                    "cargo-check",
                    ("cargo", "check", "--quiet"),
                    "types",
                ),
                ValidatorSpec(
                    "cargo-test",
                    ("cargo", "test", "--quiet"),
                    "tests",
                ),
            ]
        )
    if (root / "go.mod").exists() and shutil.which("go"):
        specs.append(
            ValidatorSpec(
                "go-test",
                ("go", "test", "./..."),
                "tests",
            )
        )
    return specs

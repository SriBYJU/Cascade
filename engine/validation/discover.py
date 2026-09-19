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
        return json.loads(path.read_text()).get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return {}


def discover_validators(root: str | Path) -> list[ValidatorSpec]:
    root = Path(root)
    specs: list[ValidatorSpec] = []
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "setup.cfg").exists():
        if shutil.which("python"):
            specs.append(ValidatorSpec("python-compile", ("python", "-m", "compileall", "-q", "."), "parser"))
        if shutil.which("pytest") or shutil.which("python"):
            specs.append(ValidatorSpec("pytest", ("python", "-m", "pytest", "-q"), "tests"))
        if shutil.which("ruff"):
            specs.append(ValidatorSpec("ruff", ("ruff", "check", "."), "lint"))
        if shutil.which("mypy"):
            specs.append(ValidatorSpec("mypy", ("mypy", "engine"), "types"))
    scripts = _package_scripts(root)
    package_manager = "pnpm" if (root / "pnpm-lock.yaml").exists() and shutil.which("pnpm") else "npm"
    if (root / "package.json").exists() and shutil.which(package_manager):
        for script, category in (("test", "tests"), ("lint", "lint"), ("typecheck", "types"), ("check", "types")):
            if script in scripts:
                specs.append(ValidatorSpec(f"js-{script}", (package_manager, "run", script, "--if-present") if package_manager == "npm" else (package_manager, script), category))
    if (root / "Cargo.toml").exists() and shutil.which("cargo"):
        specs.extend([
            ValidatorSpec("cargo-check", ("cargo", "check", "--quiet"), "types"),
            ValidatorSpec("cargo-test", ("cargo", "test", "--quiet"), "tests"),
        ])
    if (root / "go.mod").exists() and shutil.which("go"):
        specs.append(ValidatorSpec("go-test", ("go", "test", "./..."), "tests"))
    return specs

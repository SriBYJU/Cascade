from __future__ import annotations

import json
import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidatorSpec:
    name: str
    command: tuple[str, ...]
    category: str
    cwd: str = "."


def _package_data(root: Path) -> dict[str, Any]:
    path = root / "package.json"
    if not path.exists():
        return {}
    try:
        data: object = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _package_scripts(root: Path) -> dict[str, str]:
    data = _package_data(root)
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return {}
    return {
        key: value
        for key, value in scripts.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _workspace_patterns(root: Path) -> list[str]:
    data = _package_data(root)
    raw = data.get("workspaces", [])
    if isinstance(raw, list):
        return [str(item) for item in raw if isinstance(item, str)]
    if isinstance(raw, dict):
        packages = raw.get("packages", [])
        if isinstance(packages, list):
            return [
                str(item)
                for item in packages
                if isinstance(item, str)
            ]
    return []


def _safe_child(root: Path, candidate: Path) -> Path | None:
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    return resolved if resolved.is_relative_to(root.resolve()) else None


def _node_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    if (root / "package.json").exists():
        roots.append(root)
        for pattern in _workspace_patterns(root):
            if pattern.startswith("/") or ".." in Path(pattern).parts:
                continue
            for candidate in root.glob(pattern):
                safe = _safe_child(root, candidate)
                if safe is not None and (safe / "package.json").exists():
                    roots.append(safe)

    for name in ("frontend", "web", "client", "server"):
        candidate = root / name
        if (candidate / "package.json").exists():
            roots.append(candidate.resolve())

    unique: dict[str, Path] = {}
    for candidate in roots:
        rel = (
            "."
            if candidate.resolve() == root.resolve()
            else candidate.resolve().relative_to(root.resolve()).as_posix()
        )
        unique[rel] = candidate
    return [unique[key] for key in sorted(unique)]


def _python_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    if any(
        (root / name).exists()
        for name in ("pyproject.toml", "setup.py", "setup.cfg")
    ):
        roots.append(root)
    for name in ("backend", "api", "server"):
        candidate = root / name
        if any(
            (candidate / marker).exists()
            for marker in ("pyproject.toml", "setup.py", "setup.cfg")
        ):
            roots.append(candidate.resolve())

    unique: dict[str, Path] = {}
    for candidate in roots:
        rel = (
            "."
            if candidate.resolve() == root.resolve()
            else candidate.resolve().relative_to(root.resolve()).as_posix()
        )
        unique[rel] = candidate
    return [unique[key] for key in sorted(unique)]


def _jvm_roots(root: Path) -> list[Path]:
    markers = (
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "gradlew",
        "gradlew.bat",
        "mvnw",
        "mvnw.cmd",
    )
    roots: list[Path] = []
    for candidate in (
        root,
        *(root / name for name in ("backend", "server", "android", "app")),
    ):
        if any((candidate / marker).exists() for marker in markers):
            roots.append(candidate.resolve())

    unique: dict[str, Path] = {}
    for candidate in roots:
        rel = (
            "."
            if candidate.resolve() == root.resolve()
            else candidate.resolve().relative_to(root.resolve()).as_posix()
        )
        unique[rel] = candidate
    return [unique[key] for key in sorted(unique)]


def _ruby_roots(root: Path) -> list[Path]:
    markers = ("Gemfile", "Rakefile", ".rspec", ".rubocop.yml")
    roots: list[Path] = []
    for candidate in (
        root,
        *(root / name for name in ("backend", "server", "web")),
    ):
        if any((candidate / marker).exists() for marker in markers) or (
            candidate / "bin" / "rails"
        ).exists():
            roots.append(candidate.resolve())

    unique: dict[str, Path] = {}
    for candidate in roots:
        rel = (
            "."
            if candidate.resolve() == root.resolve()
            else candidate.resolve().relative_to(root.resolve()).as_posix()
        )
        unique[rel] = candidate
    return [unique[key] for key in sorted(unique)]


def _local_or_system_command(
    root: Path,
    *,
    unix_wrapper: str,
    windows_wrapper: str,
    system_command: str,
) -> tuple[str, ...] | None:
    if sys.platform.startswith("win"):
        if (root / windows_wrapper).is_file():
            return (windows_wrapper,)
    elif (root / unix_wrapper).is_file():
        return (f"./{unix_wrapper}",)
    if shutil.which(system_command):
        return (system_command,)
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _rakefile_declares_test(root: Path) -> bool:
    text = _read_text(root / "Rakefile")
    return any(
        token in text
        for token in (
            "Rake::TestTask",
            "task :test",
            "task(:test",
            'task "test"',
            "task('test'",
        )
    )


def _gemfile_mentions(root: Path, gem: str) -> bool:
    text = _read_text(root / "Gemfile")
    return gem.lower() in text.lower()


def _scope_name(root: Path, project_root: Path, name: str) -> str:
    if project_root.resolve() == root.resolve():
        return name
    rel = project_root.resolve().relative_to(root.resolve()).as_posix()
    return f"{rel}:{name}"


def _scope_cwd(root: Path, project_root: Path) -> str:
    if project_root.resolve() == root.resolve():
        return "."
    return project_root.resolve().relative_to(root.resolve()).as_posix()


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


def _package_manager(root: Path, package_root: Path) -> str | None:
    search = [package_root, root]
    if any((candidate / "pnpm-lock.yaml").exists() for candidate in search):
        return "pnpm" if shutil.which("pnpm") else None
    if any((candidate / "yarn.lock").exists() for candidate in search):
        return "yarn" if shutil.which("yarn") else None
    return "npm" if shutil.which("npm") else None


def _python_command() -> tuple[str, ...] | None:
    if shutil.which("python"):
        return ("python",)
    executable = Path(sys.executable)
    return (str(executable),) if executable.is_file() else None


def _python_tool_command(
    tool: str,
    python_command: tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if shutil.which(tool):
        return (tool,)
    if (
        python_command is not None
        and importlib.util.find_spec(tool) is not None
    ):
        return (*python_command, "-m", tool)
    return None


def discover_validators(root: str | Path) -> list[ValidatorSpec]:
    root = Path(root).resolve()
    specs: list[ValidatorSpec] = []
    python_command = _python_command()
    ruff_command = _python_tool_command("ruff", python_command)
    mypy_command = _python_tool_command("mypy", python_command)

    for project_root in _python_roots(root):
        cwd = _scope_cwd(root, project_root)
        if python_command is not None:
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "python-compile"),
                    (*python_command, "-m", "compileall", "-q", "."),
                    "parser",
                    cwd,
                )
            )
        if _uses_pytest(project_root) and python_command is not None:
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "pytest"),
                    (*python_command, "-m", "pytest", "-q"),
                    "tests",
                    cwd,
                )
            )
        if _uses_ruff(project_root) and ruff_command is not None:
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "ruff"),
                    (*ruff_command, "check", "."),
                    "lint",
                    cwd,
                )
            )
        if _uses_mypy(project_root) and mypy_command is not None:
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "mypy"),
                    (*mypy_command, "."),
                    "types",
                    cwd,
                )
            )

    for package_root in _node_roots(root):
        manager = _package_manager(root, package_root)
        if manager is None:
            continue
        scripts = _package_scripts(package_root)
        cwd = _scope_cwd(root, package_root)
        for script, category in (
            ("test", "tests"),
            ("lint", "lint"),
            ("typecheck", "types"),
            ("check", "types"),
        ):
            if script not in scripts:
                continue
            command: tuple[str, ...]
            if manager == "npm":
                command = ("npm", "run", script, "--if-present")
            elif manager == "pnpm":
                command = ("pnpm", script)
            else:
                command = ("yarn", script)
            specs.append(
                ValidatorSpec(
                    _scope_name(root, package_root, f"js-{script}"),
                    command,
                    category,
                    cwd,
                )
            )

    for project_root in _jvm_roots(root):
        cwd = _scope_cwd(root, project_root)
        has_gradle = any(
            (project_root / name).exists()
            for name in (
                "build.gradle",
                "build.gradle.kts",
                "settings.gradle",
                "settings.gradle.kts",
            )
        )
        if has_gradle:
            gradle = _local_or_system_command(
                project_root,
                unix_wrapper="gradlew",
                windows_wrapper="gradlew.bat",
                system_command="gradle",
            )
            if gradle is not None:
                specs.append(
                    ValidatorSpec(
                        _scope_name(root, project_root, "jvm-gradle-test"),
                        (*gradle, "test"),
                        "tests",
                        cwd,
                    )
                )

        if (project_root / "pom.xml").exists():
            maven = _local_or_system_command(
                project_root,
                unix_wrapper="mvnw",
                windows_wrapper="mvnw.cmd",
                system_command="mvn",
            )
            if maven is not None:
                specs.append(
                    ValidatorSpec(
                        _scope_name(root, project_root, "jvm-maven-test"),
                        (*maven, "test"),
                        "tests",
                        cwd,
                    )
                )

    for project_root in _ruby_roots(root):
        cwd = _scope_cwd(root, project_root)
        ruby = shutil.which("ruby")
        bundle = shutil.which("bundle")
        if ruby and (project_root / "bin" / "rails").is_file():
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "rails-test"),
                    ("ruby", "bin/rails", "test"),
                    "tests",
                    cwd,
                )
            )
        elif ruby and (project_root / "bin" / "rspec").is_file():
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "rspec"),
                    ("ruby", "bin/rspec"),
                    "tests",
                    cwd,
                )
            )
        elif (
            bundle
            and (project_root / "Gemfile").is_file()
            and (
                (project_root / ".rspec").exists()
                or (project_root / "spec").is_dir()
                or _gemfile_mentions(project_root, "rspec")
            )
        ):
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "rspec"),
                    ("bundle", "exec", "rspec"),
                    "tests",
                    cwd,
                )
            )
        elif (
            bundle
            and (project_root / "Gemfile").is_file()
            and _rakefile_declares_test(project_root)
        ):
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "rake-test"),
                    ("bundle", "exec", "rake", "test"),
                    "tests",
                    cwd,
                )
            )

        if (
            bundle
            and (project_root / "Gemfile").is_file()
            and (
                (project_root / ".rubocop.yml").exists()
                or _gemfile_mentions(project_root, "rubocop")
            )
        ):
            specs.append(
                ValidatorSpec(
                    _scope_name(root, project_root, "rubocop"),
                    ("bundle", "exec", "rubocop"),
                    "lint",
                    cwd,
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

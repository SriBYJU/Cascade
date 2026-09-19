from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
from pathlib import Path

from ..schemas import RepoFile, RepoMap

SKIP_DIRS = {
    ".git",
    ".cascade",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
}
TEXT_EXTENSIONS = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
}
RISK_PATTERNS = {
    "auth": re.compile(r"auth|oauth|session|login", re.I),
    "secrets": re.compile(
        r"secret|credential|token|password|keyvault",
        re.I,
    ),
    "migration": re.compile(
        r"migrat|schema|alembic|prisma",
        re.I,
    ),
    "payments": re.compile(
        r"payment|stripe|billing|checkout",
        re.I,
    ),
    "deploy": re.compile(
        r"deploy|terraform|cloudformation|kubernetes|docker",
        re.I,
    ),
}
ENTRY_POINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "index.js",
    "index.ts",
    "main.rs",
    "main.go",
}


def _git(root: Path, *args: str) -> str:
    try:
        process = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        return process.stdout.strip() if process.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def repository_fingerprint(root: str | Path) -> str:
    root = Path(root).resolve()
    head = _git(root, "rev-parse", "HEAD") or "no-head"
    raw_status = _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    status = "\n".join(
        line
        for line in raw_status.splitlines()
        if ".cascade/" not in line.replace("\\", "/")
    )
    payload = f"{root}\n{head}\n{status}".encode()
    return hashlib.sha256(payload).hexdigest()


def _python_symbols(text: str) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    imports: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return symbols, imports
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return symbols[:200], imports[:200]


def _generic_symbols(text: str) -> tuple[list[str], list[str]]:
    symbols = re.findall(
        r"(?:function|class|interface|type|struct|enum|def|fn)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        text,
    )
    imports = re.findall(
        r"(?:from|import|require\()\s*[\"']?"
        r"([@A-Za-z0-9_./-]+)",
        text,
    )
    return symbols[:200], imports[:200]


def _git_recency(root: Path, rel: str) -> float:
    raw = _git(
        root,
        "log",
        "-1",
        "--format=%ct",
        "--",
        rel,
    )
    return float(raw) if raw.isdigit() else 0.0


def _package_for(rel: str) -> str | None:
    parts = Path(rel).parts
    if len(parts) <= 1:
        return None
    return parts[0]


def _python_module_for(path: str) -> str | None:
    p = Path(path)
    if p.suffix not in {".py", ".pyi"}:
        return None
    parts = list(p.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else None


def _resolve_reference(
    source: RepoFile,
    imported: str,
    path_set: set[str],
    module_to_path: dict[str, str],
) -> str | None:
    if source.language == "python":
        if imported in module_to_path:
            return module_to_path[imported]
        pieces = imported.split(".")
        while pieces:
            candidate = ".".join(pieces)
            if candidate in module_to_path:
                return module_to_path[candidate]
            pieces.pop()
        return None

    if imported.startswith("."):
        source_parent = Path(source.path).parent
        raw = (source_parent / imported).as_posix()
        candidates = [
            raw,
            f"{raw}.js",
            f"{raw}.ts",
            f"{raw}.jsx",
            f"{raw}.tsx",
            f"{raw}/index.js",
            f"{raw}/index.ts",
        ]
        for candidate in candidates:
            normalized = Path(candidate).as_posix()
            if normalized in path_set:
                return normalized
    return None


def _link_structure(files: list[RepoFile]) -> list[RepoFile]:
    path_set = {file.path for file in files}
    module_to_path = {
        module: file.path
        for file in files
        if (module := _python_module_for(file.path)) is not None
    }
    forward: dict[str, set[str]] = {
        file.path: set()
        for file in files
    }
    reverse: dict[str, set[str]] = {
        file.path: set()
        for file in files
    }

    for file in files:
        for imported in file.imports:
            target = _resolve_reference(
                file,
                imported,
                path_set,
                module_to_path,
            )
            if target and target != file.path:
                forward[file.path].add(target)
                reverse[target].add(file.path)

    linked: list[RepoFile] = []
    by_path = {file.path: file for file in files}
    for file in files:
        test_targets = (
            sorted(
                target
                for target in forward[file.path]
                if not by_path[target].is_test
            )
            if file.is_test
            else []
        )
        linked.append(
            file.model_copy(
                update={
                    "references": sorted(forward[file.path]),
                    "referenced_by": sorted(reverse[file.path]),
                    "test_targets": test_targets,
                }
            )
        )
    return linked


def _load_cached_map(
    cache_path: Path,
    fingerprint: str,
) -> RepoMap | None:
    if not cache_path.exists():
        return None
    try:
        cached = RepoMap.model_validate_json(cache_path.read_text())
    except (OSError, ValueError):
        return None
    return cached if cached.fingerprint == fingerprint else None


def build_repo_map(
    root: str | Path,
    max_file_bytes: int = 512_000,
    *,
    use_cache: bool = True,
) -> RepoMap:
    root = Path(root).resolve()
    fingerprint = repository_fingerprint(root)
    cache_path = root / ".cascade" / "repo-map.json"
    if use_cache:
        cached = _load_cached_map(cache_path, fingerprint)
        if cached is not None:
            return cached

    files: list[RepoFile] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in SKIP_DIRS
        ]
        for name in names:
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            language = TEXT_EXTENSIONS.get(path.suffix.lower())
            if not language:
                continue
            try:
                size = path.stat().st_size
                if size > max_file_bytes:
                    continue
                text = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            symbols, imports = (
                _python_symbols(text)
                if language == "python"
                else _generic_symbols(text)
            )
            tags = [
                tag
                for tag, pattern in RISK_PATTERNS.items()
                if pattern.search(rel)
                or pattern.search(text[:5000])
            ]
            files.append(
                RepoFile(
                    path=rel,
                    language=language,
                    size_bytes=size,
                    lines=text.count("\n") + 1,
                    symbols=symbols,
                    imports=imports,
                    package=_package_for(rel),
                    git_recency=_git_recency(root, rel),
                    is_test=(
                        "test" in path.stem.lower()
                        or "/tests/" in f"/{rel}/"
                    ),
                    is_entry_point=name in ENTRY_POINT_NAMES,
                    risk_tags=tags,
                )
            )

    linked = _link_structure(files)
    repo_map = RepoMap(
        root=str(root),
        fingerprint=fingerprint,
        files=sorted(linked, key=lambda file: file.path),
    )
    if use_cache:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                repo_map.model_dump_json(indent=2)
            )
        except OSError:
            pass
    return repo_map

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


def _go_symbols(text: str) -> tuple[list[str], list[str]]:
    functions = re.findall(
        r"(?m)^\s*func\s+(?:\([^)]*\)\s*)?"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        text,
    )
    types = re.findall(
        r"(?m)^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+",
        text,
    )
    imports: list[str] = []
    imports.extend(
        re.findall(
            r'(?m)^\s*import\s+(?:[A-Za-z_][A-Za-z0-9_]*\s+)?'
            r'"([^"]+)"',
            text,
        )
    )
    for block in re.findall(
        r"(?ms)^\s*import\s*\((.*?)\)",
        text,
    ):
        imports.extend(
            re.findall(
                r'(?:^|\n)\s*(?:[A-Za-z_.][A-Za-z0-9_.]*\s+)?'
                r'"([^"]+)"',
                block,
            )
        )
    return (functions + types)[:200], imports[:200]


def _rust_symbols(text: str) -> tuple[list[str], list[str]]:
    symbols = re.findall(
        r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?"
        r"(?:async\s+)?(?:fn|struct|enum|trait|type|mod)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        text,
    )
    imports: list[str] = []
    imports.extend(
        match.strip()
        for match in re.findall(
            r"(?m)^\s*(?:pub\s+)?use\s+([^;]+);",
            text,
        )
    )
    imports.extend(
        f"mod:{name}"
        for name in re.findall(
            r"(?m)^\s*(?:pub\s+)?mod\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*;",
            text,
        )
    )
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


def _extract_symbols(
    language: str,
    text: str,
) -> tuple[list[str], list[str]]:
    if language == "python":
        return _python_symbols(text)
    if language == "go":
        return _go_symbols(text)
    if language == "rust":
        return _rust_symbols(text)
    return _generic_symbols(text)


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


def _go_module_name(root: Path) -> str | None:
    path = root / "go.mod"
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"(?m)^\s*module\s+(\S+)\s*$", text)
    return match.group(1) if match else None


def _python_reference(
    imported: str,
    module_to_path: dict[str, str],
) -> set[str]:
    if imported in module_to_path:
        return {module_to_path[imported]}
    pieces = imported.split(".")
    while pieces:
        candidate = ".".join(pieces)
        if candidate in module_to_path:
            return {module_to_path[candidate]}
        pieces.pop()
    return set()


def _relative_js_reference(
    source: RepoFile,
    imported: str,
    path_set: set[str],
) -> set[str]:
    if not imported.startswith("."):
        return set()
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
    return {
        Path(candidate).as_posix()
        for candidate in candidates
        if Path(candidate).as_posix() in path_set
    }


def _go_references(
    imported: str,
    *,
    module_name: str | None,
    files: list[RepoFile],
) -> set[str]:
    if not module_name:
        return set()
    if imported == module_name:
        rel_dir = "."
    elif imported.startswith(module_name + "/"):
        rel_dir = imported[len(module_name) + 1 :]
    else:
        return set()
    normalized = Path(rel_dir).as_posix()
    return {
        file.path
        for file in files
        if file.language == "go"
        and Path(file.path).parent.as_posix() == normalized
        and not file.is_test
    }


def _rust_candidates(
    source: RepoFile,
    imported: str,
) -> list[str]:
    source_path = Path(source.path)
    crate_root = Path("src") if source_path.parts[:1] == ("src",) else Path(".")
    if imported.startswith("mod:"):
        name = imported.split(":", 1)[1]
        parent = source_path.parent
        return [
            (parent / f"{name}.rs").as_posix(),
            (parent / name / "mod.rs").as_posix(),
        ]

    cleaned = imported.split(" as ", 1)[0].strip()
    cleaned = cleaned.split("::{", 1)[0].strip()
    parts = [part for part in cleaned.split("::") if part]
    if not parts:
        return []
    if parts[0] == "crate":
        parts = parts[1:]
        base = crate_root
    elif parts[0] == "self":
        parts = parts[1:]
        base = source_path.parent
    elif parts[0] == "super":
        while parts and parts[0] == "super":
            parts = parts[1:]
            base = source_path.parent.parent
        if "base" not in locals():
            base = source_path.parent
    else:
        return []

    candidates: list[str] = []
    while parts:
        joined = base.joinpath(*parts)
        candidates.extend(
            [
                joined.with_suffix(".rs").as_posix(),
                (joined / "mod.rs").as_posix(),
            ]
        )
        parts.pop()
    return candidates


def _resolve_references(
    source: RepoFile,
    imported: str,
    *,
    path_set: set[str],
    module_to_path: dict[str, str],
    go_module: str | None,
    files: list[RepoFile],
) -> set[str]:
    if source.language == "python":
        return _python_reference(imported, module_to_path)
    if source.language in {"javascript", "typescript"}:
        return _relative_js_reference(source, imported, path_set)
    if source.language == "go":
        return _go_references(
            imported,
            module_name=go_module,
            files=files,
        )
    if source.language == "rust":
        return {
            candidate
            for candidate in _rust_candidates(source, imported)
            if candidate in path_set
        }
    return set()


def _link_structure(
    root: Path,
    files: list[RepoFile],
) -> list[RepoFile]:
    path_set = {file.path for file in files}
    module_to_path = {
        module: file.path
        for file in files
        if (module := _python_module_for(file.path)) is not None
    }
    go_module = _go_module_name(root)
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
            targets = _resolve_references(
                file,
                imported,
                path_set=path_set,
                module_to_path=module_to_path,
                go_module=go_module,
                files=files,
            )
            for target in targets:
                if target == file.path:
                    continue
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

            symbols, imports = _extract_symbols(language, text)
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

    linked = _link_structure(root, files)
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

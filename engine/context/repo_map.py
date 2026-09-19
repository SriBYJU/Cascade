from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
from pathlib import Path

from ..schemas import RepoFile, RepoMap

SKIP_DIRS = {".git", ".cascade", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
TEXT_EXTENSIONS = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".rs": "rust", ".go": "go",
    ".java": "java", ".kt": "kotlin", ".swift": "swift", ".rb": "ruby",
    ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".md": "markdown", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".html": "html", ".css": "css", ".scss": "scss",
    ".sh": "shell", ".bash": "shell", ".sql": "sql",
}
RISK_PATTERNS = {
    "auth": re.compile(r"auth|oauth|session|login", re.I),
    "secrets": re.compile(r"secret|credential|token|password|keyvault", re.I),
    "migration": re.compile(r"migrat|schema|alembic|prisma", re.I),
    "payments": re.compile(r"payment|stripe|billing|checkout", re.I),
    "deploy": re.compile(r"deploy|terraform|cloudformation|kubernetes|docker", re.I),
}


def _git(root: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def repository_fingerprint(root: str | Path) -> str:
    root = Path(root).resolve()
    head = _git(root, "rev-parse", "HEAD") or "no-head"
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return symbols[:200], imports[:200]


def _generic_symbols(text: str) -> tuple[list[str], list[str]]:
    symbols = re.findall(r"(?:function|class|interface|type|struct|enum|def|fn)\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    imports = re.findall(r"(?:from|import|require\()\s*[\"']?([@A-Za-z0-9_./-]+)", text)
    return symbols[:200], imports[:200]


def _git_recency(root: Path, rel: str) -> float:
    raw = _git(root, "log", "-1", "--format=%ct", "--", rel)
    if not raw.isdigit():
        return 0.0
    return float(raw)


def build_repo_map(root: str | Path, max_file_bytes: int = 512_000) -> RepoMap:
    root = Path(root).resolve()
    files: list[RepoFile] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            lang = TEXT_EXTENSIONS.get(path.suffix.lower())
            if not lang:
                continue
            try:
                size = path.stat().st_size
                if size > max_file_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            symbols, imports = _python_symbols(text) if lang == "python" else _generic_symbols(text)
            tags = [tag for tag, pat in RISK_PATTERNS.items() if pat.search(rel) or pat.search(text[:5000])]
            files.append(RepoFile(
                path=rel,
                language=lang,
                size_bytes=size,
                lines=text.count("\n") + 1,
                symbols=symbols,
                imports=imports,
                git_recency=_git_recency(root, rel),
                is_test=("test" in path.stem.lower() or "/tests/" in f"/{rel}/"),
                risk_tags=tags,
            ))
    return RepoMap(root=str(root), fingerprint=repository_fingerprint(root), files=sorted(files, key=lambda f: f.path))

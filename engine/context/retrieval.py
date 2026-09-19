from __future__ import annotations

import math
import re
from pathlib import Path

from ..schemas import EvidenceRef, RepoFile, RepoMap
from .provenance import provenance_for_path

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text) if len(t) > 1}


def _score(file: RepoFile, query_tokens: set[str], max_recency: float) -> float:
    path_tokens = _tokens(file.path)
    symbol_tokens = {s.lower() for s in file.symbols}
    import_tokens = _tokens(" ".join(file.imports))
    lexical = len(query_tokens & path_tokens) * 4.0
    symbol = len(query_tokens & symbol_tokens) * 6.0
    imports = len(query_tokens & import_tokens) * 1.5
    risk = 1.5 if query_tokens & {t.lower() for t in file.risk_tags} else 0.0
    test_bonus = 0.8 if file.is_test and any(t in query_tokens for t in {"test", "bug", "fix", "verify"}) else 0.0
    recency = (file.git_recency / max_recency) if max_recency and file.git_recency else 0.0
    return lexical + symbol + imports + risk + test_bonus + 0.3 * recency


def rank_files(repo_map: RepoMap, query: str, limit: int = 12) -> list[RepoFile]:
    q = _tokens(query)
    if not q:
        return repo_map.files[:limit]
    max_recency = max((f.git_recency for f in repo_map.files), default=0.0)
    ranked = sorted(repo_map.files, key=lambda f: (_score(f, q, max_recency), -len(f.path)), reverse=True)
    return [f for f in ranked if _score(f, q, max_recency) > 0][:limit]


def collect_evidence(repo_map: RepoMap, query: str, *, max_files: int = 8, max_lines_per_file: int = 80) -> list[EvidenceRef]:
    root = Path(repo_map.root)
    evidence: list[EvidenceRef] = []
    terms = _tokens(query)
    for file in rank_files(repo_map, query, max_files):
        path = root / file.path
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        hits: list[int] = []
        for i, line in enumerate(lines, start=1):
            low = line.lower()
            if any(term in low for term in terms):
                hits.append(i)
        if hits:
            start = max(1, min(hits) - 3)
            end = min(len(lines), min(max(hits) + 3, start + max_lines_per_file - 1))
        else:
            start, end = 1, min(len(lines), max_lines_per_file)
        evidence.append(EvidenceRef(
            file=file.path,
            start_line=start,
            end_line=max(start, end),
            claim=f"ranked repository evidence for: {query[:160]}",
            provenance=provenance_for_path(file.path),
        ))
    return evidence


def estimate_context_tokens(evidence: list[EvidenceRef]) -> int:
    # Conservative code/token approximation without invoking a tokenizer.
    lines = sum(max(0, e.end_line - e.start_line + 1) for e in evidence)
    return int(math.ceil(lines * 12.0))

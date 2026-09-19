from __future__ import annotations

import re
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(?:api[_-]?key|secret|password)\s*[=:]\s*[\"'][^\"']{12,}[\"']"),
]


def scan_text_for_secrets(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def scan_files(root: str | Path, paths: list[str]) -> dict[str, list[str]]:
    root = Path(root)
    findings: dict[str, list[str]] = {}
    for rel in paths:
        path = root / rel
        if not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            matches = scan_text_for_secrets(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if matches:
            findings[rel] = matches
    return findings

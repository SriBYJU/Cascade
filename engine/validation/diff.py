from __future__ import annotations

from pathlib import Path

from ..tools.runner import run_command


def diff_stat(root: str | Path, base_ref: str = "HEAD") -> dict[str, int]:
    result = run_command(["git", "diff", "--numstat", base_ref], root)
    additions = deletions = files = 0
    if result.exit_code != 0:
        return {"files": 0, "additions": 0, "deletions": 0}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            files += 1
            additions += int(parts[0]) if parts[0].isdigit() else 0
            deletions += int(parts[1]) if parts[1].isdigit() else 0
    return {"files": files, "additions": additions, "deletions": deletions}

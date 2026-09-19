from __future__ import annotations

from dataclasses import dataclass

from ..schemas import ToolRisk


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    risk: ToolRisk
    requires_explicit_approval: bool
    retry_without_idempotency: bool


DEFAULT_POLICIES: dict[ToolRisk, ToolPolicy] = {
    ToolRisk.READ_ONLY: ToolPolicy(ToolRisk.READ_ONLY, False, True),
    ToolRisk.LOCAL_WRITE: ToolPolicy(ToolRisk.LOCAL_WRITE, False, True),
    ToolRisk.REPO_WRITE: ToolPolicy(ToolRisk.REPO_WRITE, False, True),
    ToolRisk.NETWORK_READ: ToolPolicy(ToolRisk.NETWORK_READ, False, True),
    ToolRisk.NETWORK_WRITE: ToolPolicy(ToolRisk.NETWORK_WRITE, True, False),
    ToolRisk.EXTERNAL_SIDE_EFFECT: ToolPolicy(ToolRisk.EXTERNAL_SIDE_EFFECT, True, False),
    ToolRisk.DESTRUCTIVE: ToolPolicy(ToolRisk.DESTRUCTIVE, True, False),
    ToolRisk.SECRET_ACCESS: ToolPolicy(ToolRisk.SECRET_ACCESS, True, False),
}


def classify_command(argv: list[str]) -> ToolRisk:
    if not argv:
        return ToolRisk.READ_ONLY
    cmd = argv[0].lower()
    joined = " ".join(a.lower() for a in argv)
    if cmd in {"rm", "del", "rmdir"} or " reset --hard" in f" {joined}":
        return ToolRisk.DESTRUCTIVE
    if cmd in {"curl", "wget"}:
        return ToolRisk.NETWORK_READ
    if cmd in {"git"} and any(x in argv for x in {"push", "tag"}):
        return ToolRisk.NETWORK_WRITE
    if cmd in {"git"} and any(x in argv for x in {"add", "commit", "merge", "rebase", "checkout", "switch"}):
        return ToolRisk.REPO_WRITE
    if cmd in {"python", "python3", "node", "npm", "pnpm", "yarn", "pytest", "ruff", "mypy"}:
        return ToolRisk.LOCAL_WRITE if any(k in joined for k in {" install", " --fix", " format"}) else ToolRisk.READ_ONLY
    return ToolRisk.READ_ONLY

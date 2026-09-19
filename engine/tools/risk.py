from __future__ import annotations

from dataclasses import dataclass

from ..schemas import ToolRisk


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    risk: ToolRisk
    requires_explicit_approval: bool
    retry_without_idempotency: bool


DEFAULT_POLICIES: dict[ToolRisk, ToolPolicy] = {
    ToolRisk.READ_ONLY: ToolPolicy(
        ToolRisk.READ_ONLY,
        False,
        True,
    ),
    ToolRisk.LOCAL_WRITE: ToolPolicy(
        ToolRisk.LOCAL_WRITE,
        False,
        True,
    ),
    ToolRisk.REPO_WRITE: ToolPolicy(
        ToolRisk.REPO_WRITE,
        False,
        True,
    ),
    ToolRisk.NETWORK_READ: ToolPolicy(
        ToolRisk.NETWORK_READ,
        False,
        True,
    ),
    ToolRisk.NETWORK_WRITE: ToolPolicy(
        ToolRisk.NETWORK_WRITE,
        True,
        False,
    ),
    ToolRisk.EXTERNAL_SIDE_EFFECT: ToolPolicy(
        ToolRisk.EXTERNAL_SIDE_EFFECT,
        True,
        False,
    ),
    ToolRisk.DESTRUCTIVE: ToolPolicy(
        ToolRisk.DESTRUCTIVE,
        True,
        False,
    ),
    ToolRisk.SECRET_ACCESS: ToolPolicy(
        ToolRisk.SECRET_ACCESS,
        True,
        False,
    ),
}


def _has_any(argv: list[str], values: set[str]) -> bool:
    return any(item in values for item in argv)


def classify_command(argv: list[str]) -> ToolRisk:
    """Conservative command classifier.

    Interpreters, package scripts, shell-like execution surfaces, and unknown
    commands are never assumed read-only merely because their common use is
    benign. Deterministic validators use their own bounded runner path.
    """

    if not argv:
        return ToolRisk.READ_ONLY

    cmd = argv[0].lower()
    args = [item.lower() for item in argv[1:]]
    joined = " ".join(args)

    if cmd in {"rm", "del", "rmdir", "shred"}:
        return ToolRisk.DESTRUCTIVE

    if cmd == "git":
        if _has_any(args, {"push"}):
            return ToolRisk.NETWORK_WRITE
        if _has_any(
            args,
            {
                "add",
                "commit",
                "merge",
                "rebase",
                "checkout",
                "switch",
                "reset",
                "clean",
                "restore",
                "cherry-pick",
                "revert",
                "tag",
            },
        ):
            return ToolRisk.REPO_WRITE
        if _has_any(args, {"fetch", "ls-remote"}):
            return ToolRisk.NETWORK_READ
        if _has_any(
            args,
            {
                "status",
                "diff",
                "log",
                "show",
                "rev-parse",
                "ls-files",
                "merge-base",
                "merge-tree",
            },
        ):
            return ToolRisk.READ_ONLY
        return ToolRisk.EXTERNAL_SIDE_EFFECT

    if cmd == "curl":
        write_flags = {
            "-d",
            "--data",
            "--data-raw",
            "--data-binary",
            "--data-urlencode",
            "-f",
            "--form",
            "-t",
            "--upload-file",
            "--post-data",
            "--post-file",
        }
        local_write_flags = {
            "-o",
            "--output",
            "-O".lower(),
            "--remote-name",
            "--output-dir",
        }
        explicit_write_method = (
            "-x post" in f" {joined}"
            or "-x put" in f" {joined}"
            or "-x patch" in f" {joined}"
            or "-x delete" in f" {joined}"
            or "--request post" in f" {joined}"
            or "--request put" in f" {joined}"
            or "--request patch" in f" {joined}"
            or "--request delete" in f" {joined}"
        )
        if explicit_write_method or _has_any(args, write_flags):
            return ToolRisk.NETWORK_WRITE
        if _has_any(args, local_write_flags):
            return ToolRisk.EXTERNAL_SIDE_EFFECT
        return ToolRisk.NETWORK_READ

    if cmd == "wget":
        # wget writes a local file by default. Keep it approval-gated rather
        # than guessing whether a particular flag combination is stdout-only.
        return ToolRisk.EXTERNAL_SIDE_EFFECT

    if cmd in {"env", "printenv"}:
        return ToolRisk.SECRET_ACCESS

    if cmd in {"grep", "rg", "ls", "pwd", "which", "where"}:
        return ToolRisk.READ_ONLY

    if cmd == "find":
        if _has_any(
            args,
            {"-delete", "-exec", "-execdir", "-ok", "-okdir"},
        ):
            return ToolRisk.EXTERNAL_SIDE_EFFECT
        return ToolRisk.READ_ONLY

    # General-purpose interpreters and test runners can read secrets, write
    # files, or contact the network from user-controlled code.
    if cmd in {"python", "python3", "node", "pytest"}:
        return ToolRisk.EXTERNAL_SIDE_EFFECT

    if cmd == "ruff":
        if "--fix" in args or "format" in args:
            return ToolRisk.LOCAL_WRITE
        return ToolRisk.READ_ONLY

    if cmd == "mypy":
        return ToolRisk.READ_ONLY

    if cmd in {"npm", "pnpm", "yarn"}:
        if any(
            token in args
            for token in {
                "install",
                "add",
                "remove",
                "uninstall",
                "update",
            }
        ):
            return ToolRisk.LOCAL_WRITE
        if any(
            token in args
            for token in {
                "publish",
                "run",
                "test",
                "exec",
                "dlx",
                "start",
                "restart",
                "stop",
                "login",
                "logout",
                "token",
                "access",
                "deprecate",
                "dist-tag",
                "owner",
            }
        ):
            return ToolRisk.EXTERNAL_SIDE_EFFECT
        if any(
            token in args
            for token in {
                "view",
                "info",
                "search",
                "outdated",
                "audit",
            }
        ):
            return ToolRisk.NETWORK_READ
        if any(token in args for token in {"list", "ls", "why"}):
            return ToolRisk.READ_ONLY
        return ToolRisk.EXTERNAL_SIDE_EFFECT

    if cmd in {"pip", "pip3"}:
        if any(token in args for token in {"install", "uninstall"}):
            return ToolRisk.LOCAL_WRITE
        if "download" in args:
            return ToolRisk.EXTERNAL_SIDE_EFFECT
        if any(token in args for token in {"list", "show", "freeze", "check"}):
            return ToolRisk.READ_ONLY
        if "index" in args:
            return ToolRisk.NETWORK_READ
        return ToolRisk.EXTERNAL_SIDE_EFFECT

    return ToolRisk.EXTERNAL_SIDE_EFFECT

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class InstallEntry:
    path: str
    sha256: str
    created: bool
    backup: str | None = None


@dataclass(slots=True)
class InstallReceipt:
    version: int
    files: list[InstallEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "files": [asdict(entry) for entry in self.files],
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt_path(target: Path) -> Path:
    return target / ".cascade" / "project-install.json"


def _load_receipt(target: Path) -> InstallReceipt | None:
    path = _receipt_path(target)
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("unsupported Cascade project-install receipt")
    entries: list[InstallEntry] = []
    files = raw.get("files", [])
    if not isinstance(files, list):
        raise ValueError("invalid Cascade project-install receipt")
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("invalid Cascade project-install receipt entry")
        entries.append(
            InstallEntry(
                path=str(item["path"]),
                sha256=str(item["sha256"]),
                created=bool(item["created"]),
                backup=(
                    str(item["backup"])
                    if item.get("backup") is not None
                    else None
                ),
            )
        )
    return InstallReceipt(version=1, files=entries)


def _resource_files() -> list[tuple[str, bytes]]:
    base = resources.files("engine.resources")
    outputs: list[tuple[str, bytes]] = []
    for name in (
        "architect.toml",
        "builder.toml",
        "debugger.toml",
        "integrator.toml",
        "reviewer.toml",
        "scout.toml",
    ):
        outputs.append(
            (
                f".codex/agents/{name}",
                (base / "agents" / name).read_bytes(),
            )
        )

    skill = base / "skill"
    outputs.append(
        (
            ".agents/skills/cascade-optimizer/SKILL.md",
            (skill / "SKILL.md").read_bytes(),
        )
    )
    for name in (
        "caching.md",
        "context-firewall.md",
        "routing.md",
        "scheduling.md",
        "security.md",
        "verification.md",
    ):
        outputs.append(
            (
                f".agents/skills/cascade-optimizer/references/{name}",
                (skill / "references" / name).read_bytes(),
            )
        )
    return outputs


def install_project(
    target: str | Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(target).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"project target is not a directory: {root}")

    prior = _load_receipt(root)
    prior_by_path = {
        entry.path: entry
        for entry in (prior.files if prior else [])
    }
    planned: list[dict[str, Any]] = []
    entries: list[InstallEntry] = []
    backup_root = root / ".cascade" / "install-backups"

    for rel, content in _resource_files():
        destination = root / rel
        digest = _sha(content)
        previous = prior_by_path.get(rel)
        if destination.exists():
            existing = destination.read_bytes()
            existing_sha = _sha(existing)
            if existing_sha == digest:
                created = bool(
                    previous
                    and previous.created
                    and previous.sha256 == digest
                )
                entries.append(
                    InstallEntry(
                        rel,
                        digest,
                        created=created,
                        backup=(previous.backup if previous else None),
                    )
                )
                planned.append(
                    {
                        "path": rel,
                        "action": "keep",
                        "reason": "already identical",
                    }
                )
                continue
            if not overwrite:
                raise FileExistsError(
                    f"refusing to overwrite existing project file: {rel}"
                )
            backup_name = hashlib.sha256(
                rel.encode("utf-8")
            ).hexdigest()[:16] + ".bak"
            backup_rel = (
                Path(".cascade")
                / "install-backups"
                / backup_name
            ).as_posix()
            if not dry_run:
                backup_root.mkdir(parents=True, exist_ok=True)
                (root / backup_rel).write_bytes(existing)
            entries.append(
                InstallEntry(
                    rel,
                    digest,
                    created=True,
                    backup=backup_rel,
                )
            )
            planned.append(
                {
                    "path": rel,
                    "action": "replace-with-backup",
                    "backup": backup_rel,
                }
            )
        else:
            entries.append(
                InstallEntry(rel, digest, created=True)
            )
            planned.append({"path": rel, "action": "create"})

        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)

    if not dry_run:
        receipt = InstallReceipt(version=1, files=entries)
        receipt_path = _receipt_path(root)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(
                receipt.to_dict(),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    return {
        "status": "dry-run" if dry_run else "installed",
        "target": str(root),
        "files": planned,
        "receipt": str(_receipt_path(root)),
    }


def project_status(target: str | Path) -> dict[str, Any]:
    root = Path(target).resolve()
    receipt = _load_receipt(root)
    if receipt is None:
        return {
            "status": "not-installed",
            "target": str(root),
            "files": [],
        }

    files: list[dict[str, Any]] = []
    drifted = False
    for entry in receipt.files:
        path = root / entry.path
        if not path.exists():
            state = "missing"
            drifted = True
        else:
            current = _sha(path.read_bytes())
            state = (
                "managed"
                if current == entry.sha256
                else "modified"
            )
            drifted = drifted or state != "managed"
        files.append({"path": entry.path, "state": state})

    return {
        "status": "drifted" if drifted else "installed",
        "target": str(root),
        "files": files,
    }


def _remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.is_relative_to(stop):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def uninstall_project(
    target: str | Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(target).resolve()
    receipt = _load_receipt(root)
    if receipt is None:
        return {
            "status": "not-installed",
            "target": str(root),
            "files": [],
        }

    actions: list[dict[str, Any]] = []
    retained: list[InstallEntry] = []
    for entry in receipt.files:
        path = root / entry.path
        if not path.exists():
            actions.append(
                {"path": entry.path, "action": "already-missing"}
            )
            continue

        current_sha = _sha(path.read_bytes())
        if current_sha != entry.sha256 and not force:
            retained.append(entry)
            actions.append(
                {
                    "path": entry.path,
                    "action": "keep-modified",
                    "reason": "contents changed after installation",
                }
            )
            continue

        if entry.backup:
            backup_path = root / entry.backup
            if backup_path.exists():
                actions.append(
                    {
                        "path": entry.path,
                        "action": "restore-backup",
                    }
                )
                if not dry_run:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_path, path)
                    backup_path.unlink(missing_ok=True)
                continue

        if entry.created:
            actions.append({"path": entry.path, "action": "remove"})
            if not dry_run:
                path.unlink(missing_ok=True)
                _remove_empty_parents(path.parent, root)
        else:
            actions.append(
                {
                    "path": entry.path,
                    "action": "keep-preexisting",
                }
            )

    if not dry_run:
        receipt_path = _receipt_path(root)
        if retained:
            receipt_path.write_text(
                json.dumps(
                    InstallReceipt(
                        version=1,
                        files=retained,
                    ).to_dict(),
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        else:
            receipt_path.unlink(missing_ok=True)
            backup_root = root / ".cascade" / "install-backups"
            _remove_empty_parents(backup_root, root)
            _remove_empty_parents(
                receipt_path.parent,
                root,
            )

    return {
        "status": (
            "dry-run"
            if dry_run
            else ("partial" if retained else "uninstalled")
        ),
        "target": str(root),
        "files": actions,
    }

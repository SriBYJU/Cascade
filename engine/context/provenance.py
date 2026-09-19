from __future__ import annotations

from pathlib import PurePosixPath

from ..schemas import Provenance, TrustLevel


TRUSTED_POLICY_NAMES = {"policy.lock.yaml", ".codex-plugin/plugin.json"}
PROJECT_INSTRUCTION_NAMES = {"AGENTS.md", "AGENTS.override.md"}


def provenance_for_path(path: str) -> Provenance:
    p = PurePosixPath(path)
    if p.name in TRUSTED_POLICY_NAMES:
        trust = TrustLevel.TRUSTED_POLICY
    elif p.name in PROJECT_INSTRUCTION_NAMES:
        trust = TrustLevel.PROJECT_INSTRUCTION
    else:
        trust = TrustLevel.UNTRUSTED_DATA
    return Provenance(source_type="repository", source_id=path, trust=trust, scope=str(p.parent))

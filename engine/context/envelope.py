from __future__ import annotations

from ..schemas import Capability, EvidenceRef, TaskEnvelope


def build_envelope(
    *,
    task_id: str,
    role: str,
    goal: str,
    evidence: list[EvidenceRef],
    capability: Capability,
    allowed_paths: list[str] | None = None,
    forbidden_paths: list[str] | None = None,
    constraints: list[str] | None = None,
    done_when: list[str] | None = None,
    max_attempts: int = 2,
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        role=role,
        goal=goal,
        allowed_paths=allowed_paths or ["**"],
        forbidden_paths=forbidden_paths or [],
        evidence=evidence,
        constraints=constraints or [],
        done_when=done_when or [],
        capability=capability,
        max_attempts=max_attempts,
    )

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..policy_lock import load_policy, policy_digest, write_proposal
from ..schemas import (
    Capability,
    PolicyCertificate,
    PolicyLock,
    PolicyRoute,
    ReasoningEffort,
)
from ..state.db import StateDB
from .learner import AdmittedEvidenceStore


EFFORT_FOR_CAPABILITY: dict[Capability, ReasoningEffort] = {
    Capability.NO_MODEL: ReasoningEffort.MINIMAL,
    Capability.QUICK: ReasoningEffort.LOW,
    Capability.EXPLORE: ReasoningEffort.LOW,
    Capability.BUILD: ReasoningEffort.MEDIUM,
    Capability.DEBUG: ReasoningEffort.HIGH,
    Capability.DEEP: ReasoningEffort.HIGH,
    Capability.CRITICAL: ReasoningEffort.XHIGH,
}


def evidence_snapshot(db: StateDB) -> str:
    rows = db.query(
        """SELECT id,task_class,capability,success,evaluator,metrics_json,created_at
           FROM admitted_evidence ORDER BY id"""
    )
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def compile_policy_proposal(
    current: PolicyLock,
    store: AdmittedEvidenceStore,
    *,
    minimum_samples: int = 20,
    success_floor: float = 0.95,
    benchmark_suite: str,
    quality_delta: float | None = None,
    weighted_usage_delta: float | None = None,
) -> PolicyLock:
    proposed_routes = dict(current.routes)
    suggestions = store.propose(
        minimum_samples=minimum_samples,
        success_floor=success_floor,
    )
    for task_class, capability_name in suggestions.items():
        if task_class not in proposed_routes:
            continue
        capability = Capability(capability_name)
        proposed_routes[task_class] = PolicyRoute(
            target=capability,
            effort=EFFORT_FOR_CAPABILITY[capability],
        )

    return PolicyLock(
        version=current.version + 1,
        base_evidence_snapshot=evidence_snapshot(store.db),
        routes=proposed_routes,
        guards=dict(current.guards),
        certificate=PolicyCertificate(
            benchmark_suite=benchmark_suite,
            quality_delta=quality_delta,
            weighted_usage_delta=weighted_usage_delta,
        ),
        status="proposal",
        note=(
            f"Generated from admitted evidence with minimum_samples={minimum_samples} "
            f"and success_floor={success_floor:.3f}. Explicit activation required."
        ),
    )


def policy_diff(current: PolicyLock, candidate: PolicyLock) -> dict[str, Any]:
    changed_routes: dict[str, dict[str, Any]] = {}
    route_keys = sorted(set(current.routes) | set(candidate.routes))
    for key in route_keys:
        before = current.routes.get(key)
        after = candidate.routes.get(key)
        if before == after:
            continue
        changed_routes[key] = {
            "before": before.model_dump(mode="json") if before else None,
            "after": after.model_dump(mode="json") if after else None,
        }
    return {
        "from_version": current.version,
        "to_version": candidate.version,
        "from_digest": policy_digest(current),
        "to_digest": policy_digest(candidate),
        "changed_routes": changed_routes,
        "base_evidence_snapshot": candidate.base_evidence_snapshot,
        "certificate": candidate.certificate.model_dump(mode="json"),
        "candidate_status": candidate.status,
    }


def activation_ready(candidate: PolicyLock) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if candidate.status != "proposal":
        reasons.append("candidate status must be proposal")
    if not candidate.base_evidence_snapshot.startswith("sha256:"):
        reasons.append("candidate must reference a hashed admitted-evidence snapshot")
    if candidate.certificate.quality_delta is None:
        reasons.append("quality_delta is missing")
    if candidate.certificate.weighted_usage_delta is None:
        reasons.append("weighted_usage_delta is missing")
    if candidate.certificate.benchmark_suite in {
        "",
        "bootstrap",
        "bootstrap-unmeasured",
    }:
        reasons.append("benchmark suite is not a measured evaluation suite")
    return not reasons, reasons


def activate_policy(
    *,
    active_path: str | Path,
    proposal_path: str | Path,
    approval_digest: str,
) -> PolicyLock:
    current = load_policy(active_path)
    candidate = load_policy(proposal_path)
    digest = policy_digest(candidate)
    if approval_digest != digest:
        raise PermissionError(
            "approval digest does not match the exact policy proposal"
        )
    ready, reasons = activation_ready(candidate)
    if not ready:
        raise ValueError("policy proposal is not activation-ready: " + "; ".join(reasons))
    if candidate.version <= current.version:
        raise ValueError("policy proposal version must advance the active version")
    activated = candidate.model_copy(
        update={
            "status": "active",
            "note": (
                (candidate.note or "")
                + " Activated explicitly after digest approval."
            ).strip(),
        }
    )
    write_proposal(activated, active_path)
    return activated

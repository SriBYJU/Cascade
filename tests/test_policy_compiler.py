from pathlib import Path

import pytest

from engine.policy_lock import load_policy, policy_digest, write_proposal
from engine.router.learner import AdmittedEvidenceStore
from engine.router.policy_compiler import (
    activate_policy,
    activation_ready,
    compile_policy_proposal,
    policy_diff,
)
from engine.schemas import (
    Capability,
    PolicyCertificate,
    PolicyLock,
    PolicyRoute,
    ReasoningEffort,
)
from engine.state.db import StateDB


def _active() -> PolicyLock:
    return PolicyLock(
        version=1,
        base_evidence_snapshot="bootstrap",
        routes={
            "build": PolicyRoute(
                target=Capability.BUILD,
                effort=ReasoningEffort.MEDIUM,
            )
        },
        guards={"auth_or_security": Capability.DEEP},
        certificate=PolicyCertificate(
            benchmark_suite="bootstrap-unmeasured",
            quality_delta=None,
            weighted_usage_delta=None,
        ),
        status="bootstrap",
    )


def test_untrusted_worker_self_report_cannot_enter_evidence(tmp_path: Path):
    store = AdmittedEvidenceStore(StateDB(tmp_path / "state.db"))
    with pytest.raises(ValueError):
        store.admit(
            "build",
            "quick",
            True,
            "worker-self-report",
            {},
        )


def test_policy_proposal_is_reviewable_and_not_auto_active(tmp_path: Path):
    store = AdmittedEvidenceStore(StateDB(tmp_path / "state.db"))
    for _ in range(20):
        store.admit(
            "build",
            "build",
            True,
            "tests",
            {"verified": True},
        )
    candidate = compile_policy_proposal(
        _active(),
        store,
        benchmark_suite="routing-regression-v2",
        quality_delta=0.0,
        weighted_usage_delta=-0.2,
    )
    ready, reasons = activation_ready(candidate)
    assert ready is True
    assert reasons == []
    assert candidate.status == "proposal"
    assert candidate.base_evidence_snapshot.startswith("sha256:")
    diff = policy_diff(_active(), candidate)
    assert diff["to_version"] == 2


def test_activation_requires_exact_digest_and_measured_certificate(
    tmp_path: Path,
):
    active_path = tmp_path / "policy.lock.yaml"
    proposal_path = tmp_path / "proposal.json"
    write_proposal(_active(), active_path)

    candidate = _active().model_copy(
        update={
            "version": 2,
            "base_evidence_snapshot": "sha256:" + "a" * 64,
            "status": "proposal",
            "certificate": PolicyCertificate(
                benchmark_suite="routing-regression-v2",
                quality_delta=0.0,
                weighted_usage_delta=-0.1,
            ),
        }
    )
    write_proposal(candidate, proposal_path)

    with pytest.raises(PermissionError):
        activate_policy(
            active_path=active_path,
            proposal_path=proposal_path,
            approval_digest="wrong",
        )

    activated = activate_policy(
        active_path=active_path,
        proposal_path=proposal_path,
        approval_digest=policy_digest(candidate),
    )
    assert activated.status == "active"
    assert load_policy(active_path).status == "active"


def test_unmeasured_proposal_cannot_activate(tmp_path: Path):
    active_path = tmp_path / "policy.lock.yaml"
    proposal_path = tmp_path / "proposal.json"
    write_proposal(_active(), active_path)
    candidate = _active().model_copy(
        update={
            "version": 2,
            "base_evidence_snapshot": "sha256:" + "b" * 64,
            "status": "proposal",
        }
    )
    write_proposal(candidate, proposal_path)
    ready, reasons = activation_ready(candidate)
    assert ready is False
    assert any("quality_delta" in reason for reason in reasons)

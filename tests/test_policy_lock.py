from pathlib import Path

from engine.policy_lock import load_policy, policy_digest


def test_policy_lock_is_reviewable():
    p = load_policy(Path(__file__).parents[1] / "policy.lock.yaml")
    assert p.status == "bootstrap"
    assert p.certificate.quality_delta is None
    assert len(policy_digest(p)) == 64

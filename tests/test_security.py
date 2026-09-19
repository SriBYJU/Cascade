import pytest

from engine.schemas import ToolRisk
from engine.tools.permissions import PermissionPolicy
from engine.tools.risk import classify_command


def test_destructive_requires_approval():
    risk = classify_command(["rm", "-rf", "x"])
    assert risk == ToolRisk.DESTRUCTIVE
    with pytest.raises(PermissionError):
        PermissionPolicy().check(risk)


def test_external_retry_requires_idempotency():
    policy = PermissionPolicy(allowed={ToolRisk.EXTERNAL_SIDE_EFFECT})
    with pytest.raises(PermissionError):
        policy.check(ToolRisk.EXTERNAL_SIDE_EFFECT, approved=True, retry=True, has_idempotency_key=False)

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import ToolRisk
from .risk import DEFAULT_POLICIES


@dataclass(slots=True)
class PermissionPolicy:
    allowed: set[ToolRisk] = field(default_factory=lambda: {
        ToolRisk.READ_ONLY,
        ToolRisk.LOCAL_WRITE,
        ToolRisk.REPO_WRITE,
        ToolRisk.NETWORK_READ,
    })

    def check(self, risk: ToolRisk, *, approved: bool = False, has_idempotency_key: bool = False, retry: bool = False) -> None:
        policy = DEFAULT_POLICIES[risk]
        if risk not in self.allowed and not approved:
            raise PermissionError(f"tool risk {risk.value} is not allowed without explicit approval")
        if policy.requires_explicit_approval and not approved:
            raise PermissionError(f"tool risk {risk.value} requires explicit approval")
        if retry and not policy.retry_without_idempotency and not has_idempotency_key:
            raise PermissionError(f"retry for {risk.value} requires an idempotency key")

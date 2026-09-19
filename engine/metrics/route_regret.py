from __future__ import annotations

from dataclasses import dataclass

from ..router.capability_registry import CapabilityRegistry
from ..router.learner import EvidenceSummary
from ..schemas import Capability


@dataclass(frozen=True, slots=True)
class RegretResult:
    chosen: Capability
    best_known: Capability
    regret: int

    @property
    def over_routed(self) -> bool:
        return self.regret > 0

    @property
    def under_routed(self) -> bool:
        return self.regret < 0


def best_known_capability(
    summaries: list[EvidenceSummary],
    task_class: str,
    *,
    minimum_samples: int = 20,
    success_floor: float = 0.95,
) -> Capability | None:
    eligible: list[Capability] = []
    for item in summaries:
        if item.task_class != task_class:
            continue
        if item.samples < minimum_samples:
            continue
        if item.success_rate < success_floor:
            continue
        try:
            eligible.append(Capability(item.capability))
        except ValueError:
            continue
    if not eligible:
        return None
    return min(
        eligible,
        key=CapabilityRegistry.order,
    )


def route_regret(
    chosen: Capability,
    best_known: Capability,
) -> RegretResult:
    return RegretResult(
        chosen=chosen,
        best_known=best_known,
        regret=(
            CapabilityRegistry.order(chosen)
            - CapabilityRegistry.order(best_known)
        ),
    )

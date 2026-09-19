from __future__ import annotations

from ..schemas import (
    Capability,
    ReasoningEffort,
    RiskLevel,
    RouteFeatures,
    StepType,
)
from .capability_registry import CapabilityRegistry

DEFAULT_EFFORT = {
    Capability.NO_MODEL: ReasoningEffort.MINIMAL,
    Capability.QUICK: ReasoningEffort.LOW,
    Capability.EXPLORE: ReasoningEffort.LOW,
    Capability.BUILD: ReasoningEffort.MEDIUM,
    Capability.DEBUG: ReasoningEffort.HIGH,
    Capability.DEEP: ReasoningEffort.HIGH,
    Capability.CRITICAL: ReasoningEffort.XHIGH,
}


def minimum_capability(features: RouteFeatures) -> Capability:
    if (
        features.deterministic_candidate
        and features.step_type == StepType.VERIFY
    ):
        return Capability.NO_MODEL
    if features.risk == RiskLevel.CRITICAL:
        return Capability.CRITICAL
    if (
        features.security_sensitive
        or features.data_migration
        or features.risk == RiskLevel.HIGH
    ):
        return Capability.DEEP
    if features.step_type == StepType.DEBUG:
        return Capability.DEBUG
    if features.step_type == StepType.INTEGRATE:
        return (
            Capability.BUILD
            if features.has_strong_validation
            else Capability.DEEP
        )
    if features.step_type in {StepType.BUILD, StepType.TRANSFORM}:
        if features.ambiguity and not features.has_strong_validation:
            return Capability.DEEP
        if (
            len(features.predicted_write_files) > 3
            and not features.has_tests
        ):
            return Capability.DEEP
        return Capability.BUILD
    if features.step_type == StepType.EXPLORE:
        text = features.task_text.lower()
        lightweight_read = any(
            phrase in text
            for phrase in (
                "summarize",
                "function signature",
                "signatures",
                "explain this function",
            )
        )
        if (
            lightweight_read
            and features.relevant_files <= 3
            and not features.ambiguity
        ):
            return Capability.QUICK
        return Capability.EXPLORE
    return Capability.QUICK


def choose_effort(
    capability: Capability,
    features: RouteFeatures,
) -> ReasoningEffort:
    effort = DEFAULT_EFFORT[capability]
    if capability == Capability.NO_MODEL:
        return effort
    if (
        features.has_strong_validation
        and features.risk == RiskLevel.LOW
    ):
        if effort == ReasoningEffort.MEDIUM:
            return ReasoningEffort.LOW
        if effort == ReasoningEffort.HIGH:
            return ReasoningEffort.MEDIUM
    if (
        features.ambiguity
        and capability
        in {Capability.BUILD, Capability.DEBUG, Capability.DEEP}
    ):
        return ReasoningEffort.HIGH
    return effort


def clamp_capability(
    candidate: Capability,
    floor: Capability,
) -> Capability:
    return (
        candidate
        if CapabilityRegistry.order(candidate)
        >= CapabilityRegistry.order(floor)
        else floor
    )

from engine.metrics.route_regret import (
    best_known_capability,
    route_regret,
)
from engine.router.learner import EvidenceSummary
from engine.schemas import Capability


def test_best_known_capability_uses_cheapest_tier_meeting_floor():
    summaries = [
        EvidenceSummary("build", "quick", 30, 0.80),
        EvidenceSummary("build", "build", 30, 0.97),
        EvidenceSummary("build", "deep", 30, 1.0),
    ]
    best = best_known_capability(summaries, "build")
    assert best == Capability.BUILD


def test_regret_positive_for_overrouting():
    result = route_regret(
        Capability.DEEP,
        Capability.BUILD,
    )
    assert result.regret > 0
    assert result.over_routed is True
    assert result.under_routed is False


def test_regret_negative_for_underrouting():
    result = route_regret(
        Capability.QUICK,
        Capability.BUILD,
    )
    assert result.regret < 0
    assert result.under_routed is True


def test_no_best_known_without_enough_admitted_evidence():
    summaries = [
        EvidenceSummary("build", "build", 3, 1.0),
    ]
    assert best_known_capability(summaries, "build") is None

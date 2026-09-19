import pytest

from engine.evaluation.savings import (
    render_savings,
    savings_summary,
)


def _report(candidate_quality: float = 0.96) -> dict:
    return {
        "measured": True,
        "source_commit": "abc123",
        "case_ids": ["a", "b"],
        "repeats": 3,
        "summary": {
            "plain": {
                "trials": 6,
                "verified_success_rate": 0.96,
                "total_model_tokens_mean": 10000.0,
                "weighted_usage_mean": 8000.0,
                "head_model_tokens_mean": 10000.0,
                "context_bytes_mean": 20000.0,
                "agent_calls_mean": 1.0,
                "wall_time_ms_mean": 1000.0,
                "cached_input_tokens_mean": 100.0,
            },
            "cascade": {
                "trials": 6,
                "verified_success_rate": candidate_quality,
                "total_model_tokens_mean": 3700.0,
                "weighted_usage_mean": 2400.0,
                "head_model_tokens_mean": 1800.0,
                "context_bytes_mean": 9000.0,
                "agent_calls_mean": 2.0,
                "wall_time_ms_mean": 720.0,
                "cached_input_tokens_mean": 600.0,
            },
        },
    }


def test_savings_turns_negative_delta_into_positive_headline():
    result = savings_summary(_report())
    assert result["token_savings_percent"] == pytest.approx(63.0)
    assert result["weighted_usage_savings_percent"] == pytest.approx(70.0)
    assert result["wall_time_savings_percent"] == pytest.approx(28.0)
    assert result["head_model_token_savings_percent"] == pytest.approx(82.0)
    assert result["context_transfer_savings_percent"] == pytest.approx(55.0)
    assert result["tokens_saved_mean"] == pytest.approx(6300.0)
    assert result["token_claim_eligible"] is True


def test_lower_quality_blocks_equal_quality_savings_claim():
    result = savings_summary(_report(candidate_quality=0.90))
    assert result["token_savings_percent"] == pytest.approx(63.0)
    assert result["quality_delta_percentage_points"] == pytest.approx(-6.0)
    assert result["token_claim_eligible"] is False
    rendered = render_savings(result)
    assert "do not describe token reduction as equal-quality" in rendered


def test_rendered_savings_is_immediately_readable():
    rendered = render_savings(savings_summary(_report()))
    assert "CASCADE SAVINGS" in rendered
    assert "Token savings:             63.0%" in rendered
    assert "Weighted model-use saving: 70.0%" in rendered
    assert "Head-model token saving:   82.0%" in rendered
    assert "Context-transfer saving:   55.0%" in rendered
    assert "Verified success:         96.0% vs 96.0%" in rendered
    assert "6 matched comparisons" in rendered


def test_unmeasured_report_is_rejected():
    with pytest.raises(ValueError):
        savings_summary({"measured": False, "summary": {}})


def test_mismatched_trials_are_rejected():
    report = _report()
    report["summary"]["cascade"]["trials"] = 5
    with pytest.raises(ValueError):
        savings_summary(report)



def test_public_claim_requires_release_grade_evidence():
    result = savings_summary(_report())
    assert result["token_claim_eligible"] is True
    assert result["release_grade_evidence"] is False
    assert result["public_token_claim_eligible"] is False
    assert "not release-grade evidence" in render_savings(result)


def test_public_claim_unlocks_only_with_release_grade_metadata():
    report = _report()
    report["case_ids"] = [f"case-{index}" for index in range(20)]
    report["summary"]["plain"]["trials"] = 60
    report["summary"]["cascade"]["trials"] = 60
    report["environment"] = {"python": "3.12"}
    report["policy_lock"] = {"digest": "abc"}

    result = savings_summary(report)

    assert result["release_grade_evidence"] is True
    assert result["public_token_claim_eligible"] is True
    assert "release-grade measured token reduction" in render_savings(
        result
    )

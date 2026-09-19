from engine.evaluation.report import (
    compare_summaries,
    render_markdown_report,
)


def _summary() -> dict:
    return {
        "plain": {
            "trials": 6,
            "verified_success_rate": 1.0,
            "weighted_usage_mean": 100.0,
            "total_model_tokens_mean": 100.0,
            "wall_time_ms_mean": 1000.0,
            "cached_input_tokens_mean": 10.0,
        },
        "cascade": {
            "trials": 6,
            "verified_success_rate": 1.0,
            "weighted_usage_mean": 75.0,
            "total_model_tokens_mean": 90.0,
            "wall_time_ms_mean": 800.0,
            "cached_input_tokens_mean": 30.0,
        },
    }


def test_compare_summaries_reports_relative_deltas():
    comparisons = compare_summaries(_summary())
    cascade = comparisons["cascade"]
    assert cascade["quality_delta"] == 0.0
    assert cascade["weighted_usage_delta"] == -0.25
    assert cascade["total_model_tokens_delta"] == -0.1
    assert cascade["wall_time_delta"] == -0.2
    assert cascade["cached_input_tokens_delta"] == 20.0


def test_markdown_report_labels_measured_values():
    report = {
        "measured": True,
        "source_commit": "abc",
        "model": "auto",
        "reasoning_effort": "medium",
        "case_ids": ["one"],
        "repeats": 2,
        "configs": ["plain", "cascade"],
        "summary": _summary(),
        "environment": {"python": "3.12"},
        "policy_lock": {"digest": "xyz"},
    }
    rendered = render_markdown_report(report)
    assert "Measurement status:** measured" in rendered
    assert "Relative to plain baseline" in rendered
    assert "-25.00%" in rendered
    assert "does not convert targets or estimates" in rendered


def test_unmeasured_markdown_does_not_invent_numbers():
    rendered = render_markdown_report(
        {
            "measured": False,
            "reason": "Codex unavailable",
        }
    )
    assert "not measured" in rendered
    assert "Codex unavailable" in rendered



def test_vwet_is_derived_from_verified_work_and_weighted_usage():
    from engine.evaluation.models import TrialResult, aggregate_trials

    summary = aggregate_trials(
        [
            TrialResult(
                case_id="a",
                category="x",
                config="cascade",
                repeat=1,
                verified_success=True,
                failure_kind=None,
                wall_time_ms=1,
                weighted_usage=500.0,
            ),
            TrialResult(
                case_id="b",
                category="x",
                config="cascade",
                repeat=1,
                verified_success=False,
                failure_kind="task",
                wall_time_ms=1,
                weighted_usage=500.0,
            ),
        ]
    )
    assert summary["cascade"][
        "verified_work_per_1k_weighted_tokens"
    ] == 1.0

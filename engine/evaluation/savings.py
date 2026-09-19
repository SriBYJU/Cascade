from __future__ import annotations

from typing import Any


def _number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _saved_percent(baseline: float, candidate: float) -> float | None:
    if baseline <= 0:
        return None
    return (1.0 - (candidate / baseline)) * 100.0


def savings_summary(
    report: dict[str, Any],
    *,
    baseline: str = "plain",
    candidate: str = "cascade",
) -> dict[str, Any]:
    if report.get("measured") is not True:
        raise ValueError("savings require a measured benchmark report")

    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("benchmark report has no summary")
    baseline_data = summary.get(baseline)
    candidate_data = summary.get(candidate)
    if not isinstance(baseline_data, dict):
        raise ValueError(f"benchmark report has no {baseline!r} baseline")
    if not isinstance(candidate_data, dict):
        raise ValueError(f"benchmark report has no {candidate!r} candidate")

    baseline_trials = int(_number(baseline_data.get("trials")))
    candidate_trials = int(_number(candidate_data.get("trials")))
    if baseline_trials <= 0 or candidate_trials <= 0:
        raise ValueError("savings require non-empty baseline and candidate trials")
    if baseline_trials != candidate_trials:
        raise ValueError(
            "savings require matched baseline and candidate trial counts"
        )

    baseline_tokens = _number(
        baseline_data.get("total_model_tokens_mean")
    )
    candidate_tokens = _number(
        candidate_data.get("total_model_tokens_mean")
    )
    baseline_weighted = _number(
        baseline_data.get("weighted_usage_mean")
    )
    candidate_weighted = _number(
        candidate_data.get("weighted_usage_mean")
    )
    baseline_wall = _number(
        baseline_data.get("wall_time_ms_mean")
    )
    candidate_wall = _number(
        candidate_data.get("wall_time_ms_mean")
    )
    baseline_quality = _number(
        baseline_data.get("verified_success_rate")
    )
    candidate_quality = _number(
        candidate_data.get("verified_success_rate")
    )
    baseline_cached = _number(
        baseline_data.get("cached_input_tokens_mean")
    )
    candidate_cached = _number(
        candidate_data.get("cached_input_tokens_mean")
    )

    token_savings = _saved_percent(
        baseline_tokens,
        candidate_tokens,
    )
    weighted_savings = _saved_percent(
        baseline_weighted,
        candidate_weighted,
    )
    wall_savings = _saved_percent(
        baseline_wall,
        candidate_wall,
    )
    quality_delta_pp = (
        candidate_quality - baseline_quality
    ) * 100.0

    equal_or_better_quality = candidate_quality >= baseline_quality
    token_claim_eligible = (
        token_savings is not None
        and token_savings > 0
        and equal_or_better_quality
    )
    weighted_claim_eligible = (
        weighted_savings is not None
        and weighted_savings > 0
        and equal_or_better_quality
    )

    return {
        "measured": True,
        "baseline": baseline,
        "candidate": candidate,
        "matched_trials": baseline_trials,
        "cases": len(report.get("case_ids", []))
        if isinstance(report.get("case_ids"), list)
        else 0,
        "repeats": int(_number(report.get("repeats"))),
        "source_commit": report.get("source_commit"),
        "token_savings_percent": token_savings,
        "weighted_usage_savings_percent": weighted_savings,
        "wall_time_savings_percent": wall_savings,
        "baseline_tokens_mean": baseline_tokens,
        "candidate_tokens_mean": candidate_tokens,
        "tokens_saved_mean": baseline_tokens - candidate_tokens,
        "baseline_weighted_usage_mean": baseline_weighted,
        "candidate_weighted_usage_mean": candidate_weighted,
        "baseline_wall_time_ms_mean": baseline_wall,
        "candidate_wall_time_ms_mean": candidate_wall,
        "baseline_verified_success_percent": baseline_quality * 100.0,
        "candidate_verified_success_percent": candidate_quality * 100.0,
        "quality_delta_percentage_points": quality_delta_pp,
        "cached_input_tokens_delta_mean": (
            candidate_cached - baseline_cached
        ),
        "equal_or_better_quality": equal_or_better_quality,
        "token_claim_eligible": token_claim_eligible,
        "weighted_usage_claim_eligible": weighted_claim_eligible,
    }


def _fmt_percent(value: object) -> str:
    if value is None:
        return "n/a"
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{float(value):.1f}%"


def render_savings(summary: dict[str, Any]) -> str:
    baseline = str(summary.get("baseline", "plain"))
    candidate = str(summary.get("candidate", "cascade"))
    token = summary.get("token_savings_percent")
    weighted = summary.get("weighted_usage_savings_percent")
    wall = summary.get("wall_time_savings_percent")
    quality_delta = summary.get("quality_delta_percentage_points")
    cached_delta = summary.get("cached_input_tokens_delta_mean")

    lines = [
        "CASCADE SAVINGS",
        f"Compared with: {baseline}",
        "",
        f"Token savings:             {_fmt_percent(token)}",
        f"Weighted model-use saving: {_fmt_percent(weighted)}",
        f"Wall-time saving:          {_fmt_percent(wall)}",
        (
            "Verified success:         "
            f"{float(summary.get('candidate_verified_success_percent', 0.0)):.1f}% "
            f"vs {float(summary.get('baseline_verified_success_percent', 0.0)):.1f}%"
        ),
        (
            "Quality delta:            "
            f"{float(quality_delta or 0.0):+.1f} percentage points"
        ),
        (
            "Cached-input delta:       "
            f"{float(cached_delta or 0.0):+.0f} tokens/run"
        ),
        "",
        (
            f"{int(summary.get('cases', 0))} cases × "
            f"{int(summary.get('repeats', 0))} repeats = "
            f"{int(summary.get('matched_trials', 0))} matched comparisons"
        ),
        f"Source commit: {summary.get('source_commit') or 'unknown'}",
    ]

    if summary.get("token_claim_eligible"):
        lines.extend(
            [
                "",
                (
                    "CLAIM STATUS: measured token reduction with "
                    "equal-or-better verified success."
                ),
            ]
        )
    else:
        lines.extend(
            [
                "",
                (
                    "CLAIM STATUS: do not describe token reduction as "
                    "equal-quality savings from this report."
                ),
            ]
        )
    return "\n".join(lines)

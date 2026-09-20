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
    baseline_head = _number(
        baseline_data.get("head_model_tokens_mean")
    )
    candidate_head = _number(
        candidate_data.get("head_model_tokens_mean")
    )
    baseline_context = _number(
        baseline_data.get("context_bytes_mean")
    )
    candidate_context = _number(
        candidate_data.get("context_bytes_mean")
    )
    baseline_agents = _number(
        baseline_data.get("agent_calls_mean")
    )
    candidate_agents = _number(
        candidate_data.get("agent_calls_mean")
    )
    baseline_vwet = baseline_data.get(
        "verified_work_per_1k_weighted_tokens"
    )
    candidate_vwet = candidate_data.get(
        "verified_work_per_1k_weighted_tokens"
    )
    baseline_vwet_num = (
        float(baseline_vwet)
        if isinstance(baseline_vwet, (int, float))
        else 0.0
    )
    candidate_vwet_num = (
        float(candidate_vwet)
        if isinstance(candidate_vwet, (int, float))
        else 0.0
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
    head_savings = _saved_percent(
        baseline_head,
        candidate_head,
    )
    context_savings = _saved_percent(
        baseline_context,
        candidate_context,
    )
    vwet_improvement = (
        (
            (candidate_vwet_num - baseline_vwet_num)
            / baseline_vwet_num
        )
        * 100.0
        if baseline_vwet_num > 0
        else None
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

    case_ids = report.get("case_ids", [])
    case_count = len(case_ids) if isinstance(case_ids, list) else 0
    repeats = int(_number(report.get("repeats")))
    source_commit = report.get("source_commit")
    environment = report.get("environment")
    policy_lock = report.get("policy_lock")
    expected_trials = case_count * repeats
    release_grade_evidence = (
        case_count >= 20
        and repeats >= 3
        and baseline_trials == expected_trials
        and candidate_trials == expected_trials
        and isinstance(source_commit, str)
        and bool(source_commit)
        and isinstance(environment, dict)
        and isinstance(policy_lock, dict)
    )
    public_token_claim_eligible = (
        token_claim_eligible and release_grade_evidence
    )
    public_weighted_claim_eligible = (
        weighted_claim_eligible and release_grade_evidence
    )

    model_pool = report.get("model_pool")
    route_cost_weights: dict[str, float] = {}
    if isinstance(model_pool, list):
        for row in model_pool:
            if not isinstance(row, dict):
                continue
            capability = row.get("capability")
            cost_weight = row.get("cost_weight")
            if isinstance(capability, str) and isinstance(
                cost_weight, (int, float)
            ):
                route_cost_weights[capability] = float(cost_weight)

    return {
        "measured": True,
        "baseline": baseline,
        "candidate": candidate,
        "matched_trials": baseline_trials,
        "cases": case_count,
        "repeats": repeats,
        "source_commit": source_commit,
        "token_savings_formula": (
            "100 * (1 - candidate_total_model_tokens / "
            "baseline_total_model_tokens)"
        ),
        "weighted_usage_savings_formula": (
            "100 * (1 - candidate_weighted_usage / "
            "baseline_weighted_usage)"
        ),
        "weighted_usage_definition": {
            "version": "cascade-weighted-usage-v1",
            "formula": (
                "head_tokens*1.0 + sum(worker_tokens*route_cost_weight)"
            ),
            "head_weight": 1.0,
            "route_cost_weights": route_cost_weights,
            "note": (
                "Hypothesis-derived normalized model-use metric; it is "
                "not an OpenAI billing or Codex quota formula."
            ),
        },
        "token_savings_percent": token_savings,
        "weighted_usage_savings_percent": weighted_savings,
        "wall_time_savings_percent": wall_savings,
        "head_model_token_savings_percent": head_savings,
        "context_transfer_savings_percent": context_savings,
        "vwet_improvement_percent": vwet_improvement,
        "baseline_vwet_per_1k": (
            baseline_vwet_num if baseline_vwet_num > 0 else None
        ),
        "candidate_vwet_per_1k": (
            candidate_vwet_num if candidate_vwet_num > 0 else None
        ),
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
        "agent_calls_delta_mean": (
            candidate_agents - baseline_agents
        ),
        "equal_or_better_quality": equal_or_better_quality,
        "token_claim_eligible": token_claim_eligible,
        "weighted_usage_claim_eligible": weighted_claim_eligible,
        "release_grade_evidence": release_grade_evidence,
        "public_token_claim_eligible": public_token_claim_eligible,
        "public_weighted_usage_claim_eligible": (
            public_weighted_claim_eligible
        ),
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
    head = summary.get("head_model_token_savings_percent")
    context = summary.get("context_transfer_savings_percent")
    vwet = summary.get("vwet_improvement_percent")
    quality_delta = summary.get("quality_delta_percentage_points")
    cached_delta = summary.get("cached_input_tokens_delta_mean")

    lines = [
        "CASCADE SAVINGS",
        f"Candidate: {candidate}",
        f"Compared with: {baseline}",
        "",
        f"Token savings:             {_fmt_percent(token)}",
        f"Weighted model-use saving: {_fmt_percent(weighted)}",
        f"Head-model token saving:   {_fmt_percent(head)}",
        f"Context-transfer saving:   {_fmt_percent(context)}",
        f"VWET improvement:          {_fmt_percent(vwet)}",
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

    public_token = summary.get("public_token_claim_eligible")
    public_weighted = summary.get(
        "public_weighted_usage_claim_eligible"
    )
    if public_token or public_weighted:
        lines.extend(["", "EVIDENCE-BACKED HEADLINE"])
        if public_token:
            lines.append(
                "Cascade saves "
                f"{_fmt_percent(token)} of total model tokens vs "
                f"{baseline} at equal-or-better verified success."
            )
        if public_weighted:
            lines.append(
                "Cascade saves "
                f"{_fmt_percent(weighted)} of weighted model usage vs "
                f"{baseline} under cascade-weighted-usage-v1."
            )
        lines.extend(
            [
                "",
                (
                    "TOKEN FORMULA: 100 × (1 - Cascade total tokens / "
                    "plain total tokens)"
                ),
                (
                    "USAGE FORMULA: 100 × (1 - Cascade weighted usage / "
                    "plain weighted usage)"
                ),
                (
                    "USAGE MODEL: head tokens × 1.0 + worker tokens × "
                    "the active route/model cost weight."
                ),
                (
                    "NOTE: weighted model usage is Cascade's "
                    "hypothesis-derived normalized metric, not an OpenAI "
                    "billing or Codex quota formula."
                ),
                "",
                (
                    "CLAIM STATUS: release-grade measured token reduction "
                    "with equal-or-better verified success."
                ),
            ]
        )
    elif summary.get("token_claim_eligible"):
        lines.extend(
            [
                "",
                (
                    "CLAIM STATUS: measured reduction exists, but this "
                    "report is not release-grade evidence for a public "
                    "headline claim."
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

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas import PolicyCertificate


def load_report(path: str | Path) -> dict[str, Any]:
    raw: object = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("benchmark report must be a JSON object")
    return raw


def measured_policy_certificate(
    report: dict[str, Any],
    *,
    baseline: str = "plain",
    candidate: str = "cascade",
) -> PolicyCertificate:
    if report.get("measured") is not True:
        raise ValueError("policy certificate requires a measured benchmark report")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("benchmark report has no summary")
    baseline_data = summary.get(baseline)
    candidate_data = summary.get(candidate)
    if not isinstance(baseline_data, dict) or not isinstance(
        candidate_data, dict
    ):
        raise ValueError(
            f"report must contain both {baseline!r} and {candidate!r}"
        )

    baseline_trials = int(baseline_data.get("trials", 0))
    candidate_trials = int(candidate_data.get("trials", 0))
    if baseline_trials <= 0 or candidate_trials <= 0:
        raise ValueError("certificate requires non-empty baseline/candidate trials")
    if baseline_trials != candidate_trials:
        raise ValueError("baseline and candidate trial counts must match")

    baseline_quality = float(
        baseline_data.get("verified_success_rate", 0.0)
    )
    candidate_quality = float(
        candidate_data.get("verified_success_rate", 0.0)
    )
    quality_delta = candidate_quality - baseline_quality

    baseline_usage = float(
        baseline_data.get("weighted_usage_mean", 0.0)
    )
    candidate_usage = float(
        candidate_data.get("weighted_usage_mean", 0.0)
    )
    if baseline_usage <= 0:
        raise ValueError(
            "baseline weighted usage must be positive for a certificate"
        )
    weighted_usage_delta = (
        candidate_usage - baseline_usage
    ) / baseline_usage

    source_commit = str(report.get("source_commit") or "unknown")
    case_ids = report.get("case_ids", [])
    case_count = len(case_ids) if isinstance(case_ids, list) else 0
    repeats = int(report.get("repeats", 0))
    suite = (
        f"live:{source_commit}:"
        f"{case_count}cases:{repeats}repeats:"
        f"{baseline}-vs-{candidate}"
    )
    return PolicyCertificate(
        benchmark_suite=suite,
        quality_delta=quality_delta,
        weighted_usage_delta=weighted_usage_delta,
    )


def _relative_delta(candidate: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return (candidate - baseline) / baseline


def compare_summaries(
    summary: dict[str, Any],
    *,
    baseline: str = "plain",
) -> dict[str, Any]:
    baseline_data = summary.get(baseline)
    if not isinstance(baseline_data, dict):
        return {}
    fields = {
        "verified_success_rate": "quality_delta",
        "weighted_usage_mean": "weighted_usage_delta",
        "total_model_tokens_mean": "total_model_tokens_delta",
        "wall_time_ms_mean": "wall_time_delta",
    }
    comparisons: dict[str, Any] = {}
    for name, raw in sorted(summary.items()):
        if name == baseline or not isinstance(raw, dict):
            continue
        row: dict[str, Any] = {"baseline": baseline}
        for field, output in fields.items():
            before = float(baseline_data.get(field, 0.0))
            after = float(raw.get(field, 0.0))
            if field == "verified_success_rate":
                row[output] = after - before
            else:
                row[output] = _relative_delta(after, before)
        row["cached_input_tokens_delta"] = (
            float(raw.get("cached_input_tokens_mean", 0.0))
            - float(
                baseline_data.get("cached_input_tokens_mean", 0.0)
            )
        )
        comparisons[name] = row
    return comparisons


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:+.2f}%"


def render_markdown_report(report: dict[str, Any]) -> str:
    if report.get("measured") is not True:
        reason = report.get("reason", "benchmark was not measured")
        return (
            "# Cascade benchmark report\n\n"
            "**Status:** not measured\n\n"
            f"Reason: {reason}\n"
        )
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    comparisons = report.get("comparisons")
    if not isinstance(comparisons, dict):
        comparisons = compare_summaries(summary)
    lines = [
        "# Cascade benchmark report",
        "",
        "**Measurement status:** measured",
        "",
        f"- Source commit: `{report.get('source_commit', 'unknown')}`",
        f"- Model target: `{report.get('model', 'unknown')}`",
        f"- Reasoning effort: `{report.get('reasoning_effort', 'unknown')}`",
        f"- Cases: {len(report.get('case_ids', []))}",
        f"- Repeats: {report.get('repeats', 0)}",
        "",
        "## Configuration results",
        "",
        "| Configuration | Verified success | pass@1 | pass@3 | Weighted usage | Model tokens | Wall time (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for config, raw in sorted(summary.items()):
        if not isinstance(raw, dict):
            continue
        lines.append(
            f"| {config} | "
            f"{float(raw.get('verified_success_rate', 0.0)) * 100:.2f}% | "
            f"{float(raw.get('pass_at_1', 0.0)) * 100:.2f}% | "
            f"{float(raw.get('pass_at_3', 0.0)) * 100:.2f}% | "
            f"{float(raw.get('weighted_usage_mean', 0.0)):.2f} | "
            f"{float(raw.get('total_model_tokens_mean', 0.0)):.2f} | "
            f"{float(raw.get('wall_time_ms_mean', 0.0)):.2f} |"
        )
    if comparisons:
        lines.extend([
            "",
            "## Relative to plain baseline",
            "",
            "| Candidate | Quality Δ | Weighted usage Δ | Token Δ | Wall-time Δ |",
            "|---|---:|---:|---:|---:|",
        ])
        for config, row in sorted(comparisons.items()):
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {config} | {_fmt_percent(row.get('quality_delta'))} | "
                f"{_fmt_percent(row.get('weighted_usage_delta'))} | "
                f"{_fmt_percent(row.get('total_model_tokens_delta'))} | "
                f"{_fmt_percent(row.get('wall_time_delta'))} |"
            )
    lines.extend([
        "",
        "## Reproducibility metadata",
        "",
        "```json",
        json.dumps(
            {
                "environment": report.get("environment"),
                "policy_lock": report.get("policy_lock"),
                "configs": report.get("configs"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        "```",
        "",
        "> This card reports measured values from the attached benchmark report. "
        "It does not convert targets or estimates into performance claims.",
        "",
    ])
    return "\n".join(lines)

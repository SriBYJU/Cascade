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

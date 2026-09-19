import json
from pathlib import Path

import pytest

from engine.evaluation.report import load_report, measured_policy_certificate


def _report() -> dict:
    return {
        "measured": True,
        "source_commit": "abc123",
        "case_ids": ["a", "b"],
        "repeats": 3,
        "summary": {
            "plain": {
                "trials": 6,
                "verified_success_rate": 1.0,
                "weighted_usage_mean": 100.0,
            },
            "cascade": {
                "trials": 6,
                "verified_success_rate": 1.0,
                "weighted_usage_mean": 75.0,
            },
        },
    }


def test_certificate_is_derived_from_measured_report():
    certificate = measured_policy_certificate(_report())
    assert certificate.quality_delta == 0.0
    assert certificate.weighted_usage_delta == -0.25
    assert "abc123" in certificate.benchmark_suite
    assert "2cases" in certificate.benchmark_suite


def test_unmeasured_report_cannot_certify():
    report = _report()
    report["measured"] = False
    with pytest.raises(ValueError):
        measured_policy_certificate(report)


def test_mismatched_trials_cannot_certify():
    report = _report()
    report["summary"]["cascade"]["trials"] = 5
    with pytest.raises(ValueError):
        measured_policy_certificate(report)


def test_load_report_requires_object(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps([]))
    with pytest.raises(ValueError):
        load_report(path)

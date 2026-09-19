from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import CascadeConfig
from .doctor import _agent_probe, _plugin_probe
from .evaluation.models import load_cases
from .evaluation.parallel_live import load_parallel_scenarios
from .evaluation.report import load_report
from .evaluation.savings import savings_summary
from .policy_lock import load_policy, policy_digest


def _check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    detail: str,
    *,
    required: bool = True,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "required": required,
            "detail": detail,
        }
    )


def _benchmark_checks(
    report_path: Path,
    checks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not report_path.exists():
        _check(
            checks,
            "measured-benchmark",
            False,
            f"missing measured report: {report_path}",
        )
        return None

    try:
        report = load_report(report_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _check(
            checks,
            "measured-benchmark",
            False,
            f"could not load report: {exc}",
        )
        return None

    measured = report.get("measured") is True
    _check(
        checks,
        "measured-benchmark",
        measured,
        "report is explicitly measured"
        if measured
        else "report is not marked measured",
    )
    case_ids = report.get("case_ids", [])
    case_count = len(case_ids) if isinstance(case_ids, list) else 0
    _check(
        checks,
        "benchmark-task-count",
        case_count >= 20,
        f"{case_count} live cases (minimum 20)",
    )
    repeats = int(report.get("repeats", 0) or 0)
    _check(
        checks,
        "benchmark-repeats",
        repeats >= 3,
        f"{repeats} repeats (minimum 3)",
    )

    summary = report.get("summary")
    summary_dict = summary if isinstance(summary, dict) else {}
    plain = summary_dict.get("plain")
    cascade = summary_dict.get("cascade")
    matched = isinstance(plain, dict) and isinstance(cascade, dict)
    _check(
        checks,
        "plain-vs-cascade",
        matched,
        "plain and cascade configurations are both present",
    )
    if matched:
        assert isinstance(plain, dict)
        assert isinstance(cascade, dict)
        baseline_quality = float(
            plain.get("verified_success_rate", 0.0)
        )
        candidate_quality = float(
            cascade.get("verified_success_rate", 0.0)
        )
        quality_floor = baseline_quality * 0.95
        _check(
            checks,
            "quality-retention-target",
            candidate_quality >= quality_floor,
            (
                f"Cascade {candidate_quality:.3f}; "
                f"95% of plain baseline = {quality_floor:.3f}"
            ),
            required=False,
        )

    source_commit = str(report.get("source_commit") or "")
    _check(
        checks,
        "benchmark-source-commit",
        bool(source_commit and source_commit != "unknown"),
        source_commit or "missing source commit",
    )
    _check(
        checks,
        "benchmark-environment",
        isinstance(report.get("environment"), dict),
        "toolchain/environment metadata present",
    )
    _check(
        checks,
        "benchmark-policy-lock",
        isinstance(report.get("policy_lock"), dict),
        "policy-lock metadata present",
    )
    trials = report.get("trials", [])
    raw_trace_count = 0
    if isinstance(trials, list):
        raw_trace_count = sum(
            1
            for trial in trials
            if isinstance(trial, dict) and trial.get("raw_trace")
        )
    _check(
        checks,
        "raw-trajectories",
        bool(trials) and raw_trace_count == len(trials),
        (
            f"{raw_trace_count}/{len(trials) if isinstance(trials, list) else 0} "
            "trials reference raw trajectories"
        ),
    )

    try:
        return savings_summary(report)
    except ValueError:
        return None


def release_gate(
    repo_root: str | Path = ".",
    *,
    benchmark_report: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    checks: list[dict[str, Any]] = []

    plugin = _plugin_probe(root)
    _check(
        checks,
        "portable-plugin",
        bool(plugin.get("portable_valid")),
        "portable plugin.json valid",
    )
    _check(
        checks,
        "compat-plugin",
        bool(plugin.get("compat_valid")),
        "compatibility plugin manifest valid",
    )
    _check(
        checks,
        "plugin-identity",
        bool(plugin.get("identity_match")),
        "portable/compat plugin identity matches",
    )

    agents = _agent_probe(root)
    _check(
        checks,
        "six-agents",
        bool(agents.get("required_agents_present")),
        (
            "all six required agents present"
            if agents.get("required_agents_present")
            else f"missing: {agents.get('missing_agents')}"
        ),
    )

    config = CascadeConfig.load(root)
    _check(
        checks,
        "privacy-default",
        config.trace_content == "metadata_only",
        f"trace_content={config.trace_content}",
    )
    _check(
        checks,
        "bounded-concurrency",
        1 <= config.max_concurrent_workers <= 3,
        f"max_concurrent_workers={config.max_concurrent_workers}",
    )

    live_manifest = root / "benchmarks" / "fixtures" / "live_tasks.json"
    cases = load_cases(live_manifest)
    _check(
        checks,
        "live-suite-size",
        len(cases) >= 20,
        f"{len(cases)} deterministic live cases",
    )
    _check(
        checks,
        "live-suite-acceptance",
        all(case.acceptance or case.answer_contains for case in cases),
        "every live case has deterministic/answer acceptance",
    )

    parallel_manifest = (
        root / "benchmarks" / "fixtures" / "parallel_live.json"
    )
    scenarios = load_parallel_scenarios(parallel_manifest)
    _check(
        checks,
        "parallel-live-suite",
        len(scenarios) >= 2,
        f"{len(scenarios)} parallel live scenarios",
    )

    policy = load_policy(root / "policy.lock.yaml")
    _check(
        checks,
        "policy-lock-digest",
        len(policy_digest(policy)) == 64,
        f"policy version={policy.version} status={policy.status}",
    )

    workflow = (
        root / ".github" / "workflows" / "ci.yml"
    ).read_text()
    cross_platform = all(
        marker in workflow
        for marker in (
            "ubuntu-latest",
            "macos-latest",
            "windows-latest",
            '"3.11"',
            '"3.12"',
            '"3.13"',
        )
    )
    _check(
        checks,
        "cross-platform-ci-matrix",
        cross_platform,
        "Linux/macOS/Windows × Python 3.11/3.12/3.13",
    )

    release_workflow = (
        root / ".github" / "workflows" / "release.yml"
    ).read_text()
    trusted_release = all(
        marker in release_workflow
        for marker in (
            "id-token: write",
            "actions/attest@",
            "pypa/gh-action-pypi-publish@",
        )
    )
    _check(
        checks,
        "trusted-release",
        trusted_release,
        "OIDC publishing and artifact attestation configured",
    )

    savings: dict[str, Any] | None = None
    if benchmark_report is not None:
        report_path = Path(benchmark_report)
        if not report_path.is_absolute():
            report_path = root / report_path
        savings = _benchmark_checks(report_path, checks)

    required_failures = [
        item
        for item in checks
        if item["required"] and not item["passed"]
    ]
    optional_failures = [
        item
        for item in checks
        if not item["required"] and not item["passed"]
    ]
    return {
        "engineering_ready": not required_failures
        if benchmark_report is None
        else not required_failures,
        "measured_release_evidence": benchmark_report is not None
        and not [
            item
            for item in checks
            if item["required"]
            and item["name"].startswith("benchmark")
            and not item["passed"]
        ]
        and not [
            item
            for item in checks
            if item["required"]
            and item["name"] in {"measured-benchmark", "plain-vs-cascade", "raw-trajectories"}
            and not item["passed"]
        ],
        "checks": checks,
        "required_failures": required_failures,
        "optional_target_misses": optional_failures,
        "savings": savings,
    }


def render_release_gate(result: dict[str, Any]) -> str:
    lines = [
        "CASCADE RELEASE GATE",
        "",
    ]
    for item in result.get("checks", []):
        if not isinstance(item, dict):
            continue
        mark = "PASS" if item.get("passed") else (
            "WARN" if not item.get("required") else "FAIL"
        )
        lines.append(
            f"[{mark}] {item.get('name')}: {item.get('detail')}"
        )
    lines.extend(
        [
            "",
            (
                "ENGINEERING READY: "
                + ("YES" if result.get("engineering_ready") else "NO")
            ),
            (
                "MEASURED RELEASE EVIDENCE: "
                + (
                    "YES"
                    if result.get("measured_release_evidence")
                    else "NO / NOT SUPPLIED"
                )
            ),
        ]
    )
    return "\n".join(lines)

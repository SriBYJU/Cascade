from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import CascadeConfig
from ..release_gate import release_gate
from ..router.profile_loader import load_profiles
from ..schemas import ReasoningEffort
from .harness import EvaluationHarness
from .models import load_cases
from .parallel_live import (
    ParallelLiveHarness,
    load_parallel_scenarios,
)
from .savings import savings_summary


def run_release_benchmark(
    repo_root: str | Path,
    *,
    profiles_path: str | Path,
    repeats: int = 3,
    output_dir: str | Path = ".cascade/release-benchmark",
    effort: ReasoningEffort = ReasoningEffort.MEDIUM,
) -> dict[str, Any]:
    if repeats < 3:
        raise ValueError(
            "release benchmark requires at least 3 repeats"
        )

    root = Path(repo_root).resolve()
    profile_path = Path(profiles_path)
    if not profile_path.is_absolute():
        profile_path = root / profile_path
    profiles = load_profiles(profile_path)

    out = Path(output_dir)
    if not out.is_absolute():
        out = root / out
    live_dir = out / "live"
    parallel_path = out / "parallel-live.json"
    out.mkdir(parents=True, exist_ok=True)

    configs = [
        "strongest",
        "efficient",
        "plain",
        "cascade",
        "cascade-no-context",
        "cascade-no-cache",
    ]
    if any(
        profile.local and profile.available
        for profile in profiles.values()
    ):
        configs.append("local")

    cases = load_cases(
        root / "benchmarks" / "fixtures" / "live_tasks.json"
    )
    live_harness = EvaluationHarness(root, profiles=profiles)
    live_report = live_harness.run(
        cases,
        configs=configs,
        repeats=repeats,
        output_dir=live_dir,
        effort=effort,
    )

    if live_report.get("measured") is not True:
        bundle = {
            "measured": False,
            "status": live_report.get(
                "status",
                "environment-unavailable",
            ),
            "reason": live_report.get("reason"),
            "live_report": str(live_dir / "report.json"),
        }
        (out / "bundle.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n"
        )
        return bundle

    scenarios = load_parallel_scenarios(
        root / "benchmarks" / "fixtures" / "parallel_live.json"
    )
    config = CascadeConfig.load(root)
    parallel_report = ParallelLiveHarness(root).run(
        scenarios,
        repeats=repeats,
        model="auto",
        max_workers=config.max_concurrent_workers,
    )
    parallel_path.write_text(
        json.dumps(
            parallel_report,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )

    savings = savings_summary(live_report)
    gate = release_gate(
        root,
        benchmark_report=live_dir / "report.json",
    )
    bundle = {
        "measured": True,
        "status": "completed",
        "profiles": str(profile_path),
        "repeats": repeats,
        "configs": configs,
        "live_report": str(live_dir / "report.json"),
        "live_markdown": str(live_dir / "report.md"),
        "savings_text": str(live_dir / "savings.txt"),
        "savings_json": str(live_dir / "savings.json"),
        "parallel_report": str(parallel_path),
        "savings": savings,
        "release_gate": gate,
    }
    (out / "bundle.json").write_text(
        json.dumps(
            bundle,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )
    return bundle

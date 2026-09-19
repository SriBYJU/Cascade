from __future__ import annotations

import json
import platform
import tempfile
import time
from pathlib import Path
from typing import Any

from ..adapters.base import ModelAdapter
from ..adapters.codex import CodexAdapter
from ..router.capability_registry import CapabilityRegistry
from ..router.router import Router
from ..runtime import CascadeRuntime
from ..schemas import Capability, ReasoningEffort
from ..tools.runner import run_command
from .models import BenchmarkCase, TrialResult, aggregate_trials


class EvaluationHarness:
    """Reproducible plain-Codex vs Cascade runner with raw local trajectories."""

    SUPPORTED_CONFIGS = {"plain", "cascade"}

    def __init__(
        self,
        repo_root: str | Path,
        adapter: ModelAdapter | None = None,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.adapter: ModelAdapter = adapter or CodexAdapter()

    def available(self) -> bool:
        return self.adapter.available()

    def _source_commit(self) -> str | None:
        result = run_command(
            ["git", "rev-parse", "HEAD"],
            self.repo_root,
            timeout_seconds=10,
            output_cap_chars=2000,
        )
        return result.stdout.strip() if result.exit_code == 0 else None

    @staticmethod
    def _init_fixture(case: BenchmarkCase, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for rel, content in case.files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        commands = [
            ["git", "init"],
            ["git", "config", "user.email", "cascade-benchmark@local"],
            ["git", "config", "user.name", "Cascade Benchmark"],
            ["git", "add", "-A"],
            ["git", "commit", "-m", "benchmark fixture"],
        ]
        for command in commands:
            result = run_command(command, root, timeout_seconds=30)
            if result.exit_code != 0:
                raise RuntimeError(
                    f"fixture git setup failed: {result.stderr or result.stdout}"
                )

    @staticmethod
    def _accept(
        root: Path,
        commands: list[list[str]],
    ) -> tuple[bool, list[dict[str, Any]]]:
        checks: list[dict[str, Any]] = []
        passed = True
        for command in commands:
            result = run_command(
                command,
                root,
                timeout_seconds=180,
                output_cap_chars=12000,
            )
            ok = result.exit_code == 0 and not result.timed_out
            passed = passed and ok
            checks.append(
                {
                    **result.model_dump(mode="json"),
                    "passed": ok,
                }
            )
        return passed, checks

    @staticmethod
    def _write_trace(
        output_dir: Path,
        trial_name: str,
        payload: dict[str, Any],
    ) -> str:
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{trial_name}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return str(path)

    def _plain_trial(
        self,
        case: BenchmarkCase,
        *,
        repeat: int,
        output_dir: Path,
        model: str,
        effort: ReasoningEffort,
    ) -> TrialResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="cascade-bench-plain-") as tmp:
            root = Path(tmp) / "repo"
            try:
                self._init_fixture(case, root)
                result = self.adapter.run(
                    case.task,
                    cwd=str(root),
                    model=model,
                    effort=effort,
                )
                accepted, checks = self._accept(root, case.acceptance)
                verified = result.ok and accepted
                failure_kind: str | None = None
                if not result.ok:
                    failure_kind = "agent"
                elif not accepted:
                    failure_kind = "task"
                wall = int((time.monotonic() - started) * 1000)
                usage = result.usage
                trace = self._write_trace(
                    output_dir,
                    f"{case.case_id}-plain-r{repeat}",
                    {
                        "configuration": "plain",
                        "case": case.case_id,
                        "repeat": repeat,
                        "source_commit": self._source_commit(),
                        "adapter_events": result.events,
                        "usage": usage,
                        "acceptance": checks,
                        "final_message": result.final_message,
                        "error": result.error,
                    },
                )
                head_in = int(usage.get("input_tokens", 0))
                head_out = int(usage.get("output_tokens", 0))
                cached = int(usage.get("cached_input_tokens", 0))
                return TrialResult(
                    case_id=case.case_id,
                    category=case.category,
                    config="plain",
                    repeat=repeat,
                    verified_success=verified,
                    failure_kind=failure_kind,
                    wall_time_ms=wall,
                    head_input_tokens=head_in,
                    head_output_tokens=head_out,
                    cached_input_tokens=cached,
                    total_model_tokens=head_in + head_out,
                    raw_trace=trace,
                    error=result.error,
                    acceptance=checks,
                )
            except Exception as exc:
                wall = int((time.monotonic() - started) * 1000)
                trace = self._write_trace(
                    output_dir,
                    f"{case.case_id}-plain-r{repeat}",
                    {
                        "configuration": "plain",
                        "case": case.case_id,
                        "repeat": repeat,
                        "source_commit": self._source_commit(),
                        "failure_kind": "harness",
                        "error": str(exc),
                    },
                )
                return TrialResult(
                    case_id=case.case_id,
                    category=case.category,
                    config="plain",
                    repeat=repeat,
                    verified_success=False,
                    failure_kind="harness",
                    wall_time_ms=wall,
                    raw_trace=trace,
                    error=str(exc),
                )

    def _cascade_trial(
        self,
        case: BenchmarkCase,
        *,
        repeat: int,
        output_dir: Path,
        model: str,
    ) -> TrialResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="cascade-bench-cascade-") as tmp:
            root = Path(tmp) / "repo"
            try:
                self._init_fixture(case, root)
                runtime = CascadeRuntime(root)
                runtime.codex = self.adapter
                runtime.config.local_mode = False
                runtime.config.cloud_fallback = True
                if model != "auto":
                    overrides = {
                        capability: model
                        for capability in Capability
                        if capability != Capability.NO_MODEL
                    }
                    runtime.registry = CapabilityRegistry(overrides)
                    runtime.router = Router(runtime.registry, runtime.budgets)
                result = runtime.run(
                    case.task,
                    write_paths=case.write_paths or None,
                    allowed_paths=case.write_paths or None,
                    apply=False,
                )
                target = Path(str(result.get("worktree", root)))
                accepted, checks = self._accept(target, case.acceptance)
                verified = result.get("status") == "verified" and accepted
                failure_kind: str | None = None
                if result.get("status") not in {
                    "verified",
                    "completed-read-only",
                }:
                    failure_kind = "agent"
                elif not accepted:
                    failure_kind = "task"
                stats = runtime.stats()
                wall = int((time.monotonic() - started) * 1000)
                run_id = str(result.get("run_id", "unknown"))
                trace = self._write_trace(
                    output_dir,
                    f"{case.case_id}-cascade-r{repeat}",
                    {
                        "configuration": "cascade",
                        "case": case.case_id,
                        "repeat": repeat,
                        "source_commit": self._source_commit(),
                        "result": result,
                        "stats": stats,
                        "events": runtime.trace(run_id),
                        "acceptance": checks,
                    },
                )
                return TrialResult(
                    case_id=case.case_id,
                    category=case.category,
                    config="cascade",
                    repeat=repeat,
                    verified_success=verified,
                    failure_kind=failure_kind,
                    wall_time_ms=wall,
                    head_input_tokens=int(stats.get("head_input_tokens", 0)),
                    head_output_tokens=int(stats.get("head_output_tokens", 0)),
                    worker_input_tokens=int(stats.get("worker_input_tokens", 0)),
                    worker_output_tokens=int(stats.get("worker_output_tokens", 0)),
                    cached_input_tokens=int(stats.get("cached_input_tokens", 0)),
                    total_model_tokens=int(stats.get("total_model_tokens", 0)),
                    retries=int(stats.get("retries", 0)),
                    escalations=int(stats.get("escalations", 0)),
                    raw_trace=trace,
                    acceptance=checks,
                )
            except Exception as exc:
                wall = int((time.monotonic() - started) * 1000)
                trace = self._write_trace(
                    output_dir,
                    f"{case.case_id}-cascade-r{repeat}",
                    {
                        "configuration": "cascade",
                        "case": case.case_id,
                        "repeat": repeat,
                        "source_commit": self._source_commit(),
                        "failure_kind": "harness",
                        "error": str(exc),
                    },
                )
                return TrialResult(
                    case_id=case.case_id,
                    category=case.category,
                    config="cascade",
                    repeat=repeat,
                    verified_success=False,
                    failure_kind="harness",
                    wall_time_ms=wall,
                    raw_trace=trace,
                    error=str(exc),
                )

    def run(
        self,
        cases: list[BenchmarkCase],
        *,
        configs: list[str],
        repeats: int,
        output_dir: str | Path,
        model: str = "auto",
        effort: ReasoningEffort = ReasoningEffort.MEDIUM,
    ) -> dict[str, Any]:
        if repeats < 1:
            raise ValueError("repeats must be >= 1")
        unsupported = sorted(set(configs) - self.SUPPORTED_CONFIGS)
        if unsupported:
            raise ValueError(
                f"unsupported live benchmark configurations: {unsupported}"
            )
        if not self.available():
            return {
                "measured": False,
                "status": "environment-unavailable",
                "reason": f"{self.adapter.name} adapter is unavailable",
                "trials": [],
                "summary": {},
            }

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        trials: list[TrialResult] = []
        for config in configs:
            for case in cases:
                for repeat in range(1, repeats + 1):
                    if config == "plain":
                        trial = self._plain_trial(
                            case,
                            repeat=repeat,
                            output_dir=out,
                            model=model,
                            effort=effort,
                        )
                    else:
                        trial = self._cascade_trial(
                            case,
                            repeat=repeat,
                            output_dir=out,
                            model=model,
                        )
                    trials.append(trial)

        report = {
            "measured": True,
            "status": "completed",
            "source_commit": self._source_commit(),
            "python": platform.python_version(),
            "adapter": self.adapter.name,
            "model": model,
            "reasoning_effort": effort.value,
            "repeats": repeats,
            "configs": configs,
            "case_ids": [case.case_id for case in cases],
            "trials": [trial.to_dict() for trial in trials],
            "summary": aggregate_trials(trials),
        }
        (out / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str)
        )
        return report

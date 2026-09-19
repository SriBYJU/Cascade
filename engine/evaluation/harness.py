from __future__ import annotations

import json
import platform
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..adapters.base import ModelAdapter
from ..adapters.codex import CodexAdapter
from ..observability.redaction import metadata_only_payload
from ..policy_lock import load_policy, policy_digest
from ..router.capability_registry import CapabilityRegistry
from ..router.router import Router
from ..runtime import CascadeRuntime
from ..schemas import Capability, ModelProfile, ReasoningEffort
from ..tools.runner import run_command
from ..workspace.worktree import Worktree
from .model_pool import EvaluationModelPool
from .models import BenchmarkCase, TrialResult, aggregate_trials
from .report import compare_summaries, render_markdown_report
from .savings import render_savings, savings_summary


class EvaluationHarness:
    """Reproducible plain-Codex vs Cascade runner with raw local trajectories."""

    SUPPORTED_CONFIGS = {
        "plain",
        "strongest",
        "efficient",
        "local",
        "cascade",
        "cascade-no-context",
        "cascade-no-cache",
    }

    def __init__(
        self,
        repo_root: str | Path,
        adapter: ModelAdapter | None = None,
        profiles: dict[Capability, ModelProfile] | None = None,
        full_trace: bool = False,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.adapter: ModelAdapter = adapter or CodexAdapter()
        self.full_trace = full_trace
        self.model_pool = (
            EvaluationModelPool(profiles)
            if profiles
            else None
        )

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
    def _version(command: list[str]) -> str | None:
        executable = shutil.which(command[0])
        if not executable:
            return None
        if (
            platform.system() == "Windows"
            and executable.lower().endswith((".cmd", ".bat"))
        ):
            return None
        resolved = [executable, *command[1:]]
        result = run_command(
            resolved,
            ".",
            timeout_seconds=10,
            output_cap_chars=2000,
        )
        if result.exit_code != 0:
            return None
        output = (result.stdout or result.stderr).strip()
        return output.splitlines()[0] if output else None

    def _environment(self) -> dict[str, Any]:
        adapter_version = None
        version_method = getattr(self.adapter, "version", None)
        if callable(version_method):
            try:
                adapter_version = version_method()
            except Exception:
                adapter_version = None
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "git": self._version(["git", "--version"]),
            "node": self._version(["node", "--version"]),
            "npm": self._version(["npm", "--version"]),
            "go": self._version(["go", "version"]),
            "rustc": self._version(["rustc", "--version"]),
            "cargo": self._version(["cargo", "--version"]),
            "adapter": self.adapter.name,
            "adapter_version": adapter_version,
        }

    def _policy_snapshot(self) -> dict[str, Any] | None:
        path = self.repo_root / "policy.lock.yaml"
        if not path.exists():
            return None
        try:
            policy = load_policy(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        return {
            "version": policy.version,
            "status": policy.status,
            "digest": policy_digest(policy),
            "base_evidence_snapshot": policy.base_evidence_snapshot,
        }

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
        *,
        final_message: str = "",
        answer_contains: list[str] | None = None,
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
        lowered = final_message.lower()
        for expected in answer_contains or []:
            ok = expected.lower() in lowered
            passed = passed and ok
            checks.append(
                {
                    "kind": "answer_contains",
                    "expected": expected,
                    "passed": ok,
                }
            )
        return passed, checks

    def _write_trace(
        self,
        output_dir: Path,
        trial_name: str,
        payload: dict[str, Any],
    ) -> str:
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{trial_name}.json"
        stored = (
            payload
            if self.full_trace
            else metadata_only_payload(payload)
        )
        path.write_text(
            json.dumps(
                stored,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )
        return str(path)

    def _plain_trial(
        self,
        case: BenchmarkCase,
        *,
        repeat: int,
        output_dir: Path,
        model: str,
        effort: ReasoningEffort,
        config: str = "plain",
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
                    sandbox_mode=(
                        "workspace-write"
                        if case.write_paths
                        else "read-only"
                    ),
                )
                accepted, checks = self._accept(
                    root,
                    case.acceptance,
                    final_message=result.final_message,
                    answer_contains=case.answer_contains,
                )
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
                    f"{case.case_id}-{config}-r{repeat}",
                    {
                        "configuration": config,
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
                tool_item_types = {
                    "command_execution",
                    "mcp_tool_call",
                    "web_search",
                }
                tool_calls = sum(
                    1
                    for event in result.events
                    if event.get("type") == "item.completed"
                    and isinstance(event.get("item"), dict)
                    and event["item"].get("type") in tool_item_types
                )
                stored_checks = (
                    checks
                    if self.full_trace
                    else metadata_only_payload(
                        {"checks": checks}
                    )["checks"]
                )
                assert isinstance(stored_checks, list)
                return TrialResult(
                    case_id=case.case_id,
                    category=case.category,
                    config=config,
                    repeat=repeat,
                    verified_success=verified,
                    failure_kind=failure_kind,
                    wall_time_ms=wall,
                    head_input_tokens=head_in,
                    head_output_tokens=head_out,
                    cached_input_tokens=cached,
                    total_model_tokens=head_in + head_out,
                    weighted_usage=float(head_in + head_out),
                    context_bytes=len(case.task.encode("utf-8")),
                    tool_calls=tool_calls,
                    agent_calls=1,
                    trajectory_steps=max(1, len(result.events)),
                    raw_trace=trace,
                    error=(
                        result.error
                        if self.full_trace
                        else None
                    ),
                    acceptance=stored_checks,
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

    @staticmethod
    def _cleanup_result_worktree(
        runtime: CascadeRuntime,
        result: dict[str, Any],
        fixture_root: Path,
    ) -> None:
        raw_path = result.get("worktree")
        branch = result.get("branch")
        if not raw_path or not branch:
            return
        path = Path(str(raw_path))
        if path.resolve() == fixture_root.resolve() or not path.exists():
            return
        worktree = Worktree(
            task_id=str(result.get("task_id", "benchmark")),
            path=path,
            branch=str(branch),
            base_ref="HEAD",
        )
        runtime.worktrees.cleanup(
            worktree,
            force=True,
        )

    def _cascade_trial(
        self,
        case: BenchmarkCase,
        *,
        repeat: int,
        output_dir: Path,
        model: str,
        config: str = "cascade",
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
                if self.model_pool is not None:
                    runtime.registry = CapabilityRegistry(
                        profiles=self.model_pool.profiles
                    )
                    runtime.router = Router(
                        runtime.registry,
                        runtime.budgets,
                    )
                if config == "cascade-no-context":
                    runtime.config.enable_context_firewall = False
                if config == "cascade-no-cache":
                    runtime.config.enable_prompt_cache_affinity = False
                if model != "auto":
                    overrides: dict[Capability, str] = {
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
                final_message = str(result.get("worker_message", ""))
                accepted, checks = self._accept(
                    target,
                    case.acceptance,
                    final_message=final_message,
                    answer_contains=case.answer_contains,
                )
                verified = (
                    result.get("status")
                    in {"verified", "completed-read-only"}
                    and accepted
                )
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
                    f"{case.case_id}-{config}-r{repeat}",
                    {
                        "configuration": config,
                        "case": case.case_id,
                        "repeat": repeat,
                        "source_commit": self._source_commit(),
                        "result": result,
                        "stats": stats,
                        "events": runtime.trace(run_id),
                        "acceptance": checks,
                    },
                )
                stored_checks = (
                    checks
                    if self.full_trace
                    else metadata_only_payload(
                        {"checks": checks}
                    )["checks"]
                )
                assert isinstance(stored_checks, list)
                trial = TrialResult(
                    case_id=case.case_id,
                    category=case.category,
                    config=config,
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
                    weighted_usage=float(stats.get("weighted_usage", 0.0)),
                    context_bytes=int(stats.get("context_bytes", 0)),
                    tool_calls=int(stats.get("tool_calls", 0)),
                    agent_calls=int(stats.get("agent_calls", 0)),
                    trajectory_steps=int(
                        stats.get("trajectory_steps", 0)
                    ),
                    retries=int(stats.get("retries", 0)),
                    escalations=int(stats.get("escalations", 0)),
                    raw_trace=trace,
                    acceptance=stored_checks,
                )
                self._cleanup_result_worktree(runtime, result, root)
                return trial
            except Exception as exc:
                wall = int((time.monotonic() - started) * 1000)
                trace = self._write_trace(
                    output_dir,
                    f"{case.case_id}-{config}-r{repeat}",
                    {
                        "configuration": config,
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
                    config=config,
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
        max_workers: int = 1,
    ) -> dict[str, Any]:
        if repeats < 1:
            raise ValueError("repeats must be >= 1")
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
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
        jobs: list[tuple[str, BenchmarkCase, int, str]] = []
        direct_configs = {"plain", "strongest", "efficient", "local"}
        for config in configs:
            direct_model = model
            if config in {"strongest", "efficient", "local"}:
                if self.model_pool is None:
                    raise ValueError(
                        f"{config} benchmark requires --profiles"
                    )
                if config == "strongest":
                    direct_model = self.model_pool.strongest().model_id
                elif config == "efficient":
                    direct_model = self.model_pool.efficient().model_id
                else:
                    direct_model = self.model_pool.local().model_id
            for case in cases:
                for repeat in range(1, repeats + 1):
                    jobs.append((config, case, repeat, direct_model))

        def execute(
            job: tuple[str, BenchmarkCase, int, str],
        ) -> TrialResult:
            config, case, repeat, direct_model = job
            if config in direct_configs:
                return self._plain_trial(
                    case,
                    repeat=repeat,
                    output_dir=out,
                    model=direct_model,
                    effort=effort,
                    config=config,
                )
            return self._cascade_trial(
                case,
                repeat=repeat,
                output_dir=out,
                model=model,
                config=config,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            trials = list(executor.map(execute, jobs))

        summary = aggregate_trials(trials)
        report = {
            "measured": True,
            "status": "completed",
            "source_commit": self._source_commit(),
            "environment": self._environment(),
            "policy_lock": self._policy_snapshot(),
            "adapter": self.adapter.name,
            "model": model,
            "reasoning_effort": effort.value,
            "repeats": repeats,
            "trial_workers": max_workers,
            "configs": configs,
            "model_pool": (
                self.model_pool.snapshot()
                if self.model_pool is not None
                else None
            ),
            "case_ids": [case.case_id for case in cases],
            "trials": [trial.to_dict() for trial in trials],
            "summary": summary,
            "comparisons": compare_summaries(summary),
            "failed_trials": sum(
                1 for trial in trials if not trial.verified_success
            ),
        }
        (out / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str)
        )
        (out / "report.md").write_text(render_markdown_report(report))
        if "plain" in summary and "cascade" in summary:
            savings = savings_summary(report)
            (out / "savings.json").write_text(
                json.dumps(
                    savings,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
            (out / "savings.txt").write_text(
                render_savings(savings) + "\n"
            )
        return report

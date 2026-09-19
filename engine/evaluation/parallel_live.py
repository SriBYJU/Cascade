from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..adapters.base import ModelAdapter
from ..adapters.codex import CodexAdapter
from ..observability.redaction import metadata_only_payload
from ..router.capability_registry import CapabilityRegistry
from ..router.router import Router
from ..runtime import CascadeRuntime
from ..schemas import Capability, ModelProfile
from ..scheduler.dag import TaskNode
from ..scheduler.executor import (
    ParallelTaskSpec,
    compile_safe_dag,
    execute_dag,
)
from ..tools.runner import run_command
from ..workspace.worktree import Worktree


@dataclass(frozen=True, slots=True)
class ParallelLiveTask:
    task_id: str
    task: str
    write_paths: tuple[str, ...]
    acceptance: tuple[tuple[str, ...], ...]
    answer_contains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParallelLiveScenario:
    scenario_id: str
    files: dict[str, str]
    tasks: tuple[ParallelLiveTask, ...]


def load_parallel_scenarios(
    path: str | Path,
) -> list[ParallelLiveScenario]:
    raw: object = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError("parallel-live manifest must be a list")
    scenarios: list[ParallelLiveScenario] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("parallel-live scenario must be an object")
        files_raw = item.get("files")
        tasks_raw = item.get("tasks")
        if not isinstance(files_raw, dict) or not isinstance(tasks_raw, list):
            raise ValueError("scenario requires files object and tasks list")
        tasks: list[ParallelLiveTask] = []
        for task in tasks_raw:
            if not isinstance(task, dict):
                raise ValueError("parallel-live task must be an object")
            acceptance_raw = task.get("acceptance", [])
            if not isinstance(acceptance_raw, list):
                raise ValueError("acceptance must be a list")
            commands: list[tuple[str, ...]] = []
            for command in acceptance_raw:
                if not isinstance(command, list) or not command:
                    raise ValueError(
                        "acceptance command must be a non-empty argv list"
                    )
                commands.append(tuple(str(part) for part in command))
            answer_raw = task.get("answer_contains", [])
            if not isinstance(answer_raw, list):
                raise ValueError("answer_contains must be a list")
            tasks.append(
                ParallelLiveTask(
                    task_id=str(task["id"]),
                    task=str(task["task"]),
                    write_paths=tuple(
                        str(value)
                        for value in task.get("write", [])
                    ),
                    acceptance=tuple(commands),
                    answer_contains=tuple(
                        str(value) for value in answer_raw
                    ),
                )
            )
        scenarios.append(
            ParallelLiveScenario(
                scenario_id=str(item["id"]),
                files={
                    str(key): str(value)
                    for key, value in files_raw.items()
                },
                tasks=tuple(tasks),
            )
        )
    return scenarios


class ParallelLiveHarness:
    MODES = {"sequential", "parallel"}

    def __init__(
        self,
        repo_root: str | Path,
        adapter: ModelAdapter | None = None,
        full_trace: bool = False,
        profiles: dict[Capability, ModelProfile] | None = None,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.adapter: ModelAdapter = adapter or CodexAdapter()
        self.full_trace = full_trace
        self.profiles = profiles or {}

    @staticmethod
    def _init_repo(
        scenario: ParallelLiveScenario,
        root: Path,
    ) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for rel, content in scenario.files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        for command in (
            ["git", "init"],
            ["git", "config", "user.email", "parallel@cascade.local"],
            ["git", "config", "user.name", "Cascade Parallel Benchmark"],
            ["git", "add", "-A"],
            ["git", "commit", "-m", "parallel benchmark fixture"],
        ):
            result = run_command(command, root, timeout_seconds=30)
            if result.exit_code != 0:
                raise RuntimeError(
                    result.stderr or result.stdout or "git setup failed"
                )

    @staticmethod
    def _accept(
        task: ParallelLiveTask,
        result: dict[str, Any],
        root: Path,
    ) -> tuple[bool, list[dict[str, Any]]]:
        target = Path(str(result.get("worktree", root)))
        checks: list[dict[str, Any]] = []
        passed = result.get("status") in {
            "verified",
            "completed-read-only",
        }
        for command in task.acceptance:
            command_result = run_command(
                list(command),
                target,
                timeout_seconds=180,
                output_cap_chars=12000,
            )
            ok = (
                command_result.exit_code == 0
                and not command_result.timed_out
            )
            passed = passed and ok
            checks.append(
                {
                    **command_result.model_dump(mode="json"),
                    "passed": ok,
                }
            )
        message = str(result.get("worker_message", "")).lower()
        for expected in task.answer_contains:
            ok = expected.lower() in message
            passed = passed and ok
            checks.append(
                {
                    "kind": "answer_contains",
                    "expected": expected,
                    "passed": ok,
                }
            )
        return passed, checks

    @staticmethod
    def _serial(
        dag: Any,
        fn: Any,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for level in dag.levels():
            for node in level:
                results[node.task_id] = fn(node)
        return results

    def run_scenario(
        self,
        scenario: ParallelLiveScenario,
        *,
        mode: str,
        model: str = "auto",
        max_workers: int = 3,
    ) -> dict[str, Any]:
        if mode not in self.MODES:
            raise ValueError(f"unsupported parallel-live mode: {mode}")
        if not self.adapter.available():
            return {
                "measured": False,
                "status": "environment-unavailable",
                "scenario": scenario.scenario_id,
                "mode": mode,
                "reason": f"{self.adapter.name} adapter is unavailable",
            }

        with tempfile.TemporaryDirectory(
            prefix=f"cascade-parallel-{mode}-"
        ) as tmp:
            root = Path(tmp) / "repo"
            self._init_repo(scenario, root)
            runtime = CascadeRuntime(root)
            runtime.codex = self.adapter
            if self.profiles:
                runtime.registry = CapabilityRegistry(
                    profiles=self.profiles
                )
                runtime.router = Router(
                    runtime.registry,
                    runtime.budgets,
                )
            if model != "auto":
                overrides: dict[Capability, str] = {
                    capability: model
                    for capability in Capability
                    if capability != Capability.NO_MODEL
                }
                runtime.registry = CapabilityRegistry(overrides)
                runtime.router = Router(
                    runtime.registry,
                    runtime.budgets,
                )

            by_id = {task.task_id: task for task in scenario.tasks}
            specs = [
                ParallelTaskSpec(
                    task_id=task.task_id,
                    task=task.task,
                    write_patterns=task.write_paths,
                )
                for task in scenario.tasks
            ]
            dag = compile_safe_dag(specs)

            def run_node(node: TaskNode) -> dict[str, Any]:
                task = by_id[node.task_id]
                return runtime.run(
                    task.task,
                    write_paths=list(task.write_paths) or None,
                    allowed_paths=list(task.write_paths) or None,
                    apply=False,
                )

            started = time.perf_counter()
            if mode == "parallel":
                results = execute_dag(
                    dag,
                    run_node,
                    max_workers=max_workers,
                )
            else:
                results = self._serial(dag, run_node)
            wall_ms = (time.perf_counter() - started) * 1000.0

            acceptance: dict[str, Any] = {}
            verified = True
            for task_id, result in results.items():
                ok, checks = self._accept(
                    by_id[task_id],
                    result,
                    root,
                )
                verified = verified and ok
                acceptance[task_id] = {
                    "passed": ok,
                    "checks": checks,
                    "status": result.get("status"),
                }

            levels = [
                [node.task_id for node in level]
                for level in dag.levels()
            ]
            dependency_edges = sum(
                len(node.depends_on)
                for node in dag.nodes.values()
            )
            stored_acceptance = (
                acceptance
                if self.full_trace
                else metadata_only_payload(
                    {"acceptance": acceptance}
                )["acceptance"]
            )
            stored_results = (
                results
                if self.full_trace
                else {
                    task_id: metadata_only_payload(result)
                    for task_id, result in results.items()
                }
            )
            response = {
                "measured": True,
                "status": "completed",
                "scenario": scenario.scenario_id,
                "mode": mode,
                "verified_success": verified,
                "wall_time_ms": wall_ms,
                "stats": runtime.stats(),
                "acceptance": stored_acceptance,
                "levels": levels,
                "dependency_edges": dependency_edges,
                "results": stored_results,
                "trace": runtime.trace(),
            }
            for task_id, result in results.items():
                raw_path = result.get("worktree")
                branch = result.get("branch")
                if not raw_path or not branch:
                    continue
                path = Path(str(raw_path))
                if path.resolve() == root.resolve() or not path.exists():
                    continue
                runtime.worktrees.cleanup(
                    Worktree(
                        task_id=task_id,
                        path=path,
                        branch=str(branch),
                        base_ref="HEAD",
                    ),
                    force=True,
                )
            return response

    def run(
        self,
        scenarios: list[ParallelLiveScenario],
        *,
        repeats: int,
        model: str = "auto",
        max_workers: int = 3,
    ) -> dict[str, Any]:
        if repeats < 1:
            raise ValueError("repeats must be >= 1")
        runs: list[dict[str, Any]] = []
        for scenario in scenarios:
            for repeat in range(1, repeats + 1):
                for mode in ("sequential", "parallel"):
                    result = self.run_scenario(
                        scenario,
                        mode=mode,
                        model=model,
                        max_workers=max_workers,
                    )
                    result["repeat"] = repeat
                    runs.append(result)
                    if result.get("measured") is False:
                        return {
                            "measured": False,
                            "status": "environment-unavailable",
                            "runs": runs,
                        }

        summary: dict[str, Any] = {}
        for scenario in scenarios:
            scenario_runs = [
                run
                for run in runs
                if run.get("scenario") == scenario.scenario_id
            ]
            seq = [
                float(run["wall_time_ms"])
                for run in scenario_runs
                if run.get("mode") == "sequential"
            ]
            par = [
                float(run["wall_time_ms"])
                for run in scenario_runs
                if run.get("mode") == "parallel"
            ]
            seq_mean = sum(seq) / len(seq) if seq else 0.0
            par_mean = sum(par) / len(par) if par else 0.0
            def mode_metric(
                mode: str,
                key: str,
                runs_for_scenario: list[dict[str, Any]] = scenario_runs,
            ) -> float:
                values: list[float] = []
                for run in runs_for_scenario:
                    if run.get("mode") != mode:
                        continue
                    stats = run.get("stats")
                    if not isinstance(stats, dict):
                        continue
                    value = stats.get(key)
                    if isinstance(value, (int, float)):
                        values.append(float(value))
                return sum(values) / len(values) if values else 0.0

            merge_conflicts = 0
            for run in scenario_runs:
                results = run.get("results")
                if not isinstance(results, dict):
                    continue
                for result in results.values():
                    if not isinstance(result, dict):
                        continue
                    reason = str(result.get("reason", "")).lower()
                    if "merge conflict" in reason:
                        merge_conflicts += 1

            summary[scenario.scenario_id] = {
                "sequential_wall_ms_mean": seq_mean,
                "parallel_wall_ms_mean": par_mean,
                "speedup": (
                    seq_mean / par_mean
                    if par_mean > 0
                    else 0.0
                ),
                "sequential_model_tokens_mean": mode_metric(
                    "sequential",
                    "total_model_tokens",
                ),
                "parallel_model_tokens_mean": mode_metric(
                    "parallel",
                    "total_model_tokens",
                ),
                "sequential_weighted_usage_mean": mode_metric(
                    "sequential",
                    "weighted_usage",
                ),
                "parallel_weighted_usage_mean": mode_metric(
                    "parallel",
                    "weighted_usage",
                ),
                "sequential_context_bytes_mean": mode_metric(
                    "sequential",
                    "context_bytes",
                ),
                "parallel_context_bytes_mean": mode_metric(
                    "parallel",
                    "context_bytes",
                ),
                "sequential_retries_mean": mode_metric(
                    "sequential",
                    "retries",
                ),
                "parallel_retries_mean": mode_metric(
                    "parallel",
                    "retries",
                ),
                "dependency_edges": max(
                    (
                        int(run.get("dependency_edges", 0))
                        for run in scenario_runs
                    ),
                    default=0,
                ),
                "merge_conflicts_observed": merge_conflicts,
                "all_verified": all(
                    bool(run.get("verified_success"))
                    for run in scenario_runs
                ),
            }

        return {
            "measured": True,
            "status": "completed",
            "scope": (
                "live end-to-end Cascade sequential-vs-parallel comparison "
                "on identical generated fixtures"
            ),
            "repeats": repeats,
            "model": model,
            "model_profiles": (
                [
                    profile.model_dump(mode="json")
                    for profile in sorted(
                        self.profiles.values(),
                        key=lambda item: CapabilityRegistry.order(
                            item.capability
                        ),
                    )
                ]
                if self.profiles
                else None
            ),
            "runs": runs,
            "summary": summary,
        }

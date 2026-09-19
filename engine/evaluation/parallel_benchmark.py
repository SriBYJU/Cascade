from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Any

from ..scheduler.dag import TaskDAG, TaskNode
from ..scheduler.executor import (
    ParallelTaskSpec,
    compile_safe_dag,
    execute_dag,
)


@dataclass(frozen=True, slots=True)
class SchedulerBenchmarkResult:
    sequential_ms: float
    parallel_ms: float
    speedup: float
    levels: list[list[str]]
    conflict_levels: list[list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequential_ms": self.sequential_ms,
            "parallel_ms": self.parallel_ms,
            "speedup": self.speedup,
            "levels": self.levels,
            "conflict_levels": self.conflict_levels,
        }


def independent_fixture() -> TaskDAG:
    return compile_safe_dag(
        [
            ParallelTaskSpec(
                "auth",
                "independent auth work",
                write_patterns=("src/auth/**",),
            ),
            ParallelTaskSpec(
                "payments",
                "independent payment work",
                write_patterns=("src/payments/**",),
            ),
            ParallelTaskSpec(
                "docs",
                "independent read-only documentation lookup",
            ),
        ]
    )


def conflict_fixture() -> TaskDAG:
    return compile_safe_dag(
        [
            ParallelTaskSpec(
                "auth-a",
                "first auth writer",
                write_patterns=("src/auth/**",),
            ),
            ParallelTaskSpec(
                "auth-b",
                "second auth writer",
                write_patterns=("src/auth/session.py",),
            ),
            ParallelTaskSpec(
                "payments",
                "independent payment writer",
                write_patterns=("src/payments/**",),
            ),
        ]
    )


def _serial_execute(
    dag: TaskDAG,
    fn: Any,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for level in dag.levels():
        for node in level:
            results[node.task_id] = fn(node)
    return results


def _measure(
    dag: TaskDAG,
    *,
    parallel: bool,
    sleep_seconds: float,
    max_workers: int,
) -> float:
    def work(node: TaskNode) -> str:
        time.sleep(sleep_seconds)
        return node.task_id

    started = time.perf_counter()
    if parallel:
        execute_dag(dag, work, max_workers=max_workers)
    else:
        _serial_execute(dag, work)
    return (time.perf_counter() - started) * 1000.0


def run_scheduler_benchmark(
    *,
    repeats: int = 3,
    sleep_seconds: float = 0.05,
    max_workers: int = 3,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds must be >= 0")
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    independent = independent_fixture()
    conflict = conflict_fixture()
    sequential_samples: list[float] = []
    parallel_samples: list[float] = []
    for _ in range(repeats):
        sequential_samples.append(
            _measure(
                independent,
                parallel=False,
                sleep_seconds=sleep_seconds,
                max_workers=max_workers,
            )
        )
        parallel_samples.append(
            _measure(
                independent,
                parallel=True,
                sleep_seconds=sleep_seconds,
                max_workers=max_workers,
            )
        )

    sequential_ms = float(statistics.median(sequential_samples))
    parallel_ms = float(statistics.median(parallel_samples))
    speedup = (
        sequential_ms / parallel_ms
        if parallel_ms > 0
        else 0.0
    )
    result = SchedulerBenchmarkResult(
        sequential_ms=sequential_ms,
        parallel_ms=parallel_ms,
        speedup=speedup,
        levels=[
            [node.task_id for node in level]
            for level in independent.levels()
        ],
        conflict_levels=[
            [node.task_id for node in level]
            for level in conflict.levels()
        ],
    )
    return {
        "suite": "parallel-scheduler-v1",
        "measured": True,
        "scope": (
            "scheduler-only local timing; does not measure model inference "
            "or claim end-to-end coding latency savings"
        ),
        "repeats": repeats,
        "sleep_seconds": sleep_seconds,
        "max_workers": max_workers,
        **result.to_dict(),
    }

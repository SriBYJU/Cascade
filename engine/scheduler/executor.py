from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from .dag import TaskDAG, TaskNode
from .write_sets import WriteSet, conflict_graph


@dataclass(slots=True)
class ParallelTaskSpec:
    task_id: str
    task: str
    depends_on: set[str] = field(default_factory=set)
    write_patterns: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def compile_safe_dag(specs: list[ParallelTaskSpec]) -> TaskDAG:
    """Compile explicit dependencies plus deterministic write-conflict serialization.

    Conflicting writers are ordered by input position. Read-only tasks remain independent unless
    the caller declares a dependency.
    """
    ids = [spec.task_id for spec in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task_id in batch")
    deps = {spec.task_id: set(spec.depends_on) for spec in specs}
    index = {spec.task_id: i for i, spec in enumerate(specs)}
    writers = [WriteSet(spec.task_id, spec.write_patterns) for spec in specs if spec.write_patterns]
    graph = conflict_graph(writers)
    for left, conflicts in graph.items():
        for right in conflicts:
            earlier, later = (left, right) if index[left] < index[right] else (right, left)
            deps[later].add(earlier)
    nodes = [
        TaskNode(
            task_id=spec.task_id,
            depends_on=deps[spec.task_id],
            read_only=not bool(spec.write_patterns),
            write_patterns=spec.write_patterns,
            metadata={"task": spec.task, **spec.metadata},
        )
        for spec in specs
    ]
    return TaskDAG(nodes)


def execute_dag(
    dag: TaskDAG,
    fn: Callable[[TaskNode], Any],
    *,
    max_workers: int = 3,
) -> dict[str, Any]:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    results: dict[str, Any] = {}
    for level in dag.levels():
        if len(level) == 1:
            node = level[0]
            results[node.task_id] = fn(node)
            continue
        with ThreadPoolExecutor(max_workers=min(max_workers, len(level)), thread_name_prefix="cascade-dag") as pool:
            futures = {pool.submit(fn, node): node.task_id for node in level}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
    return results

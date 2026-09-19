from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class TaskNode:
    task_id: str
    depends_on: set[str] = field(default_factory=set)
    read_only: bool = True
    write_patterns: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskDAG:
    def __init__(self, nodes: list[TaskNode]):
        self.nodes = {n.task_id: n for n in nodes}
        missing = {d for n in nodes for d in n.depends_on if d not in self.nodes}
        if missing:
            raise ValueError(f"unknown dependencies: {sorted(missing)}")
        self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        remaining = {k: set(v.depends_on) for k, v in self.nodes.items()}
        while remaining:
            ready = [k for k, deps in remaining.items() if not deps]
            if not ready:
                raise ValueError("cycle detected in task DAG")
            for key in ready:
                remaining.pop(key)
            for deps in remaining.values():
                deps.difference_update(ready)

    def levels(self) -> list[list[TaskNode]]:
        remaining = {k: set(v.depends_on) for k, v in self.nodes.items()}
        result: list[list[TaskNode]] = []
        while remaining:
            ready = sorted(k for k, deps in remaining.items() if not deps)
            result.append([self.nodes[k] for k in ready])
            for key in ready:
                remaining.pop(key)
            for deps in remaining.values():
                deps.difference_update(ready)
        return result

    def run(self, fn: Callable[[TaskNode], Any]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for level in self.levels():
            for node in level:
                results[node.task_id] = fn(node)
        return results

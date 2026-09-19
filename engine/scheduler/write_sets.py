from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class WriteSet:
    task_id: str
    patterns: tuple[str, ...]


def _prefix(pattern: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(pattern).parts:
        if any(ch in part for ch in "*?["):
            break
        parts.append(part)
    return "/".join(parts)


def patterns_overlap(a: str, b: str) -> bool:
    if a == "**" or b == "**":
        return True
    if fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
        return True
    pa, pb = _prefix(a), _prefix(b)
    if pa and pb and (pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/")):
        return True
    return False


def overlap(left: WriteSet, right: WriteSet) -> bool:
    return any(patterns_overlap(a, b) for a in left.patterns for b in right.patterns)


def conflict_graph(write_sets: list[WriteSet]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {w.task_id: set() for w in write_sets}
    for i, left in enumerate(write_sets):
        for right in write_sets[i + 1 :]:
            if overlap(left, right):
                graph[left.task_id].add(right.task_id)
                graph[right.task_id].add(left.task_id)
    return graph

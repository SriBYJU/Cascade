from __future__ import annotations


def trajectory_efficiency(*, useful_steps: int, total_steps: int, retries: int = 0, redundant_reads: int = 0, reverted_edits: int = 0) -> float:
    if total_steps <= 0:
        return 0.0
    penalty = retries + redundant_reads + 2 * reverted_edits
    return max(0.0, useful_steps / max(1, total_steps + penalty))

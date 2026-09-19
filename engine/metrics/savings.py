from __future__ import annotations


def percent_change(baseline: float, optimized: float) -> float | None:
    if baseline == 0:
        return None
    return (optimized - baseline) / baseline * 100.0


def verified_work_per_expensive_token(verified_work: float, weighted_expensive_tokens: float) -> float:
    if weighted_expensive_tokens <= 0:
        return verified_work if verified_work > 0 else 0.0
    return verified_work / weighted_expensive_tokens


def comparison(baseline: dict[str, float], optimized: dict[str, float]) -> dict[str, float | None]:
    keys = set(baseline) | set(optimized)
    return {key: percent_change(float(baseline.get(key, 0)), float(optimized.get(key, 0))) for key in sorted(keys)}

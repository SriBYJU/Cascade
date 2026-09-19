from __future__ import annotations

import statistics


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = max(0, min(len(values) - 1, round((pct / 100.0) * (len(values) - 1))))
    return float(values[idx])


def summarize(values_ms: list[float]) -> dict[str, float]:
    if not values_ms:
        return {"count": 0.0, "mean_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0}
    return {
        "count": float(len(values_ms)),
        "mean_ms": float(statistics.mean(values_ms)),
        "median_ms": float(statistics.median(values_ms)),
        "p95_ms": percentile(values_ms, 95),
    }

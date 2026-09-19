from __future__ import annotations

import hashlib


def stable_prefix_key(*parts: str) -> str:
    normalized = "\n\n".join(part.strip() for part in parts if part.strip())
    return hashlib.sha256(normalized.encode()).hexdigest()


def affinity(current_model: str | None, candidate_model: str, current_prefix_key: str | None, candidate_prefix_key: str | None) -> float:
    if not current_model or not current_prefix_key or not candidate_prefix_key:
        return 0.0
    score = 0.0
    if current_model == candidate_model:
        score += 0.65
    if current_prefix_key == candidate_prefix_key:
        score += 0.35
    return min(1.0, score)


def should_switch(expected_switch_savings: float, existing_cache_value: float, expected_retry_cost: float) -> bool:
    return expected_switch_savings > existing_cache_value + expected_retry_cost

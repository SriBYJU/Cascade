from __future__ import annotations

import json
import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    category: str
    task: str
    files: dict[str, str]
    write_paths: list[str]
    acceptance: list[list[str]]
    answer_contains: list[str] = field(default_factory=list)
    risk: str = "medium"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "BenchmarkCase":
        files_raw = data.get("files", {})
        writes_raw = data.get("write", [])
        acceptance_raw = data.get("acceptance", [])
        answer_raw = data.get("answer_contains", [])
        if not isinstance(files_raw, dict):
            raise ValueError("benchmark case files must be an object")
        if not isinstance(writes_raw, list):
            raise ValueError("benchmark case write must be a list")
        if not isinstance(acceptance_raw, list):
            raise ValueError("benchmark case acceptance must be a list")
        if not isinstance(answer_raw, list):
            raise ValueError("benchmark case answer_contains must be a list")
        files = {
            str(path): str(content)
            for path, content in files_raw.items()
        }
        write_paths = [str(item) for item in writes_raw]
        acceptance: list[list[str]] = []
        for command in acceptance_raw:
            if not isinstance(command, list) or not command:
                raise ValueError("each acceptance command must be a non-empty argv list")
            acceptance.append([str(item) for item in command])
        answer_contains = [str(item) for item in answer_raw]
        if not acceptance and not answer_contains:
            raise ValueError(
                "live benchmark cases require command or answer acceptance"
            )
        return cls(
            case_id=str(data["id"]),
            category=str(data["category"]),
            task=str(data["task"]),
            files=files,
            write_paths=write_paths,
            acceptance=acceptance,
            answer_contains=answer_contains,
            risk=str(data.get("risk", "medium")),
        )


@dataclass(slots=True)
class TrialResult:
    case_id: str
    category: str
    config: str
    repeat: int
    verified_success: bool
    failure_kind: str | None
    wall_time_ms: int
    head_input_tokens: int = 0
    head_output_tokens: int = 0
    worker_input_tokens: int = 0
    worker_output_tokens: int = 0
    cached_input_tokens: int = 0
    total_model_tokens: int = 0
    weighted_usage: float = 0.0
    retries: int = 0
    escalations: int = 0
    raw_trace: str | None = None
    error: str | None = None
    acceptance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_cases(path: str | Path) -> list[BenchmarkCase]:
    data: object = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise ValueError("benchmark manifest must be a JSON list")
    cases: list[BenchmarkCase] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("each benchmark case must be a JSON object")
        cases.append(BenchmarkCase.from_mapping(item))
    return cases


def _stdev(values: list[float]) -> float:
    return float(statistics.stdev(values)) if len(values) > 1 else 0.0


def aggregate_trials(trials: list[TrialResult]) -> dict[str, Any]:
    by_config: dict[str, list[TrialResult]] = defaultdict(list)
    for trial in trials:
        by_config[trial.config].append(trial)

    result: dict[str, Any] = {}
    for config, items in sorted(by_config.items()):
        wall = [float(item.wall_time_ms) for item in items]
        total_tokens = [float(item.total_model_tokens) for item in items]
        cached = [float(item.cached_input_tokens) for item in items]
        weighted = [float(item.weighted_usage) for item in items]
        successes = sum(1 for item in items if item.verified_success)
        result[config] = {
            "trials": len(items),
            "verified_successes": successes,
            "verified_success_rate": successes / len(items) if items else 0.0,
            "wall_time_ms_mean": statistics.mean(wall) if wall else 0.0,
            "wall_time_ms_stdev": _stdev(wall),
            "total_model_tokens_mean": statistics.mean(total_tokens)
            if total_tokens
            else 0.0,
            "total_model_tokens_stdev": _stdev(total_tokens),
            "cached_input_tokens_mean": statistics.mean(cached) if cached else 0.0,
            "weighted_usage_mean": statistics.mean(weighted)
            if weighted
            else 0.0,
            "weighted_usage_stdev": _stdev(weighted),
            "retries_total": sum(item.retries for item in items),
            "escalations_total": sum(item.escalations for item in items),
            "failure_kinds": {
                kind: sum(1 for item in items if item.failure_kind == kind)
                for kind in ("agent", "task", "environment", "harness")
            },
        }
    return result

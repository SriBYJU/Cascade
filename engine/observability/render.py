from __future__ import annotations

from typing import Any


def _metric(event: dict[str, Any], key: str) -> int:
    metrics = event.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    value = metrics.get(key, 0)
    return int(value) if isinstance(value, (int, float)) else 0


def render_trace(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No Cascade trace events recorded."
    lines: list[str] = []
    current_run: str | None = None
    current_task: str | None = None
    for event in events:
        run_id = str(event.get("run_id", "unknown"))
        task_id = str(event.get("task_id", "unknown"))
        if run_id != current_run:
            lines.append(f"run {run_id}")
            current_run = run_id
            current_task = None
        if task_id != current_task:
            lines.append(f"  task {task_id}")
            current_task = task_id

        actor = str(event.get("actor", "unknown")).upper()
        name = str(event.get("event", "event"))
        payload = event.get("payload")
        details: list[str] = []
        if isinstance(payload, dict):
            capability = payload.get("capability")
            effort = payload.get("reasoning_effort")
            if capability:
                route = str(capability)
                if effort:
                    route += f"/{effort}"
                details.append(route)
            model = payload.get("model")
            if model:
                details.append(f"model={model}")
            reason = payload.get("reason")
            if reason and name in {"validation_failed", "merge_failed", "retry"}:
                details.append(str(reason))
        latency = _metric(event, "latency_ms")
        if latency:
            details.append(f"{latency}ms")
        token_count = _metric(event, "input_tokens") + _metric(
            event, "output_tokens"
        )
        if token_count:
            details.append(f"{token_count}tok")
        suffix = f"  {' | '.join(details)}" if details else ""
        lines.append(f"    {actor:<13} {name}{suffix}")
    return "\n".join(lines)


def render_why(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "No route decision recorded yet."
    capability = payload.get("capability", payload.get("to", "unknown"))
    effort = payload.get("reasoning_effort", "unknown")
    model = payload.get("model_target", payload.get("model", "unknown"))
    cache = payload.get("cache_affinity", 0)
    budget = payload.get("budget_reserved", {})
    why = payload.get("why", [])
    escalation = payload.get("escalation_if", [])
    lines = [
        f"ROUTE: {capability} / {effort}",
        f"MODEL: {model}",
        f"CACHE AFFINITY: {float(cache):.3f}"
        if isinstance(cache, (int, float))
        else f"CACHE AFFINITY: {cache}",
    ]
    if isinstance(budget, dict):
        lines.append(
            "BUDGET: "
            f"{budget.get('tokens', 0)} model tokens, "
            f"{budget.get('context_tokens', 0)} context tokens"
        )
    if isinstance(why, list) and why:
        lines.append("WHY:")
        lines.extend(f"  - {item}" for item in why)
    if isinstance(escalation, list) and escalation:
        lines.append("ESCALATE IF:")
        lines.extend(f"  - {item}" for item in escalation)
    return "\n".join(lines)


def render_stats(stats: dict[str, Any]) -> str:
    head = int(stats.get("head_tokens", 0))
    total = int(stats.get("total_model_tokens", 0))
    worker = int(stats.get("worker_input_tokens", 0)) + int(
        stats.get("worker_output_tokens", 0)
    )
    cached = int(stats.get("cached_input_tokens", 0))
    lines = [
        f"HEAD MODEL TOKENS: {head}",
        f"WORKER MODEL TOKENS: {worker}",
        f"TOTAL MODEL TOKENS: {total}",
        f"CACHED INPUT TOKENS: {cached}",
        f"ROUTES: {int(stats.get('routes', 0))}",
        f"RETRIES: {int(stats.get('retries', 0))}",
        f"ESCALATIONS: {int(stats.get('escalations', 0))}",
        f"MODEL LATENCY: {int(stats.get('latency_ms', 0))}ms",
    ]
    cache = stats.get("cache")
    if isinstance(cache, dict):
        lines.append(
            "EXACT CACHE: "
            f"{int(cache.get('entries', 0))} entries / "
            f"{int(cache.get('hits', 0))} hits"
        )
    affinity = stats.get("prompt_cache_affinity")
    if isinstance(affinity, dict):
        lines.append(
            "PROMPT CACHE EVIDENCE: "
            f"{int(affinity.get('cached_input_tokens', 0))} cached / "
            f"{int(affinity.get('input_tokens', 0))} input tokens"
        )
    return "\n".join(lines)



def render_plan(planned: dict[str, Any], *, mode: str = "plan") -> str:
    route = planned.get("route", {})
    envelope = planned.get("envelope", {})
    if not isinstance(route, dict):
        route = {}
    if not isinstance(envelope, dict):
        envelope = {}
    write_paths = envelope.get("allowed_paths", [])
    evidence = envelope.get("evidence", [])
    risk = route.get("risk", "unknown")
    capability = route.get("capability", "unknown")
    effort = route.get("reasoning_effort", "unknown")
    model = route.get("model_target", "unknown")
    role = envelope.get("role", "unknown")
    worktree = (
        "isolated writer worktree"
        if role in {"builder", "debugger", "integrator"}
        else "shared read-only checkout"
    )
    budget = route.get("budget_reserved", {})
    if not isinstance(budget, dict):
        budget = {}
    why = route.get("why", [])
    lines = [
        f"MODE: {mode}",
        "DAG: single bounded node",
        f"ROUTE: {capability} / {effort}",
        f"MODEL TARGET: {model}",
        f"WORKER: {role}",
        f"RISK: {risk}",
        f"WORKSPACE: {worktree}",
        f"EVIDENCE REFS: {len(evidence) if isinstance(evidence, list) else 0}",
        (
            "WRITE SCOPE: "
            + ", ".join(str(item) for item in write_paths)
            if isinstance(write_paths, list) and write_paths
            else "WRITE SCOPE: read-only / unspecified"
        ),
        (
            "BUDGET: "
            f"{budget.get('tokens', 0)} model tokens / "
            f"{budget.get('context_tokens', 0)} context tokens"
        ),
    ]
    if isinstance(why, list) and why:
        lines.append("WHY:")
        lines.extend(f"  - {item}" for item in why)
    return "\n".join(lines)

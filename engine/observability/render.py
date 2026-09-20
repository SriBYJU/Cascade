from __future__ import annotations

from typing import Any


def compact_trace(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a deterministic, metadata-only trace export."""
    runs: dict[str, dict[str, Any]] = {}
    summary = {
        "events": 0,
        "routes": 0,
        "retries": 0,
        "escalations": 0,
        "validation_passed": 0,
        "validation_failed": 0,
    }
    for event in events:
        run_id = str(event.get("run_id", "unknown"))
        task_id = str(event.get("task_id", "unknown"))
        run = runs.setdefault(run_id, {"run_id": run_id, "tasks": {}})
        task = run["tasks"].setdefault(
            task_id,
            {"task_id": task_id, "events": []},
        )
        name = str(event.get("event", "event"))
        metrics = event.get("metrics")
        safe_metrics = (
            {
                key: metrics[key]
                for key in (
                    "latency_ms",
                    "input_tokens",
                    "output_tokens",
                    "cached_input_tokens",
                    "context_bytes",
                )
                if key in metrics
            }
            if isinstance(metrics, dict)
            else {}
        )
        payload = event.get("payload")
        safe_payload: dict[str, Any] = {}
        if isinstance(payload, dict):
            for key in (
                "capability",
                "reasoning_effort",
                "model",
                "model_target",
                "passed",
                "timed_out",
            ):
                if key in payload:
                    safe_payload[key] = payload[key]
            checks = payload.get("checks")
            if isinstance(checks, list):
                safe_payload["checks"] = len(checks)
        provenance = event.get("provenance")
        safe_provenance = {}
        if isinstance(provenance, dict):
            for key in ("source_type", "source_id", "trust", "scope"):
                if key in provenance:
                    safe_provenance[key] = provenance[key]
        task["events"].append(
            {
                "attempt_id": int(event.get("attempt_id", 1)),
                "event": name,
                "ts": str(event.get("ts", "")),
                "actor": str(event.get("actor", "unknown")),
                "metrics": safe_metrics,
                "metadata": safe_payload,
                "provenance": safe_provenance,
            }
        )
        summary["events"] += 1
        if name == "route_selected":
            summary["routes"] += 1
        elif name == "retry":
            summary["retries"] += 1
        elif name == "escalated":
            summary["escalations"] += 1
        elif name == "validation_passed":
            summary["validation_passed"] += 1
        elif name == "validation_failed":
            summary["validation_failed"] += 1

    return {
        "format": "cascade-compact-trace",
        "version": 1,
        "summary": summary,
        "runs": [
            {
                "run_id": run["run_id"],
                "tasks": list(run["tasks"].values()),
            }
            for run in runs.values()
        ],
    }


def _metric(event: dict[str, Any], key: str) -> int:
    metrics = event.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    value = metrics.get(key, 0)
    return int(value) if isinstance(value, (int, float)) else 0


def _event_stage(name: str) -> str:
    lowered = name.lower()
    if "route" in lowered or "escalat" in lowered:
        return "ROUTE"
    if "context" in lowered or "cache" in lowered or "fingerprint" in lowered:
        return "CONTEXT"
    if "worker" in lowered or "architecture" in lowered:
        return "AGENT"
    if "validation" in lowered or "review" in lowered:
        return "VERIFY"
    if "merge" in lowered or "integrat" in lowered:
        return "MERGE"
    if "retry" in lowered or "circuit" in lowered:
        return "RETRY"
    return "STATE"


def render_trace(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No Cascade trace events recorded."

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    run_order: list[str] = []
    task_order: dict[str, list[str]] = {}
    for event in events:
        run_id = str(event.get("run_id", "unknown"))
        task_id = str(event.get("task_id", "unknown"))
        if run_id not in grouped:
            grouped[run_id] = {}
            run_order.append(run_id)
            task_order[run_id] = []
        if task_id not in grouped[run_id]:
            grouped[run_id][task_id] = []
            task_order[run_id].append(task_id)
        grouped[run_id][task_id].append(event)

    lines: list[str] = []
    for run_index, run_id in enumerate(run_order):
        if run_index:
            lines.append("")
        lines.append(f"run {run_id}")
        tasks = task_order[run_id]
        for task_index, task_id in enumerate(tasks):
            task_last = task_index == len(tasks) - 1
            task_branch = "└─" if task_last else "├─"
            child_prefix = "   " if task_last else "│  "
            lines.append(f"{task_branch} task {task_id}")
            task_events = grouped[run_id][task_id]
            for event_index, event in enumerate(task_events):
                event_last = event_index == len(task_events) - 1
                event_branch = "└─" if event_last else "├─"
                actor = str(event.get("actor", "unknown")).upper()
                name = str(event.get("event", "event"))
                stage = _event_stage(name)
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
                    if reason and name in {
                        "validation_failed",
                        "merge_failed",
                        "retry",
                    }:
                        details.append(str(reason))
                latency = _metric(event, "latency_ms")
                if latency:
                    details.append(f"{latency}ms")
                token_count = _metric(
                    event,
                    "input_tokens",
                ) + _metric(event, "output_tokens")
                if token_count:
                    details.append(f"{token_count}tok")
                suffix = (
                    f"  {' | '.join(details)}"
                    if details
                    else ""
                )
                lines.append(
                    f"{child_prefix}{event_branch} "
                    f"{stage:<7} {actor:<11} {name}{suffix}"
                )
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
        (
            f"CACHE AFFINITY: {float(cache):.3f}"
            if isinstance(cache, (int, float))
            else f"CACHE AFFINITY: {cache}"
        ),
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
        "MODEL USAGE",
        f"  HEAD MODEL TOKENS: {head}",
        f"  WORKER MODEL TOKENS: {worker}",
        f"  TOTAL MODEL TOKENS: {total}",
        f"  WEIGHTED USAGE: {float(stats.get('weighted_usage', 0.0)):.2f}",
        f"  CACHED INPUT TOKENS: {cached}",
        "",
        "ROUTING",
        f"  ROUTES: {int(stats.get('routes', 0))}",
        f"  RETRIES: {int(stats.get('retries', 0))}",
        f"  ESCALATIONS: {int(stats.get('escalations', 0))}",
        "",
        "EXECUTION",
        f"  MODEL LATENCY: {int(stats.get('latency_ms', 0))}ms",
        f"  CONTEXT TRANSFER: {int(stats.get('context_bytes', 0))} bytes",
        f"  TOOL CALLS: {int(stats.get('tool_calls', 0))}",
        f"  AGENT CALLS: {int(stats.get('agent_calls', 0))}",
        f"  TRAJECTORY STEPS: {int(stats.get('trajectory_steps', 0))}",
    ]
    savings = stats.get("measured_savings")
    if isinstance(savings, dict):
        token_savings = savings.get("token_savings_percent")
        weighted_savings = savings.get(
            "weighted_usage_savings_percent"
        )
        baseline = str(savings.get("baseline", "plain"))
        candidate_quality = float(
            savings.get("candidate_verified_success_percent", 0.0)
        )
        baseline_quality = float(
            savings.get("baseline_verified_success_percent", 0.0)
        )
        cases = int(savings.get("cases", 0))
        repeats = int(savings.get("repeats", 0))
        lines.extend(["", "EVIDENCE-BACKED SAVINGS"])
        if (
            savings.get("public_token_claim_eligible")
            and isinstance(token_savings, (int, float))
        ):
            lines.append(
                "  CASCADE SAVES "
                f"{float(token_savings):.1f}% OF TOTAL MODEL TOKENS "
                f"VS {baseline.upper()}"
            )
        elif isinstance(token_savings, (int, float)):
            lines.append(
                "  TOKEN REDUCTION: "
                f"{float(token_savings):.1f}% "
                "(not public-claim eligible)"
            )
        if (
            savings.get("public_weighted_usage_claim_eligible")
            and isinstance(weighted_savings, (int, float))
        ):
            lines.append(
                "  CASCADE SAVES "
                f"{float(weighted_savings):.1f}% OF WEIGHTED MODEL "
                f"USAGE VS {baseline.upper()}"
            )
        elif isinstance(weighted_savings, (int, float)):
            lines.append(
                "  WEIGHTED-USAGE REDUCTION: "
                f"{float(weighted_savings):.1f}% "
                "(not public-claim eligible)"
            )
        lines.extend(
            [
                (
                    "  VERIFIED SUCCESS: "
                    f"{candidate_quality:.1f}% vs {baseline_quality:.1f}%"
                ),
                (
                    "  EVIDENCE: "
                    f"{cases} cases × {repeats} repeats"
                ),
                (
                    "  TOKEN FORMULA: 100 × "
                    "(1 - Cascade tokens / Plain tokens)"
                ),
                (
                    "  USAGE FORMULA: 100 × "
                    "(1 - Cascade weighted usage / Plain weighted usage)"
                ),
                (
                    "  USAGE MODEL: head×1.0 + "
                    "Σ(worker tokens×active route/model cost weight)"
                ),
                (
                    "  NOTE: weighted usage is Cascade's normalized "
                    "hypothesis metric, not provider billing/quota usage."
                ),
            ]
        )
        report_path = stats.get("measured_savings_report")
        if report_path:
            lines.append(f"  REPORT: {report_path}")

    definition = stats.get("weighted_usage_definition")
    if isinstance(definition, dict):
        lines.extend(
            [
                "",
                "USAGE HYPOTHESIS",
                (
                    "  VERSION: "
                    f"{definition.get('version', 'unknown')}"
                ),
                (
                    "  FORMULA: "
                    f"{definition.get('formula', 'unknown')}"
                ),
            ]
        )
        weights = definition.get("route_cost_weights")
        if isinstance(weights, dict) and weights:
            rendered_weights = ", ".join(
                f"{name}={float(value):.2f}"
                for name, value in sorted(weights.items())
                if isinstance(value, (int, float))
            )
            if rendered_weights:
                lines.append(f"  ACTIVE WEIGHTS: {rendered_weights}")
        note = definition.get("note")
        if note:
            lines.append(f"  NOTE: {note}")

    cache = stats.get("cache")
    if isinstance(cache, dict):
        lines.extend(
            [
                "",
                "CACHE",
                (
                    "  EXACT CACHE: "
                    f"{int(cache.get('entries', 0))} entries / "
                    f"{int(cache.get('hits', 0))} hits"
                ),
            ]
        )
    regret = stats.get("route_regret")
    if isinstance(regret, dict):
        mean = regret.get("mean")
        mean_text = (
            "n/a"
            if mean is None
            else f"{float(mean):.2f}"
        )
        lines.append(
            "  ROUTE REGRET: "
            f"{mean_text} mean / "
            f"{int(regret.get('samples', 0))} replay samples"
        )
    affinity = stats.get("prompt_cache_affinity")
    if isinstance(affinity, dict):
        lines.append(
            "  PROMPT CACHE EVIDENCE: "
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
        (
            f"EVIDENCE REFS: {len(evidence)}"
            if isinstance(evidence, list)
            else "EVIDENCE REFS: 0"
        ),
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

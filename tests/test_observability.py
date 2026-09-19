from engine.observability.render import (
    compact_trace,
    render_plan,
    render_stats,
    render_trace,
    render_why,
)


def test_trace_renderer_builds_tree():
    text = render_trace(
        [
            {
                "run_id": "r1",
                "task_id": "t1",
                "actor": "head",
                "event": "route_selected",
                "metrics": {},
                "payload": {
                    "capability": "build",
                    "reasoning_effort": "medium",
                },
            },
            {
                "run_id": "r1",
                "task_id": "t1",
                "actor": "builder",
                "event": "worker_completed",
                "metrics": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "latency_ms": 500,
                },
                "payload": {"model": "example"},
            },
        ]
    )
    assert "run r1" in text
    assert "task t1" in text
    assert "HEAD" in text
    assert "build/medium" in text
    assert "120tok" in text


def test_compact_trace_export_is_metadata_only_and_deterministic():
    events = [
        {
            "run_id": "r1",
            "task_id": "t1",
            "attempt_id": 2,
            "event": "route_selected",
            "ts": "2026-01-01T00:00:00Z",
            "actor": "head",
            "metrics": {"latency_ms": 10, "secret_metric": "omit"},
            "payload": {
                "capability": "build",
                "reasoning_effort": "medium",
                "model_target": "auto",
                "prompt": "do not export this",
            },
            "provenance": {
                "source_type": "cascade",
                "source_id": "runtime",
                "trust": "trusted-policy",
            },
        },
        {
            "run_id": "r1",
            "task_id": "t1",
            "event": "validation_passed",
            "actor": "deterministic",
            "metrics": {"input_tokens": 4, "output_tokens": 2},
            "payload": {"passed": True, "checks": [{"name": "pytest"}]},
        },
    ]

    exported = compact_trace(events)

    assert exported["format"] == "cascade-compact-trace"
    assert exported["summary"] == {
        "events": 2,
        "routes": 1,
        "retries": 0,
        "escalations": 0,
        "validation_passed": 1,
        "validation_failed": 0,
    }
    assert exported["runs"][0]["tasks"][0]["events"][0]["metadata"] == {
        "capability": "build",
        "reasoning_effort": "medium",
        "model_target": "auto",
    }
    assert "prompt" not in str(exported)
    assert "secret_metric" not in str(exported)


def test_why_renderer_exposes_cache_budget_and_escalation():
    text = render_why(
        {
            "capability": "build",
            "reasoning_effort": "medium",
            "model_target": "auto",
            "cache_affinity": 0.5,
            "budget_reserved": {"tokens": 8000, "context_tokens": 1000},
            "why": ["narrow write"],
            "escalation_if": ["tests fail"],
        }
    )
    assert "CACHE AFFINITY: 0.500" in text
    assert "8000 model tokens" in text
    assert "tests fail" in text


def test_stats_renderer_reports_head_and_total():
    text = render_stats(
        {
            "head_tokens": 10,
            "worker_input_tokens": 20,
            "worker_output_tokens": 5,
            "total_model_tokens": 35,
            "cached_input_tokens": 4,
            "weighted_usage": 17.5,
            "routes": 1,
            "retries": 0,
            "escalations": 0,
            "latency_ms": 100,
            "context_bytes": 2048,
            "tool_calls": 3,
            "agent_calls": 1,
            "trajectory_steps": 9,
            "cache": {"entries": 2, "hits": 3},
        }
    )
    assert "HEAD MODEL TOKENS: 10" in text
    assert "TOTAL MODEL TOKENS: 35" in text
    assert "WEIGHTED USAGE: 17.50" in text
    assert "EXACT CACHE: 2 entries / 3 hits" in text
    assert "CONTEXT TRANSFER: 2048 bytes" in text
    assert "TOOL CALLS: 3" in text
    assert "TRAJECTORY STEPS: 9" in text



def test_plan_renderer_exposes_route_workspace_and_budget():
    text = render_plan(
        {
            "route": {
                "capability": "build",
                "reasoning_effort": "medium",
                "model_target": "auto",
                "risk": "low",
                "budget_reserved": {
                    "tokens": 8000,
                    "context_tokens": 1200,
                },
                "why": ["bounded write"],
            },
            "envelope": {
                "role": "builder",
                "allowed_paths": ["src/**"],
                "evidence": [{}, {}],
            },
        }
    )
    assert "DAG: single bounded node" in text
    assert "WORKSPACE: isolated writer worktree" in text
    assert "EVIDENCE REFS: 2" in text
    assert "8000 model tokens" in text



def test_trace_renderer_distinguishes_validation_and_merge_stages():
    text = render_trace(
        [
            {
                "run_id": "r2",
                "task_id": "t2",
                "actor": "deterministic",
                "event": "validation_passed",
                "metrics": {},
                "payload": {},
            },
            {
                "run_id": "r2",
                "task_id": "t2",
                "actor": "integrator",
                "event": "merge_completed",
                "metrics": {},
                "payload": {},
            },
        ]
    )
    assert "VERIFY" in text
    assert "MERGE" in text
    assert "└─ task t2" in text


def test_stats_renderer_has_visual_sections():
    text = render_stats(
        {
            "head_tokens": 1,
            "worker_input_tokens": 2,
            "worker_output_tokens": 3,
            "total_model_tokens": 6,
            "weighted_usage": 4.0,
        }
    )
    assert "MODEL USAGE" in text
    assert "ROUTING" in text
    assert "EXECUTION" in text

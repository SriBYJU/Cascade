from engine.observability.render import render_plan, render_stats, render_trace, render_why


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
            "cache": {"entries": 2, "hits": 3},
        }
    )
    assert "HEAD MODEL TOKENS: 10" in text
    assert "TOTAL MODEL TOKENS: 35" in text
    assert "WEIGHTED USAGE: 17.50" in text
    assert "EXACT CACHE: 2 entries / 3 hits" in text



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

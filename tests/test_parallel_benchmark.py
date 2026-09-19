from engine.evaluation.parallel_benchmark import (
    conflict_fixture,
    independent_fixture,
    run_scheduler_benchmark,
)


def test_independent_fixture_is_single_parallel_level():
    levels = [
        [node.task_id for node in level]
        for level in independent_fixture().levels()
    ]
    assert levels == [["auth", "docs", "payments"]]


def test_conflicting_writer_is_serialized():
    levels = [
        [node.task_id for node in level]
        for level in conflict_fixture().levels()
    ]
    assert "auth-a" in levels[0]
    assert "payments" in levels[0]
    assert levels[1] == ["auth-b"]


def test_scheduler_benchmark_is_explicitly_scheduler_only():
    result = run_scheduler_benchmark(
        repeats=1,
        sleep_seconds=0.0,
        max_workers=3,
    )
    assert result["measured"] is True
    assert result["suite"] == "parallel-scheduler-v1"
    assert "scheduler-only" in result["scope"]

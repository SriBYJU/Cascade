from engine.scheduler.executor import ParallelTaskSpec, compile_safe_dag, execute_dag


def test_write_conflicts_are_serialized():
    dag = compile_safe_dag([
        ParallelTaskSpec("a", "auth one", write_patterns=("src/auth/**",)),
        ParallelTaskSpec("b", "payments", write_patterns=("src/payments/**",)),
        ParallelTaskSpec("c", "auth two", write_patterns=("src/auth/session.py",)),
    ])
    assert "a" in dag.nodes["c"].depends_on
    assert "a" not in dag.nodes["b"].depends_on


def test_execute_dag_respects_dependencies():
    dag = compile_safe_dag([
        ParallelTaskSpec("a", "one"),
        ParallelTaskSpec("b", "two"),
        ParallelTaskSpec("c", "three", depends_on={"a", "b"}),
    ])
    seen = []
    result = execute_dag(dag, lambda node: seen.append(node.task_id) or node.task_id, max_workers=2)
    assert set(result) == {"a", "b", "c"}
    assert seen[-1] == "c"

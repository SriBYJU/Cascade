import pytest

from engine.scheduler.dag import TaskDAG, TaskNode
from engine.scheduler.write_sets import WriteSet, conflict_graph, overlap


def test_dag_levels():
    dag = TaskDAG([
        TaskNode("map"),
        TaskNode("auth", {"map"}),
        TaskNode("frontend", {"map"}),
        TaskNode("integrate", {"auth", "frontend"}),
    ])
    assert [[n.task_id for n in level] for level in dag.levels()] == [["map"], ["auth", "frontend"], ["integrate"]]


def test_cycle_rejected():
    with pytest.raises(ValueError):
        TaskDAG([TaskNode("a", {"b"}), TaskNode("b", {"a"})])


def test_write_conflict_graph():
    a = WriteSet("a", ("src/auth/**",))
    b = WriteSet("b", ("src/payments/**",))
    c = WriteSet("c", ("src/auth/middleware.py",))
    assert not overlap(a, b)
    assert overlap(a, c)
    graph = conflict_graph([a, b, c])
    assert graph["a"] == {"c"}

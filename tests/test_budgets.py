import pytest

from engine.schemas import BudgetReservation
from engine.scheduler.budgets import BudgetManager


def test_budget_reservation_denial():
    b = BudgetManager(total_tokens=100, head_tokens=50, context_tokens=50)
    b.reserve("a", BudgetReservation(tokens=80, head_tokens=30, context_tokens=20))
    with pytest.raises(RuntimeError):
        b.reserve("b", BudgetReservation(tokens=30, head_tokens=0, context_tokens=0))


def test_release_frees_budget():
    b = BudgetManager(total_tokens=100, head_tokens=50, context_tokens=50)
    b.reserve("a", BudgetReservation(tokens=80, head_tokens=30, context_tokens=20))
    b.release("a")
    b.reserve("b", BudgetReservation(tokens=100, head_tokens=50, context_tokens=50))
    assert b.snapshot().total_tokens == 100



def test_denied_replacement_preserves_existing_reservation():
    b = BudgetManager(
        total_tokens=100,
        head_tokens=100,
        context_tokens=100,
    )
    original = BudgetReservation(
        tokens=40,
        head_tokens=10,
        context_tokens=10,
    )
    b.reserve("a", original)
    b.reserve(
        "b",
        BudgetReservation(
            tokens=50,
            head_tokens=0,
            context_tokens=0,
        ),
    )

    with pytest.raises(RuntimeError):
        b.reserve(
            "a",
            BudgetReservation(
                tokens=60,
                head_tokens=10,
                context_tokens=10,
            ),
        )

    snapshot = b.snapshot()
    assert snapshot.reservations["a"] == original
    assert snapshot.total_tokens == 90

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from ..schemas import BudgetReservation


@dataclass(slots=True)
class BudgetSnapshot:
    total_tokens: int
    head_tokens: int
    context_tokens: int
    reservations: dict[str, BudgetReservation] = field(default_factory=dict)


class BudgetManager:
    def __init__(self, *, total_tokens: int = 150000, head_tokens: int = 50000, context_tokens: int = 30000):
        self.total_limit = total_tokens
        self.head_limit = head_tokens
        self.context_limit = context_tokens
        self._reservations: dict[str, BudgetReservation] = {}
        self._lock = threading.RLock()

    def reserve(self, task_id: str, reservation: BudgetReservation) -> None:
        with self._lock:
            others = [
                value
                for key, value in self._reservations.items()
                if key != task_id
            ]
            total = sum(r.tokens for r in others) + reservation.tokens
            head = sum(r.head_tokens for r in others) + reservation.head_tokens
            context = (
                sum(r.context_tokens for r in others)
                + reservation.context_tokens
            )
            if total > self.total_limit:
                raise RuntimeError("total model-token budget reservation denied")
            if head > self.head_limit:
                raise RuntimeError("head-model budget reservation denied")
            if context > self.context_limit:
                raise RuntimeError("context budget reservation denied")
            self._reservations[task_id] = reservation

    def release(self, task_id: str) -> None:
        with self._lock:
            self._reservations.pop(task_id, None)

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            return BudgetSnapshot(
                total_tokens=sum(r.tokens for r in self._reservations.values()),
                head_tokens=sum(r.head_tokens for r in self._reservations.values()),
                context_tokens=sum(r.context_tokens for r in self._reservations.values()),
                reservations=dict(self._reservations),
            )

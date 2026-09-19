from __future__ import annotations

import threading
from concurrent.futures import Future
from typing import Callable, TypeVar

T = TypeVar("T")


class SingleFlight:
    """Coalesces simultaneous identical work in-process."""

    def __init__(self):
        self._lock = threading.Lock()
        self._inflight: dict[str, Future] = {}

    def do(self, key: str, fn: Callable[[], T]) -> tuple[T, bool]:
        owner = False
        with self._lock:
            future = self._inflight.get(key)
            if future is None:
                future = Future()
                self._inflight[key] = future
                owner = True
        if owner:
            try:
                value = fn()
                future.set_result(value)
            except BaseException as exc:
                future.set_exception(exc)
                raise
            finally:
                with self._lock:
                    self._inflight.pop(key, None)
            return value, False
        return future.result(), True

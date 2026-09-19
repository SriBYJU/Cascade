from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class BoundedExecutor:
    def __init__(self, max_workers: int = 3):
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self.max_workers = max_workers

    def map_unordered(self, items: list[T], fn: Callable[[T], R]) -> list[R]:
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="cascade") as pool:
            futures: list[Future[R]] = [pool.submit(fn, item) for item in items]
            return [future.result() for future in as_completed(futures)]

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UsageTotals:
    head_input_tokens: int = 0
    head_output_tokens: int = 0
    worker_input_tokens: int = 0
    worker_output_tokens: int = 0
    cached_input_tokens: int = 0

    @property
    def head_tokens(self) -> int:
        return self.head_input_tokens + self.head_output_tokens

    @property
    def total_tokens(self) -> int:
        return self.head_tokens + self.worker_input_tokens + self.worker_output_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "head_input_tokens": self.head_input_tokens,
            "head_output_tokens": self.head_output_tokens,
            "head_tokens": self.head_tokens,
            "worker_input_tokens": self.worker_input_tokens,
            "worker_output_tokens": self.worker_output_tokens,
            "total_tokens": self.total_tokens,
            "cached_input_tokens": self.cached_input_tokens,
        }

"""Optional future semantic cache.

Cascade deliberately ships exact cache first. This module exposes an explicit disabled
surface so callers cannot accidentally treat fuzzy reuse as trustworthy evidence.
"""
from __future__ import annotations


class SemanticCacheDisabled(RuntimeError):
    pass


class SemanticCache:
    enabled = False

    def get(self, *_: object, **__: object) -> None:
        raise SemanticCacheDisabled("semantic cache is disabled until exact-cache evaluation justifies it")

    def put(self, *_: object, **__: object) -> None:
        raise SemanticCacheDisabled("semantic cache is disabled until exact-cache evaluation justifies it")

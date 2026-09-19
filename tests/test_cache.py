from pathlib import Path

from engine.cache.exact import ExactCache, make_cache_key
from engine.cache.singleflight import SingleFlight
from engine.state.db import StateDB


def test_stale_cache_invalidates(tmp_path: Path):
    db = StateDB(tmp_path / "state.db")
    cache = ExactCache(db)
    key = make_cache_key("task", "fp1", [], {}, {})
    cache.put(key, "fp1", {"x": 1})
    assert cache.get(key, "fp1") == {"x": 1}
    assert cache.get(key, "fp2") is None


def test_singleflight_reuses_inflight_result():
    sf = SingleFlight()
    value, joined = sf.do("k", lambda: 4)
    assert value == 4 and joined is False

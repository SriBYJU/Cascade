from pathlib import Path

import pytest

from engine.evaluation.release_bundle import run_release_benchmark


def test_release_benchmark_requires_three_repeats(tmp_path: Path):
    with pytest.raises(ValueError):
        run_release_benchmark(
            tmp_path,
            profiles_path="profiles.json",
            repeats=2,
        )

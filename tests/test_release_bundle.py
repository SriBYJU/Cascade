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



def test_release_benchmark_requires_complete_capability_pool(
    tmp_path: Path,
):
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        """[
          {
            "model_id": "only-build",
            "capability": "build",
            "reasoning_efforts": ["medium"]
          }
        ]"""
    )

    with pytest.raises(
        ValueError,
        match="explicit profiles for every model-backed capability",
    ):
        run_release_benchmark(
            tmp_path,
            profiles_path=profiles,
            repeats=3,
        )

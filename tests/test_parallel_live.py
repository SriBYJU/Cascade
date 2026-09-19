from pathlib import Path
import threading
import time

from engine.adapters.base import AdapterResult
from engine.evaluation.parallel_live import (
    ParallelLiveHarness,
    ParallelLiveScenario,
    ParallelLiveTask,
    load_parallel_scenarios,
)
from engine.schemas import ReasoningEffort


class ParallelFakeAdapter:
    name = "parallel-fake"

    def __init__(self, *, synchronize: bool = True) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.barrier = (
            threading.Barrier(2)
            if synchronize
            else None
        )

    def available(self) -> bool:
        return True

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        model: str = "auto",
        effort: ReasoningEffort = ReasoningEffort.MEDIUM,
        timeout_seconds: int = 900,
        sandbox_mode: str = "read-only",
    ) -> AdapterResult:
        del model, effort, timeout_seconds
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.barrier is not None:
                self.barrier.wait(timeout=2)
            time.sleep(0.05)
            if sandbox_mode == "workspace-write":
                if '"goal": "Fix alpha.py' in prompt:
                    Path(cwd, "alpha.py").write_text(
                        "def alpha():\n    return 10\n"
                    )
                elif '"goal": "Fix beta.py' in prompt:
                    Path(cwd, "beta.py").write_text(
                        "def beta():\n    return 20\n"
                    )
            return AdapterResult(
                True,
                "done",
                usage={"input_tokens": 10, "output_tokens": 2},
            )
        finally:
            with self.lock:
                self.active -= 1


def test_parallel_live_manifest_loads():
    root = Path(__file__).parents[1]
    scenarios = load_parallel_scenarios(
        root / "benchmarks" / "fixtures" / "parallel_live.json"
    )
    assert len(scenarios) >= 2
    assert all(len(scenario.tasks) >= 3 for scenario in scenarios)


def test_parallel_live_harness_overlaps_disjoint_writers(tmp_path: Path):
    scenario = ParallelLiveScenario(
        scenario_id="two",
        files={
            "pyproject.toml": (
                '[project]\nname="fixture"\nversion="0.0.0"\n'
                '[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
            ),
            "alpha.py": "def alpha():\n    return 1\n",
            "beta.py": "def beta():\n    return 2\n",
            "tests/test_smoke.py": (
                "from alpha import alpha\n"
                "from beta import beta\n\n"
                "def test_imports():\n"
                "    assert isinstance(alpha(), int)\n"
                "    assert isinstance(beta(), int)\n"
            ),
        },
        tasks=(
            ParallelLiveTask(
                "alpha",
                "Fix alpha.py so alpha() returns 10.",
                ("alpha.py",),
                (("python", "-c", "from alpha import alpha; assert alpha() == 10"),),
            ),
            ParallelLiveTask(
                "beta",
                "Fix beta.py so beta() returns 20.",
                ("beta.py",),
                (("python", "-c", "from beta import beta; assert beta() == 20"),),
            ),
        ),
    )
    adapter = ParallelFakeAdapter()
    result = ParallelLiveHarness(
        tmp_path,
        adapter=adapter,
    ).run_scenario(
        scenario,
        mode="parallel",
        max_workers=2,
    )
    assert result["measured"] is True
    assert result["verified_success"] is True
    assert adapter.max_active >= 2



def test_parallel_live_harness_cleans_writer_worktrees(tmp_path: Path):
    scenario = ParallelLiveScenario(
        scenario_id="cleanup",
        files={
            "pyproject.toml": (
                '[project]\nname="fixture"\nversion="0.0.0"\n'
                '[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
            ),
            "alpha.py": "def alpha():\n    return 1\n",
            "beta.py": "def beta():\n    return 2\n",
            "tests/test_smoke.py": (
                "def test_smoke():\n    assert True\n"
            ),
        },
        tasks=(
            ParallelLiveTask(
                "alpha",
                "Fix alpha.py so alpha() returns 10.",
                ("alpha.py",),
                (
                    (
                        "python",
                        "-c",
                        "from alpha import alpha; assert alpha() == 10",
                    ),
                ),
            ),
            ParallelLiveTask(
                "beta",
                "Fix beta.py so beta() returns 20.",
                ("beta.py",),
                (
                    (
                        "python",
                        "-c",
                        "from beta import beta; assert beta() == 20",
                    ),
                ),
            ),
        ),
    )
    result = ParallelLiveHarness(
        tmp_path,
        adapter=ParallelFakeAdapter(),
    ).run_scenario(
        scenario,
        mode="parallel",
        max_workers=2,
    )
    assert result["verified_success"] is True
    leftovers = list(tmp_path.glob(".repo.cascade-worktrees/*"))
    assert leftovers == []



def test_parallel_live_summary_records_system_metrics(tmp_path: Path):
    scenario = ParallelLiveScenario(
        scenario_id="metrics",
        files={
            "pyproject.toml": (
                '[project]\nname="fixture"\nversion="0.0.0"\n'
                '[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
            ),
            "alpha.py": "def alpha():\n    return 1\n",
            "beta.py": "def beta():\n    return 2\n",
            "tests/test_smoke.py": "def test_smoke():\n    assert True\n",
        },
        tasks=(
            ParallelLiveTask(
                "alpha",
                "Fix alpha.py so alpha() returns 10.",
                ("alpha.py",),
                (
                    (
                        "python",
                        "-c",
                        "from alpha import alpha; assert alpha() == 10",
                    ),
                ),
            ),
            ParallelLiveTask(
                "beta",
                "Fix beta.py so beta() returns 20.",
                ("beta.py",),
                (
                    (
                        "python",
                        "-c",
                        "from beta import beta; assert beta() == 20",
                    ),
                ),
            ),
        ),
    )
    report = ParallelLiveHarness(
        tmp_path,
        adapter=ParallelFakeAdapter(synchronize=False),
    ).run(
        [scenario],
        repeats=1,
        max_workers=2,
    )
    row = report["summary"]["metrics"]
    assert "sequential_model_tokens_mean" in row
    assert "parallel_model_tokens_mean" in row
    assert "sequential_context_bytes_mean" in row
    assert "parallel_context_bytes_mean" in row
    assert "sequential_retries_mean" in row
    assert "parallel_retries_mean" in row
    assert "merge_conflicts_observed" in row
    assert row["all_verified"] is True



def test_parallel_live_report_records_controlled_profiles(
    tmp_path: Path,
):
    from engine.schemas import Capability, ModelProfile

    profiles = {
        Capability.BUILD: ModelProfile(
            model_id="controlled-build",
            capability=Capability.BUILD,
            reasoning_efforts=[ReasoningEffort.MEDIUM],
        )
    }
    scenario = ParallelLiveScenario(
        scenario_id="profile",
        files={
            "pyproject.toml": (
                '[project]\nname="fixture"\nversion="0.0.0"\n'
                '[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
            ),
            "alpha.py": "def alpha():\n    return 1\n",
            "beta.py": "def beta():\n    return 2\n",
            "tests/test_smoke.py": "def test_smoke():\n    assert True\n",
        },
        tasks=(
            ParallelLiveTask(
                "alpha",
                "Fix alpha.py so alpha() returns 10.",
                ("alpha.py",),
                (
                    (
                        "python",
                        "-c",
                        "from alpha import alpha; assert alpha() == 10",
                    ),
                ),
            ),
            ParallelLiveTask(
                "beta",
                "Fix beta.py so beta() returns 20.",
                ("beta.py",),
                (
                    (
                        "python",
                        "-c",
                        "from beta import beta; assert beta() == 20",
                    ),
                ),
            ),
        ),
    )
    report = ParallelLiveHarness(
        tmp_path,
        adapter=ParallelFakeAdapter(synchronize=False),
        profiles=profiles,
    ).run(
        [scenario],
        repeats=1,
        max_workers=2,
    )
    assert report["model_profiles"][0]["model_id"] == "controlled-build"

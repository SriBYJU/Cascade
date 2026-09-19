from pathlib import Path

from engine.adapters.base import AdapterResult
from engine.evaluation.harness import EvaluationHarness
from engine.evaluation.models import BenchmarkCase, aggregate_trials, load_cases
from engine.schemas import ReasoningEffort


class FakeEditingAdapter:
    name = "fake"

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
        del prompt, model, effort, timeout_seconds, sandbox_mode
        Path(cwd, "value.py").write_text("VALUE = 2\n")
        return AdapterResult(
            True,
            "updated value",
            events=[{"type": "fake"}],
            usage={
                "input_tokens": 100,
                "output_tokens": 20,
                "cached_input_tokens": 40,
            },
        )


def test_live_manifest_loads():
    root = Path(__file__).parents[1]
    cases = load_cases(root / "benchmarks" / "fixtures" / "live_tasks.json")
    assert len(cases) >= 4
    assert all(case.acceptance for case in cases)


def test_plain_harness_records_measured_trial(tmp_path: Path):
    case = BenchmarkCase(
        case_id="fake",
        category="trivial-edit",
        task="set VALUE to 2",
        files={"value.py": "VALUE = 1\n"},
        write_paths=["value.py"],
        acceptance=[
            [
                "python",
                "-c",
                "import value; assert value.VALUE == 2",
            ]
        ],
    )
    harness = EvaluationHarness(tmp_path, adapter=FakeEditingAdapter())
    report = harness.run(
        [case],
        configs=["plain"],
        repeats=2,
        output_dir=tmp_path / "report",
    )
    assert report["measured"] is True
    trials = report["trials"]
    assert len(trials) == 2
    assert all(item["verified_success"] for item in trials)
    assert report["summary"]["plain"]["total_model_tokens_mean"] == 120
    assert report["summary"]["plain"]["cached_input_tokens_mean"] == 40


def test_aggregate_trials_empty():
    assert aggregate_trials([]) == {}

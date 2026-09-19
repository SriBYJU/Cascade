from pathlib import Path

from engine.adapters.base import AdapterResult
from engine.evaluation.harness import EvaluationHarness
from engine.evaluation.models import BenchmarkCase, aggregate_trials, load_cases
from engine.schemas import ReasoningEffort


class FakeEditingAdapter:
    name = "fake"

    def __init__(self) -> None:
        self.sandbox_modes: list[str] = []

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
        del prompt, model, effort, timeout_seconds
        self.sandbox_modes.append(sandbox_mode)
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
    assert len(cases) >= 20
    assert all(case.acceptance or case.answer_contains for case in cases)
    categories = {case.category for case in cases}
    required = {
        "trivial-edit",
        "search",
        "single-file-bug",
        "multi-file-bug",
        "feature",
        "test-repair",
        "migration",
        "frontend",
        "docs-lookup",
        "architecture",
        "security",
        "repo-explore",
        "refactor",
        "ambiguity",
    }
    assert required <= categories


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
    adapter = FakeEditingAdapter()
    harness = EvaluationHarness(tmp_path, adapter=adapter)
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
    assert adapter.sandbox_modes == ["workspace-write", "workspace-write"]


def test_aggregate_trials_empty():
    assert aggregate_trials([]) == {}



def test_answer_acceptance_supports_read_only_tasks(tmp_path: Path):
    case = BenchmarkCase(
        case_id="search",
        category="search",
        task="find config",
        files={"config.py": "VALUE = 1\n"},
        write_paths=[],
        acceptance=[],
        answer_contains=["config.py"],
    )
    harness = EvaluationHarness(tmp_path, adapter=FakeEditingAdapter())
    passed, checks = harness._accept(
        tmp_path,
        [],
        final_message="The value is in config.py.",
        answer_contains=case.answer_contains,
    )
    assert passed is True
    assert checks[0]["kind"] == "answer_contains"



def test_plain_read_only_trial_uses_read_only_sandbox(tmp_path: Path):
    class ReadOnlyAdapter(FakeEditingAdapter):
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
            del prompt, cwd, model, effort, timeout_seconds
            self.sandbox_modes.append(sandbox_mode)
            return AdapterResult(
                True,
                "The setting is in config.py",
                usage={"input_tokens": 10, "output_tokens": 5},
            )

    case = BenchmarkCase(
        case_id="search",
        category="search",
        task="find config",
        files={"config.py": "VALUE = 1\n"},
        write_paths=[],
        acceptance=[],
        answer_contains=["config.py"],
    )
    adapter = ReadOnlyAdapter()
    report = EvaluationHarness(tmp_path, adapter=adapter).run(
        [case],
        configs=["plain"],
        repeats=1,
        output_dir=tmp_path / "readonly",
    )
    assert report["trials"][0]["verified_success"] is True
    assert adapter.sandbox_modes == ["read-only"]



def test_cascade_trial_cleans_external_worktree(tmp_path: Path):
    case = BenchmarkCase(
        case_id="cleanup",
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
    harness = EvaluationHarness(
        tmp_path,
        adapter=FakeEditingAdapter(),
    )
    report = harness.run(
        [case],
        configs=["cascade"],
        repeats=1,
        output_dir=tmp_path / "cleanup-report",
    )
    assert len(report["trials"]) == 1
    leftovers = list(tmp_path.glob(".repo.cascade-worktrees/*"))
    assert leftovers == []

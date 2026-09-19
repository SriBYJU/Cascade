from pathlib import Path

from engine.adapters.base import AdapterResult
from engine.runtime import CascadeRuntime
from engine.schemas import ReasoningEffort


class MetricsAdapter:
    name = "metrics"

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
        del model, effort, timeout_seconds, sandbox_mode
        Path(cwd, "value.py").write_text("VALUE = 2\n")
        return AdapterResult(
            True,
            "done",
            events=[
                {
                    "type": "item.completed",
                    "item": {"type": "command_execution"},
                },
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message"},
                },
            ],
            usage={
                "input_tokens": 100,
                "cached_input_tokens": 40,
                "output_tokens": 20,
            },
        )


def test_runtime_records_context_tool_and_agent_metrics(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="fixture"\nversion="0.0.0"\n'
    )
    (repo / "value.py").write_text("VALUE = 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_value.py").write_text(
        "import value\n\n"
        "def test_value():\n"
        "    assert value.VALUE == 2\n"
    )
    import subprocess

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    runtime = CascadeRuntime(repo)
    runtime.codex = MetricsAdapter()
    result = runtime.run(
        "Set VALUE to 2",
        write_paths=["value.py"],
        allowed_paths=["value.py"],
    )
    assert result["status"] == "verified"
    stats = runtime.stats()
    assert stats["agent_calls"] >= 1
    assert stats["tool_calls"] >= 1
    assert stats["context_bytes"] > 0
    assert stats["trajectory_steps"] > 0
    assert stats["cached_input_tokens"] == 40

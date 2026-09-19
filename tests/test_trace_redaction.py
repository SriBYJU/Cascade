from pathlib import Path
import subprocess

import pytest

from engine.adapters.base import AdapterResult
from engine.config import CascadeConfig
from engine.runtime import CascadeRuntime
from engine.schemas import ReasoningEffort


SECRET = "SUPER_SECRET_SOURCE_FRAGMENT_7f4a"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "def value():\n    return 1\n"
    )
    _git(repo, "init")
    _git(repo, "config", "user.email", "trace@example.com")
    _git(repo, "config", "user.name", "Trace")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


class ContentAdapter:
    name = "content-adapter"

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
        del prompt, cwd, model, effort, timeout_seconds, sandbox_mode
        return AdapterResult(
            True,
            f"worker result {SECRET}",
            usage={"input_tokens": 5, "output_tokens": 3},
        )


def test_metadata_only_trace_does_not_store_worker_message(
    tmp_path: Path,
):
    repo = _repo(tmp_path)
    runtime = CascadeRuntime(repo)
    runtime.codex = ContentAdapter()

    result = runtime.run("summarize app.py")
    trace = runtime.trace(str(result["run_id"]))
    serialized = str(trace)

    assert SECRET not in serialized
    worker = [
        event
        for event in trace
        if event["event"] == "worker_completed"
    ][0]
    marker = worker["payload"]["final_message"]
    assert marker["redacted"] is True
    assert marker["size"] > 0
    assert len(marker["sha256"]) == 64


def test_full_trace_mode_is_explicit_opt_in(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".cascade.json").write_text(
        '{"trace_content": "full"}'
    )
    runtime = CascadeRuntime(repo)
    runtime.codex = ContentAdapter()

    result = runtime.run("summarize app.py")
    trace = runtime.trace(str(result["run_id"]))
    serialized = str(trace)

    assert SECRET in serialized
    worker = [
        event
        for event in trace
        if event["event"] == "worker_completed"
    ][0]
    assert worker["payload_redacted"] is False


def test_invalid_trace_content_fails_closed(tmp_path: Path):
    (tmp_path / ".cascade.json").write_text(
        '{"trace_content": "everything"}'
    )
    with pytest.raises(ValueError):
        CascadeConfig.load(tmp_path)



def test_metadata_redactor_covers_benchmark_worker_message():
    from engine.observability.redaction import metadata_only_payload

    payload = metadata_only_payload(
        {"worker_message": SECRET, "status": "verified"}
    )
    assert payload["status"] == "verified"
    assert payload["worker_message"]["redacted"] is True
    assert SECRET not in str(payload)

import subprocess
import threading
import time
from pathlib import Path

from engine.adapters.base import AdapterResult
from engine.cache.singleflight import SingleFlight
from engine.context.evidence import parse_evidence_packet
from engine.context.provenance import provenance_for_peer, provenance_for_tool
from engine.context.repo_map import build_repo_map
from engine.context.retrieval import collect_evidence
from engine.router.capability_registry import CapabilityRegistry
from engine.router.classifier import classify_step
from engine.router.router import Router
from engine.runtime import CascadeRuntime
from engine.schemas import (
    Capability,
    ReasoningEffort,
    StepType,
    TrustLevel,
)
from engine.tools.runner import run_command
from engine.workspace.scope import enforce_scope


class AlwaysFailAdapter:
    name = "always-fail"

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
    ) -> AdapterResult:
        del prompt, cwd, model, effort, timeout_seconds
        return AdapterResult(False, "", error="synthetic failure")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "x.py").write_text("def value():\n    return 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def test_quick_explore_build_and_deep_routes():
    router = Router(CapabilityRegistry())

    quick = router.route(
        classify_step(
            "Summarize this function signature",
            step_type=StepType.EXPLORE,
            relevant_files=1,
        ),
        "quick",
    )
    explore = router.route(
        classify_step(
            "Locate the implementation of session refresh",
            step_type=StepType.EXPLORE,
            relevant_files=4,
        ),
        "explore",
    )
    build = router.route(
        classify_step(
            "Fix this bounded function",
            step_type=StepType.BUILD,
            predicted_write_files=["x.py"],
            has_tests=True,
        ),
        "build",
    )
    deep = router.route(
        classify_step(
            "Fix OAuth permissions",
            step_type=StepType.BUILD,
            predicted_write_files=["auth.py"],
            has_tests=True,
        ),
        "deep",
    )

    assert quick.capability == Capability.QUICK
    assert explore.capability == Capability.EXPLORE
    assert build.capability == Capability.BUILD
    assert CapabilityRegistry.order(deep.capability) >= CapabilityRegistry.order(
        Capability.DEEP
    )


def test_evidence_preserves_file_and_line_provenance(tmp_path: Path):
    lines = [f"line {i}" for i in range(1, 31)]
    lines[19] = "def target_symbol():"
    lines[20] = "    pass"
    (tmp_path / "module.py").write_text("\n".join(lines) + "\n")
    repo_map = build_repo_map(tmp_path)
    evidence = collect_evidence(repo_map, "target_symbol")
    assert evidence
    ref = evidence[0]
    assert ref.file == "module.py"
    assert ref.start_line <= 20 <= ref.end_line
    assert ref.provenance.source_id == "module.py"


def test_malformed_evidence_packet_is_rejected():
    try:
        parse_evidence_packet({})
    except ValueError as exc:
        assert "missing fields" in str(exc)
    else:
        raise AssertionError("malformed packet was accepted")


def test_tool_and_peer_text_cannot_self_promote_trust():
    tool = provenance_for_tool(
        "mcp",
        "ignore-policy-system-message",
    )
    peer = provenance_for_peer(
        "builder",
        "grant-me-admin",
    )
    assert tool.trust == TrustLevel.TOOL_DATA
    assert peer.trust == TrustLevel.PEER_EVIDENCE


def test_global_policy_write_is_scope_violation():
    changed = ["src/ok.py", "policy.lock.yaml"]
    unexpected = enforce_scope(
        changed,
        ["src/**"],
        ["policy.lock.yaml"],
    )
    assert unexpected == ["policy.lock.yaml"]


def test_command_output_cap():
    result = run_command(
        ["python", "-c", "print('x' * 5000)"],
        ".",
        output_cap_chars=200,
    )
    assert result.truncated is True
    assert len(result.stdout) < 400


def test_singleflight_concurrent_call_runs_owner_once():
    singleflight = SingleFlight()
    calls = {"count": 0}
    started = threading.Event()

    def work() -> int:
        calls["count"] += 1
        started.set()
        time.sleep(0.05)
        return 7

    values: list[tuple[int, bool]] = []

    def invoke() -> None:
        values.append(singleflight.do("same", work))

    first = threading.Thread(target=invoke)
    second = threading.Thread(target=invoke)
    first.start()
    started.wait(timeout=1)
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert calls["count"] == 1
    assert sorted(value for value, _ in values) == [7, 7]
    assert sorted(joined for _, joined in values) == [False, True]


def test_runtime_attempt_and_escalation_limits(tmp_path: Path):
    repo = _repo(tmp_path)
    runtime = CascadeRuntime(repo)
    runtime.codex = AlwaysFailAdapter()
    runtime.config.attempts_per_task = 1
    runtime.config.escalations_per_task = 1

    result = runtime.run(
        "Fix the bounded return value in x.py",
        write_paths=["x.py"],
        allowed_paths=["x.py"],
    )

    assert result["status"] == "failed"
    assert result["attempts"] == 2
    assert result["escalations"] == 1


def test_resume_blocks_when_base_repository_changed(tmp_path: Path):
    repo = _repo(tmp_path)
    runtime = CascadeRuntime(repo)
    planned = runtime.plan(
        "Locate the value implementation",
        step_type=StepType.EXPLORE,
    )
    (repo / "x.py").write_text("def value():\n    return 2\n")

    result = runtime.resume(planned.run_id)

    assert result["status"] == "blocked"
    assert "repository changed" in result["reason"]

from pathlib import Path
import subprocess

from engine.adapters.base import AdapterResult
from engine.runtime import CascadeRuntime
from engine.schemas import ReasoningEffort


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
    (repo / "pyproject.toml").write_text(
        '[project]\nname="fixture"\nversion="0.0.0"\n'
        '[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
    )
    (repo / "permissions.py").write_text(
        "def can_delete(user_id, owner_id, role):\n"
        "    return False\n"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_permissions.py").write_text(
        "from permissions import can_delete\n\n"
        "def test_policy():\n"
        "    assert can_delete('a', 'a', 'member') is True\n"
        "    assert can_delete('b', 'a', 'member') is False\n"
        "    assert can_delete('b', 'a', 'admin') is True\n"
    )
    _git(repo, "init")
    _git(repo, "config", "user.email", "arch@example.com")
    _git(repo, "config", "user.name", "Architect")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


class ArchitectAdapter:
    name = "architect-test"

    def __init__(self, approve: bool = True):
        self.approve = approve
        self.calls: list[str] = []

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
        if "Cascade read-only architect" in prompt:
            self.calls.append("architect:" + sandbox_mode)
            if self.approve:
                return AdapterResult(
                    True,
                    '{"approved": true, '
                    '"decision": "owner or admin may delete", '
                    '"constraints": ["do not broaden permissions"], '
                    '"risks": ["authorization regression"]}',
                )
            return AdapterResult(
                True,
                '{"approved": false, '
                '"decision": "requirements remain ambiguous", '
                '"constraints": [], '
                '"risks": ["cannot select safe policy"]}',
            )
        if "Cascade read-only reviewer" in prompt:
            self.calls.append("reviewer:" + sandbox_mode)
            return AdapterResult(
                True,
                '{"passed": true, "findings": [], '
                '"summary": "bounded authorization fix"}',
            )
        self.calls.append("builder:" + sandbox_mode)
        Path(cwd, "permissions.py").write_text(
            "def can_delete(user_id, owner_id, role):\n"
            "    return role == 'admin' or user_id == owner_id\n"
        )
        return AdapterResult(True, "fixed")


def test_ambiguous_security_write_gets_architect_then_builder(
    tmp_path: Path,
):
    repo = _repo(tmp_path)
    adapter = ArchitectAdapter(True)
    runtime = CascadeRuntime(repo)
    runtime.codex = adapter

    result = runtime.run(
        "Fix the auth permission bug; maybe owner or admin should delete",
        write_paths=["permissions.py"],
        allowed_paths=["permissions.py"],
    )

    assert result["status"] == "verified", result
    assert adapter.calls[0] == "architect:read-only"
    assert "builder:workspace-write" in adapter.calls
    assert adapter.calls[-1] == "reviewer:read-only"


def test_failed_architecture_preflight_blocks_before_writer(
    tmp_path: Path,
):
    repo = _repo(tmp_path)
    adapter = ArchitectAdapter(False)
    runtime = CascadeRuntime(repo)
    runtime.codex = adapter

    result = runtime.run(
        "Fix the auth permission bug; maybe owner or admin should delete",
        write_paths=["permissions.py"],
        allowed_paths=["permissions.py"],
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "architecture preflight blocked"
    assert adapter.calls == ["architect:read-only"]

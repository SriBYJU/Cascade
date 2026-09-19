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
        "    return role == 'admin' or user_id != owner_id\n"
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
    _git(repo, "config", "user.email", "review@example.com")
    _git(repo, "config", "user.name", "Review")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


class ReviewAwareAdapter:
    name = "review-aware"

    def __init__(self, reviewer_passes: bool):
        self.reviewer_passes = reviewer_passes
        self.sandboxes: list[str] = []

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
        self.sandboxes.append(sandbox_mode)
        if "Cascade read-only reviewer" in prompt:
            if self.reviewer_passes:
                return AdapterResult(
                    True,
                    '{"passed": true, "findings": [], '
                    '"summary": "authorization logic is bounded"}',
                    usage={"input_tokens": 30, "output_tokens": 10},
                )
            return AdapterResult(
                True,
                '{"passed": false, "findings": ["missing owner check"], '
                '"summary": "material authorization issue remains"}',
                usage={"input_tokens": 30, "output_tokens": 10},
            )
        Path(cwd, "permissions.py").write_text(
            "def can_delete(user_id, owner_id, role):\n"
            "    return role == 'admin' or user_id == owner_id\n"
        )
        return AdapterResult(
            True,
            "fixed",
            usage={"input_tokens": 20, "output_tokens": 5},
        )


def test_high_risk_change_requires_read_only_reviewer(tmp_path: Path):
    repo = _repo(tmp_path)
    adapter = ReviewAwareAdapter(True)
    runtime = CascadeRuntime(repo)
    runtime.codex = adapter

    result = runtime.run(
        "Fix the authorization permission bug in permissions.py",
        write_paths=["permissions.py"],
        allowed_paths=["permissions.py"],
    )

    assert result["status"] == "verified"
    assert result["review"]["passed"] is True
    assert adapter.sandboxes[-1] == "read-only"


def test_failed_high_risk_review_blocks_merge_ready_state(tmp_path: Path):
    repo = _repo(tmp_path)
    adapter = ReviewAwareAdapter(False)
    runtime = CascadeRuntime(repo)
    runtime.codex = adapter

    result = runtime.run(
        "Fix the authorization permission bug in permissions.py",
        write_paths=["permissions.py"],
        allowed_paths=["permissions.py"],
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "required reviewer failed"
    assert result["review"]["passed"] is False

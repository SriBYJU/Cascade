import sys
from pathlib import Path

from engine.tools.runner import run_command
from engine.validation.pipeline import validate_progressively


def test_command_timeout(tmp_path: Path):
    result = run_command(["python", "-c", "import time; time.sleep(1)"], tmp_path, timeout_seconds=0.05)
    assert result.timed_out


def test_command_uses_running_python_when_path_has_no_python(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr("engine.tools.runner.shutil.which", lambda _: None)
    result = run_command(
        ["python", "-c", "print('fallback-ok')"],
        tmp_path,
    )
    assert result.exit_code == 0
    assert result.command[0] == sys.executable
    assert result.stdout.strip() == "fallback-ok"


def test_python_validation_passes(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="0.0.1"\n')
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert 1 == 1\n")
    result = validate_progressively(tmp_path, risk="low", changed_files=["ok.py"])
    assert result.passed


def test_python_validation_fails_syntax(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="0.0.1"\n')
    (tmp_path / "bad.py").write_text("def broken(:\n")
    result = validate_progressively(tmp_path, risk="low", changed_files=["bad.py"])
    assert not result.passed

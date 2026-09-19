from pathlib import Path

from engine.validation.discover import discover_validators


def _commands(root: Path) -> list[tuple[str, ...]]:
    return [spec.command for spec in discover_validators(root)]


def test_minimal_python_project_does_not_inherit_global_ruff_or_mypy(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="fixture"\nversion="0.0.0"\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n"
    )
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda _: "/usr/bin/tool",
    )
    commands = _commands(tmp_path)
    assert ("ruff", "check", ".") not in commands
    assert ("mypy", ".") not in commands
    assert ("python", "-m", "pytest", "-q") in commands


def test_project_config_enables_ruff_and_mypy(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="fixture"\nversion="0.0.0"\n'
        "[tool.ruff]\nline-length=100\n"
        "[tool.mypy]\npython_version='3.11'\n"
    )
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda _: "/usr/bin/tool",
    )
    commands = _commands(tmp_path)
    assert ("ruff", "check", ".") in commands
    assert ("mypy", ".") in commands

import sys
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


def test_python_validators_fall_back_to_running_interpreter(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="fixture"\nversion="0.0.0"\n'
        '[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
    )
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda _: None,
    )

    commands = _commands(tmp_path)
    assert (sys.executable, "-m", "compileall", "-q", ".") in commands
    assert (sys.executable, "-m", "pytest", "-q") in commands


def test_declared_python_tools_use_module_fallback(
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
        lambda _: None,
    )
    monkeypatch.setattr(
        "engine.validation.discover.importlib.util.find_spec",
        lambda name: object() if name in {"ruff", "mypy"} else None,
    )

    commands = _commands(tmp_path)
    assert (sys.executable, "-m", "ruff", "check", ".") in commands
    assert (sys.executable, "-m", "mypy", ".") in commands


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


def test_declared_gradle_project_uses_wrapper_without_guessing_tools(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "build.gradle.kts").write_text(
        'plugins { kotlin("jvm") version "2.0.0" }\n'
    )
    wrapper = "gradlew.bat" if sys.platform.startswith("win") else "gradlew"
    (tmp_path / wrapper).write_text("wrapper")
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda _: None,
    )

    specs = discover_validators(tmp_path)
    by_name = {spec.name: spec for spec in specs}
    command = by_name["jvm-gradle-test"].command
    assert command[-1] == "test"
    assert "gradlew" in command[0]
    assert by_name["jvm-gradle-test"].cwd == "."


def test_declared_maven_project_requires_wrapper_or_installed_tool(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "pom.xml").write_text("<project></project>\n")
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda _: None,
    )
    names = {spec.name for spec in discover_validators(tmp_path)}
    assert "jvm-maven-test" not in names

    wrapper = "mvnw.cmd" if sys.platform.startswith("win") else "mvnw"
    (tmp_path / wrapper).write_text("wrapper")
    specs = discover_validators(tmp_path)
    by_name = {spec.name: spec for spec in specs}
    assert by_name["jvm-maven-test"].command[-1] == "test"


def test_declared_rspec_and_rubocop_use_bundle_exec(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "Gemfile").write_text(
        'gem "rspec"\ngem "rubocop"\n'
    )
    (tmp_path / ".rspec").write_text("--format progress\n")
    (tmp_path / ".rubocop.yml").write_text("AllCops:\n  NewCops: enable\n")
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "bundle" else None,
    )

    specs = discover_validators(tmp_path)
    by_name = {spec.name: spec for spec in specs}
    assert by_name["rspec"].command == ("bundle", "exec", "rspec")
    assert by_name["rubocop"].command == ("bundle", "exec", "rubocop")


def test_ruby_project_without_declared_test_or_lint_does_not_invent_validator(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "Gemfile").write_text('gem "rack"\n')
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )

    names = {spec.name for spec in discover_validators(tmp_path)}
    assert "rspec" not in names
    assert "rake-test" not in names
    assert "rubocop" not in names

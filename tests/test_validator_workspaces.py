import json
from pathlib import Path

from engine.validation.discover import discover_validators
from engine.validation.tests import run_validator


def test_discovers_node_workspace_scripts(monkeypatch, tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"workspaces": ["packages/*"]})
    )
    web = tmp_path / "packages" / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "test": "vitest run",
                    "lint": "eslint .",
                    "typecheck": "tsc --noEmit",
                }
            }
        )
    )
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )

    specs = discover_validators(tmp_path)
    by_name = {spec.name: spec for spec in specs}
    assert by_name["packages/web:js-test"].cwd == "packages/web"
    assert by_name["packages/web:js-lint"].cwd == "packages/web"
    assert by_name["packages/web:js-typecheck"].cwd == "packages/web"


def test_discovers_conventional_nested_python_project(
    monkeypatch,
    tmp_path: Path,
):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text(
        "[project]\nname='backend'\nversion='0.0.0'\n"
        "[tool.pytest.ini_options]\ntestpaths=['tests']\n"
    )
    (backend / "tests").mkdir()
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )

    specs = discover_validators(tmp_path)
    by_name = {spec.name: spec for spec in specs}
    assert by_name["backend:python-compile"].cwd == "backend"
    assert by_name["backend:pytest"].cwd == "backend"


def test_validator_runs_from_declared_subproject_cwd(
    tmp_path: Path,
):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text(
        "[project]\nname='backend'\nversion='0.0.0'\n"
    )
    (backend / "check.py").write_text(
        "from pathlib import Path\n"
        "assert Path('pyproject.toml').exists()\n"
    )

    from engine.validation.discover import ValidatorSpec

    spec = ValidatorSpec(
        "subproject-check",
        ("python", "check.py"),
        "tests",
        "backend",
    )
    result = run_validator(spec, tmp_path)
    assert result.passed is True

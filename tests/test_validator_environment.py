from pathlib import Path

from engine.validation.discover import ValidatorSpec
from engine.validation.tests import _validator_environment, run_validator


def test_validator_environment_omits_common_provider_secrets(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("PATH", "safe-path")

    env = _validator_environment(tmp_path)

    assert env["PATH"] == "safe-path"
    assert "OPENAI_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["HOME"] == str(tmp_path)
    assert env["PYTHONNOUSERSITE"] == "1"


def test_validator_process_does_not_receive_secret_env(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CASCADE_TEST_SECRET_TOKEN", "must-not-leak")
    script = tmp_path / "check_env.py"
    script.write_text(
        "import os\n"
        "assert 'CASCADE_TEST_SECRET_TOKEN' not in os.environ\n"
    )
    spec = ValidatorSpec(
        name="env-check",
        command=("python", "check_env.py"),
        category="tests",
    )

    result = run_validator(spec, tmp_path)

    assert result.passed is True

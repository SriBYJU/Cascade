from pathlib import Path

from engine.doctor import _agent_probe, _codex_exec_probe, _plugin_probe


def test_plugin_probe_accepts_repository_manifests():
    root = Path(__file__).parents[1]
    result = _plugin_probe(root)
    assert result["portable_valid"] is True
    assert result["compat_valid"] is True
    assert result["identity_match"] is True


def test_agent_probe_requires_six_roles():
    root = Path(__file__).parents[1]
    result = _agent_probe(root)
    assert result["required_agents_present"] is True
    assert result["missing_agents"] == []


def test_codex_probe_reports_required_flags(monkeypatch):
    monkeypatch.setattr(
        "engine.doctor.shutil.which",
        lambda _: "/usr/bin/codex",
    )

    class Proc:
        returncode = 0
        stdout = "--json --sandbox --model --config"
        stderr = ""

    monkeypatch.setattr(
        "engine.doctor.subprocess.run",
        lambda *args, **kwargs: Proc(),
    )
    result = _codex_exec_probe()
    assert result["compatible"] is True
    assert all(result["flags"].values())


def test_codex_probe_fails_closed_on_missing_flag(monkeypatch):
    monkeypatch.setattr(
        "engine.doctor.shutil.which",
        lambda _: "/usr/bin/codex",
    )

    class Proc:
        returncode = 0
        stdout = "--json --model --config"
        stderr = ""

    monkeypatch.setattr(
        "engine.doctor.subprocess.run",
        lambda *args, **kwargs: Proc(),
    )
    result = _codex_exec_probe()
    assert result["compatible"] is False
    assert result["flags"]["sandbox"] is False

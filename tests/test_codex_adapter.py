from types import SimpleNamespace

from engine.adapters.codex import CodexAdapter
from engine.schemas import ReasoningEffort


def test_codex_builder_uses_explicit_workspace_write(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.adapters.codex.shutil.which",
        lambda _: "/usr/bin/codex",
    )

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"turn.completed","usage":'
                '{"input_tokens":10,"cached_input_tokens":4,'
                '"output_tokens":2,"reasoning_output_tokens":1}}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "engine.adapters.codex.subprocess.run",
        fake_run,
    )
    result = CodexAdapter().run(
        "edit the file",
        cwd=".",
        effort=ReasoningEffort.MEDIUM,
        sandbox_mode="workspace-write",
    )
    command = captured["command"]
    assert isinstance(command, list)
    assert command[:5] == [
        "codex",
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
    ]
    assert result.ok is True
    assert result.usage["cached_input_tokens"] == 4


def test_codex_rejects_danger_full_access(monkeypatch):
    monkeypatch.setattr(
        "engine.adapters.codex.shutil.which",
        lambda _: "/usr/bin/codex",
    )
    result = CodexAdapter().run(
        "do work",
        cwd=".",
        sandbox_mode="danger-full-access",
    )
    assert result.ok is False
    assert "unsupported" in (result.error or "")


def test_codex_release_mode_is_ephemeral_and_ignores_user_config(
    monkeypatch,
):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.adapters.codex.shutil.which",
        lambda _: "/usr/bin/codex",
    )

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "engine.adapters.codex.subprocess.run",
        fake_run,
    )
    result = CodexAdapter(
        ephemeral=True,
        ignore_user_config=True,
    ).run("measure this", cwd=".")

    command = captured["command"]
    assert isinstance(command, list)
    assert command[:4] == [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
    ]
    assert result.ok is True

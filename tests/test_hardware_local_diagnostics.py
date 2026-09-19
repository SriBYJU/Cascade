from engine.adapters.hardware import detect_hardware
from engine.adapters.ollama import OllamaAdapter
from engine.adapters.vllm import VLLMAdapter


def test_hardware_probe_is_cross_platform_and_nonfatal():
    info = detect_hardware()
    assert info.cpu_count >= 1
    assert info.system
    assert info.machine


def test_local_adapter_diagnostics_declare_no_filesystem_tools(
    monkeypatch,
):
    ollama = OllamaAdapter()
    monkeypatch.setattr(ollama, "available", lambda: True)
    monkeypatch.setattr(ollama, "models", lambda: ["local-a"])
    monkeypatch.setattr(
        ollama,
        "model_context_length",
        lambda model: 8192,
    )
    diag = ollama.diagnostics()
    assert diag["models"][0]["context_length"] == 8192
    assert diag["filesystem_tools"] is False
    assert diag["sandbox_enforced"] is False

    vllm = VLLMAdapter()
    monkeypatch.setattr(vllm, "available", lambda: True)
    monkeypatch.setattr(
        vllm,
        "_models_payload",
        lambda: [{"id": "local-b", "max_model_len": 16384}],
    )
    diag2 = vllm.diagnostics()
    assert diag2["models"][0]["context_length"] == 16384
    assert diag2["filesystem_tools"] is False

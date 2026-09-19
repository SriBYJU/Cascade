from __future__ import annotations

import platform, shutil, subprocess
from pathlib import Path
from typing import Any
from .adapters.codex import CodexAdapter
from .adapters.hardware import detect_hardware
from .adapters.ollama import OllamaAdapter
from .adapters.vllm import VLLMAdapter
from .validation.discover import discover_validators

def _version(command:list[str])->str|None:
    if not shutil.which(command[0]): return None
    try: p=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,check=False)
    except OSError: return None
    return (p.stdout or p.stderr).strip().splitlines()[0] if p.returncode==0 else None

def doctor(repo_root:str|Path=".")->dict[str,Any]:
    root=Path(repo_root).resolve(); codex=CodexAdapter(); ollama=OllamaAdapter(); vllm=VLLMAdapter()
    return {"repo_root":str(root),"python":platform.python_version(),"git":_version(["git","--version"]),"codex":codex.version(),"codex_available":codex.available(),"ollama_available":ollama.available(),"ollama_models":ollama.models() if ollama.available() else [],"vllm_available":vllm.available(),"vllm_models":vllm.models() if vllm.available() else [],"hardware":detect_hardware().to_dict(),"validators":[{"name":v.name,"command":list(v.command),"category":v.category} for v in discover_validators(root)],"project_codex_config":str(root/".codex"/"config.toml") if (root/".codex"/"config.toml").exists() else None,"plugin_manifest":str(root/".codex-plugin"/"plugin.json") if (root/".codex-plugin"/"plugin.json").exists() else None}

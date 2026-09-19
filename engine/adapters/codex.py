from __future__ import annotations
import json,shutil,subprocess
from .base import AdapterResult
from ..schemas import ReasoningEffort
class CodexAdapter:
    name="codex"
    def available(self)->bool: return shutil.which("codex") is not None
    def version(self)->str|None:
        if not self.available(): return None
        proc=subprocess.run(["codex","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=False)
        return (proc.stdout or proc.stderr).strip() if proc.returncode==0 else None
    def run(self,prompt:str,*,cwd:str,model:str="auto",effort:ReasoningEffort=ReasoningEffort.MEDIUM,timeout_seconds:int=900)->AdapterResult:
        if not self.available(): return AdapterResult(False,"",error="codex CLI is not installed")
        command=["codex","exec","--json"]
        if model and model!="auto": command.extend(["--model",model])
        command.extend(["--config",f'model_reasoning_effort="{effort.value}"']); command.append(prompt)
        try: proc=subprocess.run(command,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout_seconds,check=False)
        except subprocess.TimeoutExpired: return AdapterResult(False,"",error=f"codex timed out after {timeout_seconds}s")
        events=[]; final=""; usage={}
        for line in (proc.stdout or "").splitlines():
            try: event=json.loads(line)
            except json.JSONDecodeError: continue
            events.append(event)
            if event.get("type")=="item.completed" and event.get("item",{}).get("type")=="agent_message": final=event["item"].get("text",final)
            if event.get("type")=="turn.completed" and isinstance(event.get("usage"),dict): usage={k:int(v) for k,v in event["usage"].items() if isinstance(v,int)}
        error=None if proc.returncode==0 else (proc.stderr or "codex execution failed").strip()
        return AdapterResult(proc.returncode==0,final,events=events,usage=usage,error=error)

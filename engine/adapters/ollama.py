from __future__ import annotations
import json,urllib.error,urllib.request
from .base import AdapterResult
from ..schemas import ReasoningEffort
class OllamaAdapter:
    name="ollama"
    def __init__(self,base_url:str="http://127.0.0.1:11434"): self.base_url=base_url.rstrip("/")
    def available(self)->bool:
        try:
            with urllib.request.urlopen(self.base_url+"/api/tags",timeout=1.0) as r: return r.status==200
        except (OSError,urllib.error.URLError): return False
    def models(self)->list[str]:
        if not self.available(): return []
        with urllib.request.urlopen(self.base_url+"/api/tags",timeout=2.0) as r: data=json.loads(r.read().decode())
        return [m.get("name","") for m in data.get("models",[]) if m.get("name")]
    def run(self,prompt:str,*,cwd:str,model:str="auto",effort:ReasoningEffort=ReasoningEffort.MEDIUM,timeout_seconds:int=900)->AdapterResult:
        if model=="auto":
            models=self.models()
            if not models: return AdapterResult(False,"",error="no Ollama model is available")
            model=models[0]
        payload=json.dumps({"model":model,"prompt":prompt,"stream":False}).encode(); req=urllib.request.Request(self.base_url+"/api/generate",data=payload,headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=timeout_seconds) as r: data=json.loads(r.read().decode())
            return AdapterResult(True,data.get("response",""),usage={"input_tokens":int(data.get("prompt_eval_count",0)),"output_tokens":int(data.get("eval_count",0))})
        except (OSError,urllib.error.URLError,json.JSONDecodeError) as exc: return AdapterResult(False,"",error=str(exc))

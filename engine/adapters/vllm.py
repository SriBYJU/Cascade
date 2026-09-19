from __future__ import annotations
import json,urllib.error,urllib.request
from .base import AdapterResult
from ..schemas import ReasoningEffort
class VLLMAdapter:
    name="vllm"
    def __init__(self,base_url:str="http://127.0.0.1:8000/v1"): self.base_url=base_url.rstrip("/")
    def available(self)->bool:
        try:
            with urllib.request.urlopen(self.base_url+"/models",timeout=1.0) as r: return r.status==200
        except (OSError,urllib.error.URLError): return False
    def models(self)->list[str]:
        if not self.available(): return []
        with urllib.request.urlopen(self.base_url+"/models",timeout=2.0) as r: data=json.loads(r.read().decode())
        return [m.get("id","") for m in data.get("data",[]) if m.get("id")]
    def run(self,prompt:str,*,cwd:str,model:str="auto",effort:ReasoningEffort=ReasoningEffort.MEDIUM,timeout_seconds:int=900)->AdapterResult:
        models=self.models(); model=models[0] if model=="auto" and models else model
        if not model or model=="auto": return AdapterResult(False,"",error="no vLLM model is available")
        payload=json.dumps({"model":model,"input":prompt}).encode(); req=urllib.request.Request(self.base_url+"/responses",data=payload,headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=timeout_seconds) as r: data=json.loads(r.read().decode())
            usage=data.get("usage",{}) if isinstance(data.get("usage"),dict) else {}
            return AdapterResult(True,data.get("output_text",""),usage={k:int(v) for k,v in usage.items() if isinstance(v,int)})
        except (OSError,urllib.error.URLError,json.JSONDecodeError) as exc: return AdapterResult(False,"",error=str(exc))

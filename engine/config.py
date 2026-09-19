from __future__ import annotations

import json, os
from dataclasses import dataclass, field
from pathlib import Path
from .schemas import Capability

@dataclass(slots=True)
class CascadeConfig:
    repo_root:Path; state_dir:Path; db_path:Path; max_concurrent_workers:int=3; attempts_per_task:int=2; escalations_per_task:int=2; command_timeout_seconds:int=120; output_cap_chars:int=20000; head_token_budget:int=50000; total_token_budget:int=150000; context_token_budget:int=30000; capability_map:dict[Capability,str]=field(default_factory=dict); local_mode:bool=False; cloud_fallback:bool=True; trace_content:str="metadata_only"
    @classmethod
    def load(cls,repo_root:str|Path=".")->"CascadeConfig":
        root=Path(repo_root).resolve(); state_dir=root/".cascade"; state_dir.mkdir(parents=True,exist_ok=True); mapping={}
        for cap in Capability:
            env=os.getenv(f"CASCADE_MODEL_{cap.value.upper().replace('-','_')}")
            if env: mapping[cap]=env
        cfg=cls(repo_root=root,state_dir=state_dir,db_path=state_dir/"cascade.sqlite3",max_concurrent_workers=int(os.getenv("CASCADE_MAX_WORKERS","3")),capability_map=mapping,local_mode=os.getenv("CASCADE_LOCAL_MODE","0")=="1",cloud_fallback=os.getenv("CASCADE_CLOUD_FALLBACK","1")=="1")
        p=root/".cascade.json"
        if p.exists():
            data=json.loads(p.read_text())
            for key in ("max_concurrent_workers","attempts_per_task","escalations_per_task","command_timeout_seconds","output_cap_chars","head_token_budget","total_token_budget","context_token_budget","local_mode","cloud_fallback","trace_content"):
                if key in data: setattr(cfg,key,data[key])
            for key,value in data.get("capability_map",{}).items(): cfg.capability_map[Capability(key)]=value
        return cfg

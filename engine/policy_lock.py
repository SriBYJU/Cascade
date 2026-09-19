from __future__ import annotations
import hashlib,json
from pathlib import Path
from .schemas import PolicyLock

def load_policy(path:str|Path)->PolicyLock: return PolicyLock.model_validate(json.loads(Path(path).read_text()))
def policy_digest(policy:PolicyLock)->str:
    raw=json.dumps(policy.model_dump(mode="json"),sort_keys=True,separators=(",",":")); return hashlib.sha256(raw.encode()).hexdigest()
def write_proposal(policy:PolicyLock,path:str|Path)->None: Path(path).write_text(json.dumps(policy.model_dump(mode="json"),indent=2,sort_keys=True)+"\n")

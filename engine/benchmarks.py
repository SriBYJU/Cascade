from __future__ import annotations

import json,time
from pathlib import Path
from typing import Any, cast
from .router.capability_registry import CapabilityRegistry
from .router.classifier import classify_step
from .router.policy import minimum_capability
from .schemas import Capability,StepType

class BenchmarkRunner:
    def __init__(self,repo_root:str|Path): self.repo_root=Path(repo_root).resolve(); self.registry=CapabilityRegistry()
    def _fixtures(self)->list[dict[str,Any]]: return cast(list[dict[str,Any]], json.loads((self.repo_root/"benchmarks"/"fixtures"/"micro_tasks.json").read_text()))
    def run_micro(self)->dict[str,Any]:
        started=time.time(); results=[]; failures=0; order=[c.value for c in Capability]
        for item in self._fixtures():
            features=classify_step(item["task"],step_type=StepType(item["step_type"]),predicted_write_files=item.get("write",[]),has_tests=bool(item.get("has_tests")),has_strong_validation=bool(item.get("strong_validation",item.get("has_tests"))))
            floor=minimum_capability(features); expected=Capability(item["expected_min"]); passed=order.index(floor.value)>=order.index(expected.value); failures+=int(not passed)
            results.append({"id":item["id"],"category":item["category"],"expected_min":expected.value,"actual_min":floor.value,"risk":features.risk.value,"passed":passed})
        return {"suite":"micro-routing-v1","measured":True,"scope":"deterministic router-policy acceptance only; no model quality/cost claim","results":results,"summary":{"tasks":len(results),"failures":failures,"passed":len(results)-failures,"duration_ms":int((time.time()-started)*1000)}}

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from ..state.db import StateDB
@dataclass(frozen=True,slots=True)
class EvidenceSummary: task_class:str; capability:str; samples:int; success_rate:float
class AdmittedEvidenceStore:
    TRUSTED_EVALUATORS={"tests","benchmark-ground-truth","human-accept","human-reject","approved-objective"}
    def __init__(self,db:StateDB): self.db=db
    def admit(self,task_class:str,capability:str,success:bool,evaluator:str,metrics:dict[str,Any])->None:
        if evaluator not in self.TRUSTED_EVALUATORS: raise ValueError(f"untrusted evaluator: {evaluator}")
        self.db.execute("INSERT INTO admitted_evidence(task_class,capability,success,evaluator,metrics_json) VALUES(?,?,?,?,?)",(task_class,capability,int(success),evaluator,self.db.dumps(metrics)))
    def summaries(self)->list[EvidenceSummary]:
        rows=self.db.query("SELECT task_class,capability,COUNT(*) samples,AVG(success) success_rate FROM admitted_evidence GROUP BY task_class,capability")
        return [EvidenceSummary(r["task_class"],r["capability"],r["samples"],float(r["success_rate"])) for r in rows]
    def propose(self,minimum_samples:int=20,success_floor:float=0.95)->dict[str,str]:
        by_task=defaultdict(list)
        for item in self.summaries(): by_task[item.task_class].append(item)
        proposal={}; order=["quick","explore","build","debug","deep","critical"]
        for task,items in by_task.items():
            eligible=[i for i in items if i.samples>=minimum_samples and i.success_rate>=success_floor]
            if eligible: proposal[task]=min(eligible,key=lambda i:order.index(i.capability) if i.capability in order else 99).capability
        return proposal

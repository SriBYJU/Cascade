from __future__ import annotations
import re
from collections.abc import Iterable
from ..schemas import RiskLevel,RouteFeatures,StepType
SECURITY_TERMS={"auth","oauth","permission","permissions","secret","token","password","encryption","security","payment","billing","credential","rbac","acl"}
CRITICAL_TERMS={"production","delete data","drop table","rotate key","deploy","destructive"}
AMBIGUITY_TERMS={"maybe","perhaps","unclear","choose","design","architecture","tradeoff"}
DETERMINISTIC_TERMS={"grep","find exact","search exact","run tests","run lint","typecheck","format","git status","git diff","parse json","validate yaml","validate toml"}
def classify_step(task_text:str,*,step_type:StepType|None=None,predicted_write_files:Iterable[str]=(),relevant_files:int=0,has_tests:bool=False,has_strong_validation:bool=False,prompt_cache_affinity:float=0.0,remaining_budget_ratio:float=1.0,quota_pressure:float=0.0)->RouteFeatures:
    text=task_text.lower(); writes=list(predicted_write_files)
    if step_type is None:
        if any(k in text for k in {"debug","failing test","traceback","race condition"}): step_type=StepType.DEBUG
        elif any(k in text for k in {"verify","test","lint","typecheck","check"}): step_type=StepType.VERIFY
        elif any(k in text for k in {"architecture","design","policy conflict"}): step_type=StepType.CRITICAL
        elif any(k in text for k in {"find","locate","map","explore","where is"}): step_type=StepType.EXPLORE
        elif any(k in text for k in {"merge","integrate","rebase"}): step_type=StepType.INTEGRATE
        else: step_type=StepType.BUILD if writes or re.search(r"\b(add|fix|change|implement|refactor|update)\b",text) else StepType.EXPLORE
    security=any(t in text for t in SECURITY_TERMS); critical=any(t in text for t in CRITICAL_TERMS); data_migration=any(t in text for t in {"migration","schema","database migration","alter table"}); ambiguity=any(t in text for t in AMBIGUITY_TERMS) or " or " in text; deterministic=any(t in text for t in DETERMINISTIC_TERMS) or step_type==StepType.VERIFY; write_intent=step_type in {StepType.BUILD,StepType.DEBUG,StepType.INTEGRATE,StepType.TRANSFORM} or bool(writes)
    if critical or step_type==StepType.CRITICAL: risk=RiskLevel.CRITICAL
    elif security or data_migration: risk=RiskLevel.HIGH
    elif len(writes)>3 or relevant_files>8 or ambiguity: risk=RiskLevel.MEDIUM
    else: risk=RiskLevel.LOW
    return RouteFeatures(step_type=step_type,task_text=task_text,risk=risk,write_intent=write_intent,relevant_files=relevant_files,predicted_write_files=writes,has_strong_validation=has_strong_validation,has_tests=has_tests,security_sensitive=security,data_migration=data_migration,ambiguity=ambiguity,deterministic_candidate=deterministic,prompt_cache_affinity=prompt_cache_affinity,remaining_budget_ratio=remaining_budget_ratio,quota_pressure=quota_pressure)

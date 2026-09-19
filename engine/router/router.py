from __future__ import annotations
import uuid
from ..schemas import BudgetReservation,Capability,RouteDecision,RouteFeatures
from ..scheduler.budgets import BudgetManager
from .capability_registry import CapabilityRegistry
from .policy import choose_effort,minimum_capability
from .scorer import route_score
class Router:
    def __init__(self,registry:CapabilityRegistry,budget_manager:BudgetManager|None=None): self.registry=registry; self.budget_manager=budget_manager
    def route(self,features:RouteFeatures,task_id:str|None=None)->RouteDecision:
        task_id=task_id or f"task-{uuid.uuid4().hex[:10]}"; floor=minimum_capability(features)
        if floor==Capability.NO_MODEL:
            profile=self.registry.resolve(Capability.NO_MODEL); reservation=BudgetReservation(tokens=0,attempts=1)
            return RouteDecision(task_id=task_id,step_type=features.step_type,capability=Capability.NO_MODEL,reasoning_effort=choose_effort(Capability.NO_MODEL,features),model_target=profile.model_id,cache_affinity=features.prompt_cache_affinity,risk=features.risk,budget_reserved=reservation,utility=1.0,why=["deterministic mechanism can prove this verification step"],escalation_if=["deterministic validator is unavailable or inconclusive"])
        utility,profile=max([(route_score(p,features),p) for p in self.registry.available(floor)],key=lambda x:x[0]); estimated={Capability.QUICK:2500,Capability.EXPLORE:4000,Capability.BUILD:8000,Capability.DEBUG:10000,Capability.DEEP:14000,Capability.CRITICAL:18000}.get(profile.capability,0); reservation=BudgetReservation(tokens=estimated,attempts=1,head_tokens=estimated if profile.capability==Capability.CRITICAL else 0,context_tokens=min(features.context_tokens_estimate,12000))
        if self.budget_manager: self.budget_manager.reserve(task_id,reservation)
        why=[f"minimum safe capability={floor.value}",f"selected {profile.capability.value} with utility={utility:.3f}"]
        if features.has_strong_validation: why.append("strong deterministic validation lowers retry risk")
        if features.prompt_cache_affinity>0.5: why.append("warm prompt-cache affinity favored staying near current route")
        if features.security_sensitive: why.append("security-sensitive task raised the capability floor")
        if features.ambiguity: why.append("requirement ambiguity increased reasoning demand")
        return RouteDecision(task_id=task_id,step_type=features.step_type,capability=profile.capability,reasoning_effort=choose_effort(profile.capability,features),model_target=profile.model_id,cache_affinity=features.prompt_cache_affinity,risk=features.risk,budget_reserved=reservation,utility=utility,why=why,escalation_if=["required validator fails twice","scope expands materially","new high-risk evidence appears"])

from __future__ import annotations
import os
from collections.abc import Iterable
from ..schemas import Capability,ModelProfile,ReasoningEffort
_CAPABILITY_ORDER=[Capability.NO_MODEL,Capability.QUICK,Capability.EXPLORE,Capability.BUILD,Capability.DEBUG,Capability.DEEP,Capability.CRITICAL]
_DEFAULT_COST_WEIGHT={Capability.NO_MODEL:0.0,Capability.QUICK:0.20,Capability.EXPLORE:0.25,Capability.BUILD:0.50,Capability.DEBUG:0.70,Capability.DEEP:0.85,Capability.CRITICAL:1.00}
class CapabilityRegistry:
    def __init__(self,overrides:dict[Capability,str]|None=None): self.overrides=overrides or {}; self._profiles=self._build_profiles()
    def _build_profiles(self)->dict[Capability,ModelProfile]:
        profiles={}
        for cap in _CAPABILITY_ORDER:
            if cap==Capability.NO_MODEL:
                profiles[cap]=ModelProfile(model_id="deterministic",capability=cap,reasoning_efforts=[ReasoningEffort.MINIMAL],local=True,cost_weight=0.0001,latency_weight=0.1); continue
            model=self.overrides.get(cap) or os.getenv(f"CASCADE_MODEL_{cap.value.upper().replace('-','_')}") or "auto"
            if cap in {Capability.QUICK,Capability.EXPLORE}: efforts=[ReasoningEffort.LOW,ReasoningEffort.MEDIUM]
            elif cap==Capability.BUILD: efforts=[ReasoningEffort.LOW,ReasoningEffort.MEDIUM,ReasoningEffort.HIGH]
            else: efforts=[ReasoningEffort.MEDIUM,ReasoningEffort.HIGH,ReasoningEffort.XHIGH,ReasoningEffort.MAX]
            profiles[cap]=ModelProfile(model_id=model,capability=cap,reasoning_efforts=efforts,cost_weight=_DEFAULT_COST_WEIGHT[cap],latency_weight=0.5+_CAPABILITY_ORDER.index(cap)*0.15)
        return profiles
    def resolve(self,capability:Capability)->ModelProfile: return self._profiles[capability]
    def available(self,minimum:Capability=Capability.QUICK)->list[ModelProfile]:
        start=_CAPABILITY_ORDER.index(minimum); return [self._profiles[c] for c in _CAPABILITY_ORDER[start:] if self._profiles[c].available]
    def all(self)->Iterable[ModelProfile]: return self._profiles.values()
    @staticmethod
    def order(capability:Capability)->int: return _CAPABILITY_ORDER.index(capability)

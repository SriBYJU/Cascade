from __future__ import annotations
from dataclasses import dataclass
from ..schemas import ModelProfile,RouteFeatures
from .capability_registry import CapabilityRegistry
@dataclass(frozen=True,slots=True)
class ScoreWeights: cost:float=0.35; latency:float=0.12; context:float=0.08; quota:float=0.10; retry:float=0.20; risk:float=0.25; cache:float=0.12; local:float=0.05
def expected_success(profile:ModelProfile,features:RouteFeatures)->float:
    strength=CapabilityRegistry.order(profile.capability)/6.0; base=0.55+0.40*strength
    if features.has_strong_validation: base+=0.04
    if features.ambiguity: base-=max(0.0,0.12-0.10*strength)
    if features.security_sensitive: base-=max(0.0,0.15-0.12*strength)
    hist=features.historical_success.get(profile.capability.value)
    if hist is not None: base=0.65*base+0.35*hist
    return max(0.01,min(0.995,base))
def route_score(profile:ModelProfile,features:RouteFeatures,weights:ScoreWeights|None=None)->float:
    w=weights or ScoreWeights(); success=expected_success(profile,features); context_norm=min(1.0,features.context_tokens_estimate/30000.0); retry_risk=1.0-success; risk_exposure=(1.0-success)*{"low":0.2,"medium":0.5,"high":0.8,"critical":1.0}[features.risk.value]
    return success-w.cost*profile.cost_weight-w.latency*profile.latency_weight/2.0-w.context*context_norm-w.quota*features.quota_pressure-w.retry*retry_risk-w.risk*risk_exposure+w.cache*features.prompt_cache_affinity+w.local*(1.0 if profile.local else 0.0)

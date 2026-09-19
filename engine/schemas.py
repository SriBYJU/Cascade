from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

class Capability(str, Enum):
    NO_MODEL="no-model"; QUICK="quick"; EXPLORE="explore"; BUILD="build"; DEBUG="debug"; DEEP="deep"; CRITICAL="critical"

class ReasoningEffort(str, Enum):
    MINIMAL="minimal"; LOW="low"; MEDIUM="medium"; HIGH="high"; XHIGH="xhigh"; MAX="max"

class RiskLevel(str, Enum):
    LOW="low"; MEDIUM="medium"; HIGH="high"; CRITICAL="critical"

class StepType(str, Enum):
    EXPLORE="explore"; TRANSFORM="transform"; BUILD="build"; DEBUG="debug"; VERIFY="verify"; INTEGRATE="integrate"; CRITICAL="critical"

class TrustLevel(str, Enum):
    TRUSTED_POLICY="trusted-policy"; PROJECT_INSTRUCTION="project-instruction"; UNTRUSTED_DATA="untrusted-data"; TOOL_DATA="tool-data"; PEER_EVIDENCE="peer-evidence"

class ToolRisk(str, Enum):
    READ_ONLY="read-only"; LOCAL_WRITE="local-write"; REPO_WRITE="repo-write"; NETWORK_READ="network-read"; NETWORK_WRITE="network-write"; EXTERNAL_SIDE_EFFECT="external-side-effect"; DESTRUCTIVE="destructive"; SECRET_ACCESS="secret-access"

class Provenance(StrictModel):
    source_type:str; source_id:str; trust:TrustLevel; scope:str|None=None

class EvidenceRef(StrictModel):
    file:str; start_line:int=Field(ge=1); end_line:int=Field(ge=1); claim:str; provenance:Provenance
    @field_validator("end_line")
    @classmethod
    def validate_line_order(cls,value:int,info:Any)->int:
        start=info.data.get("start_line")
        if start is not None and value<start: raise ValueError("end_line must be >= start_line")
        return value

class BudgetReservation(StrictModel):
    tokens:int=Field(default=0,ge=0); attempts:int=Field(default=1,ge=1); head_tokens:int=Field(default=0,ge=0); context_tokens:int=Field(default=0,ge=0); wall_time_seconds:float=Field(default=0,ge=0)

class TaskEnvelope(StrictModel):
    task_id:str; role:str; goal:str; allowed_paths:list[str]=Field(default_factory=lambda:["**"]); forbidden_paths:list[str]=Field(default_factory=list); evidence:list[EvidenceRef]=Field(default_factory=list); constraints:list[str]=Field(default_factory=list); done_when:list[str]=Field(default_factory=list); capability:Capability=Capability.BUILD; max_attempts:int=Field(default=2,ge=1,le=10); max_context_tokens:int=Field(default=12000,ge=256); escalation:Capability|None=Capability.DEBUG; summary_chars:int=Field(default=1200,ge=100,le=20000)

class EvidencePacket(StrictModel):
    status:str; changed_files:list[str]=Field(default_factory=list); validation:dict[str,Any]=Field(default_factory=dict); evidence:list[EvidenceRef]=Field(default_factory=list); risk:RiskLevel=RiskLevel.LOW; unresolved:list[str]=Field(default_factory=list); summary:str=""; scope_deviation:list[str]=Field(default_factory=list); escalation_request:str|None=None

class RouteFeatures(StrictModel):
    step_type:StepType; task_text:str; risk:RiskLevel=RiskLevel.LOW; write_intent:bool=False; relevant_files:int=Field(default=0,ge=0); predicted_write_files:list[str]=Field(default_factory=list); has_strong_validation:bool=False; has_tests:bool=False; security_sensitive:bool=False; data_migration:bool=False; ambiguity:bool=False; deterministic_candidate:bool=False; prompt_cache_affinity:float=Field(default=0.0,ge=0.0,le=1.0); prompt_cache_affinity_by_model:dict[str,float]=Field(default_factory=dict); remaining_budget_ratio:float=Field(default=1.0,ge=0.0,le=1.0); quota_pressure:float=Field(default=0.0,ge=0.0,le=1.0); context_tokens_estimate:int=Field(default=0,ge=0); historical_success:dict[str,float]=Field(default_factory=dict)

class RouteDecision(StrictModel):
    task_id:str; step_type:StepType; capability:Capability; reasoning_effort:ReasoningEffort; model_target:str; cache_affinity:float=Field(default=0.0,ge=0.0,le=1.0); risk:RiskLevel; budget_reserved:BudgetReservation; utility:float=0.0; why:list[str]=Field(default_factory=list); escalation_if:list[str]=Field(default_factory=list)

class ValidationCheck(StrictModel):
    name:str; command:list[str]=Field(default_factory=list); passed:bool; exit_code:int|None=None; duration_ms:int=Field(default=0,ge=0); stdout:str=""; stderr:str=""; timed_out:bool=False

class ValidationResult(StrictModel):
    passed:bool; risk:RiskLevel; checks:list[ValidationCheck]=Field(default_factory=list); changed_files:list[str]=Field(default_factory=list); unexpected_files:list[str]=Field(default_factory=list); unresolved_high_severity:list[str]=Field(default_factory=list)

class ReviewDecision(StrictModel):
    passed:bool; findings:list[str]=Field(default_factory=list); summary:str=""

class ArchitectureDecision(StrictModel):
    approved:bool; decision:str; constraints:list[str]=Field(default_factory=list); risks:list[str]=Field(default_factory=list)

class Event(StrictModel):
    run_id:str; task_id:str; attempt_id:int=Field(default=1,ge=0); event:str; ts:str=Field(default_factory=lambda:datetime.now(timezone.utc).isoformat()); actor:str; provenance:Provenance|None=None; metrics:dict[str,float|int]=Field(default_factory=dict); payload:dict[str,Any]=Field(default_factory=dict); payload_redacted:bool=True

class PolicyCertificate(StrictModel):
    benchmark_suite:str; quality_delta:float|None=None; weighted_usage_delta:float|None=None
class PolicyRoute(StrictModel):
    target:Capability; effort:ReasoningEffort
class PolicyLock(StrictModel):
    version:int=Field(ge=1); base_evidence_snapshot:str; routes:dict[str,PolicyRoute]; guards:dict[str,Capability]=Field(default_factory=dict); certificate:PolicyCertificate; status:str="active"; note:str|None=None
class CommandResult(StrictModel):
    command:list[str]; cwd:str; exit_code:int|None; stdout:str; stderr:str; duration_ms:int=Field(ge=0); timed_out:bool=False; truncated:bool=False
class RepoFile(StrictModel):
    path:str; language:str; size_bytes:int=Field(ge=0); lines:int=Field(ge=0); symbols:list[str]=Field(default_factory=list); imports:list[str]=Field(default_factory=list); package:str|None=None; references:list[str]=Field(default_factory=list); referenced_by:list[str]=Field(default_factory=list); test_targets:list[str]=Field(default_factory=list); git_recency:float=0.0; is_test:bool=False; is_entry_point:bool=False; risk_tags:list[str]=Field(default_factory=list)
class RepoMap(StrictModel):
    root:str; fingerprint:str; generated_at:str=Field(default_factory=lambda:datetime.now(timezone.utc).isoformat()); files:list[RepoFile]=Field(default_factory=list)
class ModelProfile(StrictModel):
    model_id:str; capability:Capability; reasoning_efforts:list[ReasoningEffort]; local:bool=False; available:bool=True; cost_weight:float=Field(default=1.0,gt=0); latency_weight:float=Field(default=1.0,gt=0)
class RunSummary(StrictModel):
    run_id:str; verified_success:bool; head_input_tokens:int=0; head_output_tokens:int=0; worker_input_tokens:int=0; worker_output_tokens:int=0; cached_input_tokens:int=0; weighted_usage:float=0.0; context_bytes:int=0; wall_time_ms:int=0; retries:int=0; escalations:int=0; tool_calls:int=0; agent_calls:int=0

def normalize_repo_path(path:str|Path)->str:
    raw = Path(path).as_posix()
    while raw.startswith("./"):
        raw = raw[2:]
    return raw

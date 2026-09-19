"""Optional direct OpenAI Responses adapter boundary."""
from __future__ import annotations
import os
from .base import AdapterResult
from ..schemas import ReasoningEffort
class OpenAIAdapter:
    name="openai"
    def available(self)->bool: return bool(os.getenv("OPENAI_API_KEY"))
    def run(self,prompt:str,*,cwd:str,model:str="auto",effort:ReasoningEffort=ReasoningEffort.MEDIUM,timeout_seconds:int=900,sandbox_mode:str="read-only")->AdapterResult:
        return AdapterResult(False,"",error="direct OpenAI adapter is optional and not enabled in the Codex-native v0.1 path")

from pathlib import Path

from engine.config import CascadeConfig
from engine.context.repo_map import build_repo_map
from engine.context.retrieval import collect_broad_evidence, collect_evidence


def test_ablation_flags_default_on(tmp_path: Path):
    cfg = CascadeConfig.load(tmp_path)
    assert cfg.enable_context_firewall is True
    assert cfg.enable_prompt_cache_affinity is True
    assert cfg.enable_parallel_dag is True


def test_broad_context_moves_more_repository_evidence(tmp_path: Path):
    (tmp_path / "target.py").write_text("def target():\n    return 1\n")
    (tmp_path / "unrelated.py").write_text("def unrelated():\n    return 2\n")
    repo_map = build_repo_map(tmp_path)
    narrow = collect_evidence(repo_map, "target")
    broad = collect_broad_evidence(repo_map, "target")
    assert {ref.file for ref in narrow} == {"target.py"}
    assert {ref.file for ref in broad} >= {"target.py", "unrelated.py"}
    assert len(broad) > len(narrow)

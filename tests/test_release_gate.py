from pathlib import Path

import pytest

from engine.release_gate import release_gate, render_release_gate


def test_repository_engineering_release_gate_passes():
    root = Path(__file__).parents[1]
    result = release_gate(root)
    assert result["engineering_ready"] is True
    assert result["required_failures"] == []
    rendered = render_release_gate(result)
    assert "ENGINEERING READY: YES" in rendered
    assert "MEASURED RELEASE EVIDENCE: NO / NOT SUPPLIED" in rendered


def test_release_gate_checks_measured_report(tmp_path: Path):
    root = Path(__file__).parents[1]
    report = tmp_path / "report.json"
    report.write_text(
        """{
          "measured": true,
          "source_commit": "abc123",
          "repeats": 3,
          "case_ids": [
            "01","02","03","04","05","06","07","08","09","10",
            "11","12","13","14","15","16","17","18","19","20"
          ],
          "environment": {"python": "3.12"},
          "policy_lock": {"digest": "abc"},
          "trials": [
            {"raw_trace": "raw/a.json"},
            {"raw_trace": "raw/b.json"}
          ],
          "summary": {
            "plain": {
              "trials": 2,
              "verified_success_rate": 1.0,
              "total_model_tokens_mean": 1000,
              "weighted_usage_mean": 1000,
              "wall_time_ms_mean": 1000,
              "cached_input_tokens_mean": 0
            },
            "cascade": {
              "trials": 2,
              "verified_success_rate": 1.0,
              "total_model_tokens_mean": 700,
              "weighted_usage_mean": 600,
              "wall_time_ms_mean": 800,
              "cached_input_tokens_mean": 100
            }
          }
        }"""
    )
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "a.json").write_text("{}")
    (raw_dir / "b.json").write_text("{}")
    data = report.read_text().replace(
        '"raw/a.json"',
        f'"{(raw_dir / "a.json").as_posix()}"',
    ).replace(
        '"raw/b.json"',
        f'"{(raw_dir / "b.json").as_posix()}"',
    )
    data = data.replace(
        '"measured": true,',
        '"measured": true,\n'
        '          "configs": ["strongest","efficient","plain",'
        '"cascade","cascade-no-context","cascade-no-cache"],',
        1,
    )
    report.write_text(data)

    parallel = tmp_path / "parallel.json"
    parallel.write_text(
        """{
          "measured": true,
          "repeats": 3,
          "summary": {
            "disjoint": {
              "all_verified": true,
              "speedup": 1.25
            }
          }
        }"""
    )

    result = release_gate(
        root,
        benchmark_report=report,
        parallel_report=parallel,
    )
    assert result["measured_release_evidence"] is True
    assert result["savings"]["token_savings_percent"] == pytest.approx(30.0)

from pathlib import Path

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
    result = release_gate(root, benchmark_report=report)
    assert result["measured_release_evidence"] is True
    assert result["savings"]["token_savings_percent"] == 30.0

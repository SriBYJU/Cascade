# Acceptance Matrix

This file maps the frozen master-handoff acceptance gates to executable Cascade evidence. It distinguishes deterministic engineering gates from the two checks that still require a real authenticated Codex/model runtime.

| Area | Frozen requirement | Repository evidence | Status |
|---|---|---|---|
| Routing | quick/explore/build/deep; security floor; no-model; explicit override | `tests/test_acceptance_matrix.py`, `tests/test_routing.py`, `tests/test_model_profiles.py` | Automated |
| Context | no unrelated transcript; file/line provenance | `tests/test_context.py`, `tests/test_acceptance_matrix.py`, Context Firewall retrieval | Automated |
| Worktrees | writers isolated; forbidden path blocked; cleanup safe | `tests/test_worktrees.py`, `tests/test_parallel_executor.py`, merge/scope gates | Automated |
| Validation | pass/fail/timeout; discovery; output caps | `tests/test_validation.py`, `tests/test_validator_discovery.py`, `tests/test_validator_workspaces.py` | Automated |
| Budgets | denial; attempt/escalation limits; goal feature probe | `tests/test_budgets.py`, `tests/test_acceptance_matrix.py`, `scripts/verify_plugin_layout.py` | Automated |
| Reliability | resume; single-flight; stale cache | `tests/test_checkpoints.py`, `tests/test_acceptance_matrix.py`, `tests/test_cache.py` | Automated |
| Idempotency | replay returns prior result | `tests/test_idempotency.py` | Automated |
| Security | malicious repo/tool/peer text; policy protection; untrusted tool risk | `tests/test_security.py`, `tests/test_security_injection_matrix.py`, `tests/test_trace_redaction.py` | Automated |
| Metrics | head vs total; cached; route reason; trajectory steps | `tests/test_runtime_metrics.py`, `tests/test_observability.py`, `optimizer stats` | Automated |
| Plugin | manifests; safe install/uninstall; skill + six agents | `tests/test_plugin_manifest.py`, `tests/test_marketplace.py`, `tests/test_project_install.py`, `scripts/verify_plugin_layout.py` | Automated layout/install; live fresh-session discovery pending |
| Cross-platform | macOS/Linux/Windows clean engineering gate | GitHub Actions matrix: all three OSes × Python 3.11/3.12/3.13; `optimizer release-gate` runs in each job | Automated |
| Privacy | metadata-only by default | `tests/test_trace_redaction.py`; event redaction happens before SQLite write | Automated |
| Release provenance | trusted publishing + attestation | `scripts/release_preflight.py`, release workflow OIDC + artifact attestation | Automated |
| Scientific benchmark | repeatable A/B, ablations, raw trajectories, exact environment/policy | 23-task live suite, controlled model pool, parallel-live suite, `optimizer release-benchmark` | Harness complete; real authenticated run pending |
| Public claims | measured only | `optimizer savings`, benchmark cards, claim eligibility guard | Automated guard; no public savings number until live run |

## Final two external evidence steps

1. **Live Codex plugin smoke test** — install from the repository marketplace in a current authenticated Codex environment, start a fresh session, confirm the Cascade skill and six project agents are discoverable, then uninstall and verify cleanup.
2. **Measured release benchmark** — run `optimizer release-benchmark --profiles <real-profile.json> --repeats 3` on a real authenticated model environment, retain the raw trajectories and generated bundle, and pass it to `optimizer release-gate --benchmark-report ...`.

Everything else in the v0.1 engineering acceptance matrix is exercised automatically in CI.

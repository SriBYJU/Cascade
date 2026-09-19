# Roadmap

| Phase | Deliverable | Exit gate |
|---|---|---|
| 0 Measurement | baseline/trace schema, 20+ micro tasks | comparable task traces and quality/time/usage fields |
| 1 Codex-native proof | plugin, six agents, capability classes, Task Envelope, Context Firewall, rule router | installable local proof; bounded tasks route correctly |
| 2 Safety core | worktrees, scope gates, tool risk, idempotency, budgets, checkpoints | parallel writers isolated; resume/idempotency tests pass |
| 3 Context intelligence | repo map, retrieval fusion, compact evidence, exact cache | exploration context measurable vs baseline |
| 4 Verification | validator discovery, progressive validation, merge gates | no benchmark “done” without machine evidence |
| 5 Performance | DAG, bounded parallelism, single-flight, prompt affinity | selected parallel suite shows measured net improvement |
| 6 Observability | trace/why/stats/shadow and local event DB | every route explainable from local evidence |
| 7 Local tier | Ollama/vLLM, hardware detection, local-only policy | configured low-risk work can run locally |
| 8 Scientific eval | repeats, ablations, raw trajectories | report reproducible from release commit |
| 9 Adaptive policy | admitted evidence + policy proposal/lock | updates benchmarked, diffed, explicitly activated |
| 1.0 | cross-platform hardening, docs, security review, provenance | all release gates pass |

## Current implementation

The repository now contains executable implementations and automated gates across all phases. `optimizer release-gate` verifies the engineering/reproducibility prerequisites.

### Remaining release evidence

- **Real 23-task × 3-repeat authenticated run:** not preserved yet.
- **Real defensible “Cascade saves X%” number:** not yet; it must come from the preserved release-grade plain-vs-Cascade report and pass the public-claim guard.
- **Real sequential-vs-parallel report:** still needs to be preserved from the authenticated run.
- **Fresh ChatGPT desktop Codex discovery/install check:** still requires one product-level fresh-session confirmation.

Until those checks are complete, performance claims that depend on real model execution remain intentionally unclaimed. The earlier 63% example is not a measured Cascade release result.

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

The repository contains executable foundations for all phases so development can proceed without redesigning architecture. Claims that require real Codex/model runs remain intentionally unclaimed until measured.

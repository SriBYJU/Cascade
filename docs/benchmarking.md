# Benchmarking

## Principle

Benchmark the **harness**, not just the model. Hold task, repository commit, environment, toolchain, and model pool constant when comparing plain Codex with Cascade.

## Configurations

The evaluation framework is designed for:

1. strongest available model for all steps;
2. efficient model for all steps;
3. plain Codex/default delegation;
4. Cascade rule-based routing;
5. Cascade without Context Firewall;
6. Cascade without prompt-cache affinity;
7. Cascade without parallel DAG;
8. Cascade with a configured local tier.

## Outcomes

Quality: task success, deterministic acceptance, regressions, pass@1/pass@3.

Model use: head/worker input-output tokens, cached tokens, reasoning level.

System: wall time, context bytes, tool calls, agent calls, retries.

Routing: route decisions, escalations, unnecessary strong-tier calls, route regret in replay.

Safety: scope violations, unexpected writes, denied side effects, injection fixtures.

Reliability: resume success, idempotent replay, merge conflicts, circuit trips.

## Current included suite

`optimizer benchmark` runs a 20-case deterministic routing-policy suite. It is a code/acceptance benchmark only. It intentionally does not fabricate model usage, latency savings, or quality numbers.

## Scientific-report rule

For non-deterministic agent tasks, run repeated trials and report variance. Publish raw traces, exact commits, policy lock, environment metadata, and failed runs. Label every number as measured, estimated, or target.


## Live A/B harness

The live harness holds the generated fixture, task, acceptance commands, and model selection constant while comparing plain Codex with Cascade.

```bash
optimizer benchmark --suite live \
  --configs plain,cascade \
  --repeats 3 \
  --manifest benchmarks/fixtures/live_tasks.json \
  --output .cascade/benchmarks/live
```

Each trial starts from the same generated git fixture, runs deterministic acceptance commands, records failed runs, and writes a raw JSON trajectory under `raw/`. If Codex is unavailable, the report says `environment-unavailable`; Cascade does not fabricate benchmark numbers.

The first live manifest covers trivial edit, single-file bug, security/authorization, and multi-file dependency work. It is an initial A/B suite, not yet the full Phase 8 scientific benchmark.


## Implemented ablations

The live runner now supports two real single-task ablations in addition to plain and normal Cascade:

- `cascade-no-context`: disables the evidence-first Context Firewall and deliberately feeds a much broader mapped repository context.
- `cascade-no-cache`: disables measured prompt-cache-affinity scoring and observation.

```bash
optimizer benchmark --suite live \
  --configs plain,cascade,cascade-no-context,cascade-no-cache \
  --repeats 3
```

The parallel-DAG ablation remains a separate roadmap item because single-task live fixtures do not exercise DAG concurrency; Cascade does not label a no-op switch as a measured ablation.

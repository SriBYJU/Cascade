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

The live manifest now contains 23 deterministic cases across trivial edits, search, single- and multi-file bugs, features, test repair, migration, frontend behavior, documentation lookup, architecture exploration, security, repository exploration, refactoring, ambiguity, configuration, concurrency, serialization, cache behavior, integration, error handling, API validation, CLI behavior, and data structures. Read-only cases use explicit answer-substring acceptance while write cases use deterministic commands.


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


## Parallel scheduler micro-benchmark

`optimizer benchmark --suite parallel` measures only the local scheduler's ability to overlap three independent nodes while still serializing overlapping writer scopes.

```bash
optimizer benchmark --suite parallel --repeats 5 \
  --output .cascade/benchmarks/parallel.json
```

This benchmark is deliberately labeled **scheduler-only**. It proves the DAG/concurrency machinery can create parallel benefit without violating write-set serialization, but it is not an end-to-end model-latency claim. A live parallel-agent suite is still required before publishing product performance numbers.


## Live parallel ablation

Cascade also includes an end-to-end sequential-vs-parallel harness using identical generated repositories and the same model mapping:

```bash
optimizer benchmark --suite parallel-live \
  --repeats 3 \
  --model auto \
  --output .cascade/benchmarks/parallel-live.json
```

The current manifest contains a three-writer disjoint scenario and a mixed read/write scenario. Each writer is still isolated in its own worktree, acceptance is evaluated inside that worktree, and the report records full runtime stats plus sequential/parallel wall time. This is the appropriate surface for the Phase 5 latency claim; the scheduler-only benchmark remains a lower-level implementation check.


## Route regret replay

Once a task class has enough admitted objective evidence, `optimizer stats` compares each chosen route with the cheapest capability tier that has met the configured verified-success floor for that task class. Positive regret means over-routing to a stronger tier; negative regret flags a route below the best-known safe tier. The metric remains unavailable until the evidence threshold is met rather than fabricating an oracle from sparse runs.


## Reproducibility envelope and benchmark card

Live reports now capture OS/release/machine, Python, Git, Node/npm, Go, Rust/Cargo, adapter version when available, the exact Cascade commit, the active policy-lock digest/version, failed-trial count, per-configuration variance, and relative comparisons against the plain baseline. The harness writes both `report.json` and a human-readable `report.md`.

An existing JSON report can be rendered without rerunning models:

```bash
optimizer benchmark-card .cascade/benchmarks/live/report.json
```

Relative deltas remain `n/a` when the baseline denominator is zero. The Markdown card explicitly labels measured results and does not convert targets or estimates into performance claims.


## Controlled model-pool baselines

For a real model-routing experiment, pass a provider-neutral capability profile file rather than leaving every capability mapped to `auto`. The same pool is then available to Cascade and to fixed direct baselines:

```bash
optimizer benchmark --suite live \
  --profiles examples/model-profiles.example.json \
  --configs strongest,efficient,plain,cascade,cascade-no-context,cascade-no-cache,local \
  --repeats 3 \
  --output .cascade/benchmarks/model-pool
```

- `strongest` sends every task directly to the highest-capability available model in the supplied pool.
- `efficient` sends every task directly to the lowest-cost available model in the pool.
- `local` sends every task directly to the lowest-cost available local model and fails clearly if no local profile exists.
- `plain` preserves the direct/default Codex path using `--model` (default `auto`).
- `cascade` uses the full capability mapping so the router can select different models by trajectory step.

The report records the entire model-pool snapshot. Model names remain configuration data, not hard-coded routing policy.


## One-command final evidence bundle

For a release candidate, run:

```bash
optimizer release-benchmark \
  --profiles examples/model-profiles.example.json \
  --repeats 3 \
  --output .cascade/release-benchmark
```

The command requires at least three repeats and produces the live controlled-model-pool report, Context Firewall and cache ablations, optional local baseline, sequential-vs-parallel live report, explicit savings summaries, raw trial trajectories, and the release-gate result in one bundle. It requires a real authenticated model runtime and intentionally returns `environment-unavailable` rather than synthetic performance data when that runtime is absent.


## Benchmark trace privacy

Benchmark trajectories are metadata-only by default. Content-bearing fields such as model messages, errors, stdout/stderr, reviewer prose, and worker output are replaced with type/size/SHA-256 metadata before they are written to benchmark artifacts. This keeps the default privacy posture consistent with normal Cascade traces.

For synthetic/public fixtures where publishing full model/tool content is intentional, pass `--full-trace` to `optimizer benchmark`. Treat that flag as an explicit disclosure choice; do not use it on proprietary repositories or sensitive manifests unless the resulting artifacts are handled accordingly.

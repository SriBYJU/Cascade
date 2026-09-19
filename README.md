# Cascade

[![CI](https://github.com/SriBYJU/Cascade/actions/workflows/ci.yml/badge.svg)](https://github.com/SriBYJU/Cascade/actions/workflows/ci.yml)
[![CodeQL](https://github.com/SriBYJU/Cascade/actions/workflows/codeql.yml/badge.svg)](https://github.com/SriBYJU/Cascade/actions/workflows/codeql.yml)

**Stop making your smartest coding model do routine work.**

Cascade is a local-first adaptive orchestration layer for Codex. It routes each **trajectory step** to the least-expensive capable model—or to a deterministic tool—while minimizing context movement, isolating concurrent writes, verifying outcomes, and recording auditable evidence.

> Status: **engineering release candidate**. The core engine, safety gates, plugin packaging, cross-platform CI, benchmark harness, and release gate are implemented. Public performance claims still require the final repeated real-model benchmark; Cascade does not invent savings numbers.

> **New to Cascade?** Run `optimizer tutorial` after installation, or jump to the [step-by-step tutorial](#step-by-step-tutorial-use-cascade-on-any-repository).

## Why Cascade exists

A coding task does not have one difficulty level. The same request may involve cheap repository exploration, a difficult architecture choice, routine implementation, hard debugging, and deterministic tests. Using the strongest model for every step wastes scarce reasoning capacity; using a weak model everywhere causes retries and regressions.

Cascade treats models as heterogeneous compute, context as scarce bandwidth, deterministic tools as zero-LLM processors, tests as evidence, and the router as a scheduler.

## Five pillars

| Pillar | Question |
|---|---|
| **Route** | What is the least-expensive intelligence that can reliably handle this step? |
| **Context** | What is the minimum trustworthy evidence that worker needs? |
| **Execute** | Can this be deterministic, cached, or safely parallelized? |
| **Verify** | What objective evidence proves the result is correct? |
| **Learn** | What admitted evidence should influence future routes? |

## What is implemented

- Codex plugin manifest and six specialized agent contracts: scout, builder, debugger, reviewer, architect, integrator.
- Capability classes: `no-model`, `quick`, `explore`, `build`, `debug`, `deep`, `critical`.
- Step-level deterministic rule router with risk floors and separate reasoning-effort selection.
- Context Firewall primitives: incremental repository map, lexical/symbol/import/test/recency retrieval, file/line provenance, bounded Task Envelopes.
- Exact cache, prompt-affinity utilities, in-process single-flight deduplication.
- SQLite event log, checkpoints, exact-cache state, admitted-evidence store, idempotency ledger, and circuit breakers.
- Worktree-per-writer manager, write-set conflict detection, scope gate, rollback, and merge-gate primitives.
- Validator discovery for Python, JavaScript/TypeScript, Rust, and Go; progressive deterministic validation and secret-pattern checks.
- Bounded DAG/concurrency and token/context budget reservation.
- Codex `exec --json` adapter plus optional Ollama/vLLM adapter boundaries.
- Local `doctor`, `plan`, `run`, `resume`, `shadow`, `status`, `trace`, `why`, `stats`, `models`, `cache`, `benchmark`, and `cleanup` commands.
- 23-task live benchmark suite, deterministic micro-routing benchmark, controlled baselines/ablations, and acceptance-oriented automated tests.

## 60-second local quickstart

```bash
git clone https://github.com/SriBYJU/Cascade.git
cd Cascade
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
optimizer doctor
```

Then point Cascade at your own repository:

```bash
optimizer project-install --target /path/to/your/repo
cd /path/to/your/repo
optimizer plan "Fix the API validation bug" --write "src/api/**"
optimizer run "Fix the API validation bug" --write "src/api/**"
optimizer trace
optimizer stats
```

Add `--apply` to `optimizer run` only when you want a verified writer result integrated into a clean current checkout.

## Step-by-step tutorial: use Cascade on any repository

This is the simplest end-to-end path. You do **not** need to understand the router, worktrees, or benchmark system first.

### 1. Install the prerequisites

You need:

- **Git**
- **Python 3.11+**
- the **Codex CLI**, signed in if you want Cascade to execute model-backed tasks

Check the basics:

```bash
git --version
python --version
codex --version
```

If you only want to inspect Cascade's routing without running a model, Codex authentication is not required for `plan` or `shadow`.

### 2. Install Cascade

Clone Cascade once and install it into a virtual environment:

```bash
git clone https://github.com/SriBYJU/Cascade.git
cd Cascade
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
```

Verify the installation:

```bash
optimizer doctor
```

A healthy result shows your Git/Python environment, Codex compatibility, discovered validators, plugin/agent checks, and any local Ollama/vLLM models.

### 3. Add Cascade to the repository you want to work on

Suppose your project is at `~/code/my-app`:

```bash
optimizer project-install --target ~/code/my-app --dry-run
optimizer project-install --target ~/code/my-app
optimizer project-status --target ~/code/my-app
```

This installs the Cascade project skill and six project-scoped agent definitions. It does **not** overwrite conflicting project files unless you explicitly use `--overwrite`.

Now move into your project:

```bash
cd ~/code/my-app
```

### 4. Preview what Cascade would do

Start with `plan`. This does not execute the task:

```bash
optimizer plan "Fix the API validation bug" --write "src/api/**"
```

Then ask why Cascade chose that route:

```bash
optimizer why
```

You will see the selected capability class, reasoning effort, model target, risk level, evidence scope, budget, and escalation conditions.

If you want an even safer preview:

```bash
optimizer shadow "Fix the API validation bug" --write "src/api/**"
```

### 5. Run the task

For a read-only task:

```bash
optimizer run "Find where request authentication is enforced"
```

For a task that may edit files, give Cascade the narrowest reasonable write scope:

```bash
optimizer run \
  "Fix the API validation bug and add the smallest necessary test" \
  --write "src/api/**" \
  --write "tests/**"
```

Cascade will route the task, gather bounded evidence, create an isolated worktree for a writer, run validation, retry/escalate only when justified, and stop at the merge gate.

### 6. Inspect what happened

After a run:

```bash
optimizer trace
optimizer why
optimizer stats
optimizer status
```

- `trace` shows the route → context → agent → verification → merge/retry trajectory.
- `why` explains the most recent route choice.
- `stats` shows model tokens, weighted usage, cached input, context transfer, tool/agent calls, retries, and escalations.
- `status` shows persisted local state and resumable work.

### 7. Apply a verified change

By default, writer changes stay isolated. If you want Cascade to integrate a verified result into your **clean current checkout**, use `--apply`:

```bash
optimizer run \
  "Fix the API validation bug and add the smallest necessary test" \
  --write "src/api/**" \
  --write "tests/**" \
  --apply
```

Cascade only applies after scope, validation, merge, and safety gates pass. If the main checkout is dirty or integration validation fails, it stops instead of forcing the change.

### 8. Measure whether Cascade is actually saving work

For ordinary runs:

```bash
optimizer stats
```

For a reproducible A/B benchmark against plain Codex:

```bash
optimizer benchmark \
  --suite live \
  --configs plain,cascade \
  --repeats 3 \
  --output .cascade/benchmarks/live
```

Then show the readable savings summary:

```bash
optimizer savings .cascade/benchmarks/live/report.json
```

For a full release-grade experiment with controlled model profiles, ablations, and parallel evidence:

```bash
optimizer release-benchmark \
  --profiles examples/model-profiles.example.json \
  --repeats 3
```

Use real model IDs in your own profile file before treating the results as a performance claim.

### 9. Remove Cascade from a project

To remove only the files managed by Cascade:

```bash
optimizer project-uninstall --target ~/code/my-app
```

If you edited a managed file after installation, normal uninstall preserves it instead of deleting your work.

### The short version

For everyday use, remember this flow:

```text
doctor
  ↓
project-install
  ↓
plan / shadow
  ↓
run
  ↓
trace + why + stats
  ↓
run --apply  (only when you want integration)
```

### Optional: install Cascade from the Codex plugin marketplace

Current Codex supports repository marketplaces. Add Cascade with:

```bash
codex plugin marketplace add SriBYJU/Cascade
codex plugin marketplace list
```

Then restart the ChatGPT desktop app, open the **Plugin Directory**, choose **Cascade Local**, and install **Cascade**. Start a new conversation after installation so the plugin skill is freshly discovered.

The two installation paths are complementary:

- the **plugin** exposes the reusable Cascade skill;
- `optimizer project-install` installs the six project-scoped custom agents into a specific repository.

You can also print the beginner workflow at any time:

```bash
optimizer tutorial
```

## Architecture

```text
USER INTENT
    |
    v
HEAD / ORCHESTRATOR
    |
TASK / STEP COMPILER
    |
    +----------------------+----------------------+
    |                      |                      |
DETERMINISTIC         CONTEXT ENGINE          AI ROUTER
 git/AST/tests         repo map/evidence     capability+effort
    |                      |                      |
    +----------------------+----------------------+
                           |
                     TASK ENVELOPE
                           |
                 bounded worker / worktree
                           |
               DETERMINISTIC VALIDATION
                           |
                 pass / retry / escalate
                           |
                    MERGE / REVIEW GATE
                           |
                     VERIFIED RESULT
```

Sidecars: budget manager, exact cache, single-flight, worktree manager, write-set conflict predictor, idempotency ledger, checkpoint store, circuit breakers, policy lock, metrics.

## Commands

| Command | Purpose |
|---|---|
| `optimizer init` | Initialize local Cascade state. |
| `optimizer doctor` | Detect Codex, local endpoints, hardware, toolchain, and validators. |
| `optimizer tutorial` | Print the beginner end-to-end workflow in the terminal. |
| `optimizer plan` | Preview route, risk, evidence scope, and expected worker. |
| `optimizer run` | Execute the routed workflow. |
| `optimizer resume` | Inspect persisted resumable work. |
| `optimizer shadow` | Observe what Cascade would route without executing. |
| `optimizer status` | Current checkpoints, cache, and budget reservations. |
| `optimizer trace` | Structured local execution trace. |
| `optimizer why` | Explain the most recent route decision. |
| `optimizer stats` | Head-model and total-model usage plus routing outcomes. |
| `optimizer models` | Runtime capability profile. |
| `optimizer cache` | Inspect or clear exact cache. |
| `optimizer benchmark` | Run reproducible local benchmark fixtures. |
| `optimizer release-benchmark` | Run the full repeated live, ablation, parallel, savings, and release-evidence bundle. |
| `optimizer savings` | Show measured token/model-use/time savings from a live benchmark report. |
| `optimizer release-gate` | Run final engineering and measured-evidence release checks. |
| `optimizer project-install` | Safely install the Cascade skill and six custom agents into a repository. |
| `optimizer project-status` | Detect drift in installed project integration. |
| `optimizer project-uninstall` | Remove managed integration files while preserving user edits/backups. |
| `optimizer cleanup` | Prune stale worktrees and transient state. |

## Routing is capability-based, not model-name based

Policy says **what level of capability is required**. Runtime configuration says which concrete model currently implements that class. Override only when needed:

```bash
export CASCADE_MODEL_QUICK="<available-efficient-model>"
export CASCADE_MODEL_BUILD="<available-balanced-model>"
export CASCADE_MODEL_CRITICAL="<available-frontier-model>"
```

If unset, Cascade passes `auto` and lets Codex inherit the currently available model while still controlling the semantic route and reasoning level.

## Context Firewall

Workers do not receive full conversation or exploratory transcripts by default. They receive compact evidence with source path, line range, trust class, scope, constraints, and completion criteria. README text, source comments, logs, tool output, and peer-agent prose are treated as **data**, not authority.

## Verification > confidence

Cascade does not treat “done” from a model as proof. The preferred evidence order is:

`parser/compiler → types → targeted/package tests → integration tests → diff/scope → security → reviewer → head judgment`

The smallest defensible diff is preferred because unnecessary refactors increase context, merge risk, review cost, and regression surface.

## Privacy and infrastructure

- No signup required by Cascade.
- No Cascade telemetry backend.
- No source-code upload to Cascade servers—there are no required Cascade servers.
- SQLite state stays local under `.cascade/`.
- Trace bodies are designed to remain redacted/metadata-only by default.
- Optional local inference can use Ollama or vLLM if the user configures it.
- Cloud inference uses the user's own Codex/provider access; Cascade does not describe that inference as free.

## Benchmarks and claims

Cascade deliberately separates **goals** from **measured results**. The included micro-suite measures deterministic routing-policy behavior only. It does **not** support claims about token savings, model quality, or latency.

Any future public savings claim must publish the task list, exact policy lock, model/version/effort, toolchain versions, raw traces, failed runs, repeat counts, and comparison baseline. See [`docs/benchmarking.md`](docs/benchmarking.md).

## Current Codex compatibility assumptions

The repository was re-verified against current OpenAI documentation on 2026-09-19: project custom agents live under `.codex/agents/`; custom agents can select model, reasoning effort, and sandbox behavior; `codex exec --json` emits JSONL events including token/cache usage; and new portable Agent Plugins use a root `plugin.json` with the Agent Plugins schema. Cascade also keeps `.codex-plugin/plugin.json` as the supported Codex compatibility fallback. These interfaces evolve, so `optimizer doctor` and release CI treat platform drift as an explicit risk.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
python -m compileall -q engine
optimizer benchmark
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), and [`ROADMAP.md`](ROADMAP.md).

## License

MIT.


### Runtime compatibility preflight

`optimizer doctor` now feature-probes the installed Codex CLI for the exact non-interactive surfaces Cascade needs (`--json`, `--sandbox`, `--model`, and `--config`), validates both plugin manifests, checks all six project agents, reports local Ollama/vLLM availability, discovers deterministic validators, and returns an explicit release-preflight block. This keeps platform drift visible instead of silently assuming old interfaces still work.


## Measured savings

When a live benchmark contains both `plain` and `cascade`, Cascade automatically writes `savings.txt` and `savings.json` beside `report.json`. The terminal-friendly view can also be regenerated later:

```bash
optimizer savings .cascade/benchmarks/live/report.json
```

The summary reports token savings, weighted model-use savings, wall-time savings, verified-success change, cache delta, matched comparisons, and the exact source commit. Cascade only marks a token-savings claim as eligible when the measured candidate uses fewer tokens **and** has equal-or-better verified success than the selected baseline.


## Release gate

`optimizer release-gate` checks the portable and compatibility plugin manifests, six agents, metadata-only privacy default, bounded concurrency, 20+ live tasks, deterministic acceptance, parallel live suite, policy-lock digest, cross-platform CI matrix, and trusted OIDC/attested publishing configuration.

For a final measured release, provide the live benchmark report:

```bash
optimizer release-gate \
  --benchmark-report .cascade/benchmarks/live/report.json \
  --parallel-report .cascade/release-benchmark/parallel-live.json
```

The second form additionally requires a measured 20+ task report with at least three repeats, plain-vs-Cascade matched evidence, source commit, environment/policy metadata, and raw trajectory references. Performance targets are reported separately from hard engineering/safety gates.


## One-command release benchmark

On a machine with an authenticated Codex runtime and a real capability-profile file, the final scientific evidence bundle is one command:

```bash
optimizer release-benchmark \
  --profiles examples/model-profiles.example.json \
  --repeats 3
```

This runs the 23-case live suite across strongest-only, efficient-only, plain Codex, normal Cascade, Context-Firewall ablation, prompt-cache-affinity ablation, and a local tier when configured. It then runs the sequential-vs-parallel live suite, writes raw trajectories, generates `report.json`, `report.md`, `savings.txt`, `savings.json`, `parallel-live.json`, and a final `bundle.json` containing the release-gate result. If the model runtime is unavailable, the command records that state instead of inventing benchmark numbers.

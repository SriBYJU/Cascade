# Cascade

**Stop making your smartest coding model do routine work.**

Cascade is a local-first adaptive orchestration layer for Codex. It routes each **trajectory step** to the least-expensive capable model—or to a deterministic tool—while minimizing context movement, isolating concurrent writes, verifying outcomes, and recording auditable evidence.

> Status: **developer preview / active implementation**. The architecture is intentionally conservative: transparent rules first, measured claims only, no required backend, no telemetry by default.

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
- 20-task deterministic micro-routing benchmark and acceptance-oriented automated tests.

## 60-second local quickstart

```bash
git clone https://github.com/SriBYJU/Cascade.git
cd Cascade
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
optimizer doctor
optimizer plan "Fix the API validation bug" --write "src/api/**"
optimizer why
```

To execute a routed worker, install/sign in to Codex CLI and run:

```bash
optimizer run "Fix the API validation bug" --write "src/api/**"
```

For write tasks Cascade creates an isolated worktree and validates the result before marking it merge-ready. It does **not** silently bypass repository or permission gates.

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
  --benchmark-report .cascade/benchmarks/live/report.json
```

The second form additionally requires a measured 20+ task report with at least three repeats, plain-vs-Cascade matched evidence, source commit, environment/policy metadata, and raw trajectory references. Performance targets are reported separately from hard engineering/safety gates.

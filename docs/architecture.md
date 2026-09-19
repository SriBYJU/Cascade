# Architecture

Cascade is a Codex-native plugin with a portable Python 3.11+ local engine. Its invariant is that routing is only one part of the control loop. The product combines step-level capability routing, evidence-bounded context, deterministic-first execution, safe concurrency, objective validation, and explicit policy learning.

## Runtime loop

1. Fingerprint repository, toolchain, environment, and git state.
2. Reuse still-valid exact evidence when available.
3. Classify the current trajectory step: explore, transform, build, debug, verify, integrate, or critical.
4. Try deterministic resolution first.
5. Gather the minimum trustworthy evidence for the next decision.
6. Estimate risk, scope, write set, validation strength, and parallelizability.
7. Compile independent work into a DAG when useful.
8. Route capability + reasoning effort + concrete runtime model while accounting for budget, quota, cache, and risk.
9. Reserve hard budget before delegation.
10. Create one worktree per concurrent writer.
11. Send a bounded Task Envelope.
12. Execute while collecting structured events and provenance.
13. Run progressive deterministic validators.
14. Accept, review, retry, replan, escalate, or block based on evidence.
15. Dry-run conflict detection and enforce merge/scope gates.
16. Record outcomes; only trustworthy evaluator outcomes may enter admitted evidence.

## Architectural invariants

- No model is trusted merely because it is stronger.
- No worker gets full history unless a reason is recorded.
- No concurrent writers share a checkout.
- No external side effect is retried without idempotency protection.
- No routing policy silently changes live behavior.
- No public performance claim exists without reproducible traces.
- Untrusted repository/tool text cannot promote itself to trusted instruction.


## Structural repository map

The repository map now persists an exact-fingerprint local cache under `.cascade/repo-map.json` and records package boundaries, entry points, resolved intra-repository imports, reverse import edges, and test-to-implementation targets. Retrieval scoring can therefore rank structural neighbors rather than relying only on filename/token overlap. Python resolution uses the standard AST; relative JS/TS imports receive lightweight local resolution. Optional tree-sitter/LSP enrichment remains a future adapter rather than a mandatory dependency.


## High-risk reviewer trajectory step

After deterministic validation succeeds, HIGH and CRITICAL write tasks now enter a separate read-only reviewer step before becoming merge-ready. The reviewer sees a capped diff plus machine-validation evidence, runs with an explicit read-only sandbox, and must return structured JSON. Malformed reviewer output, adapter failure, or a material reviewer finding blocks the task. Low-risk bounded changes retain the fast lane and skip this expensive review step.


## Architect preflight for ambiguous/critical writes

Ambiguous write tasks and CRITICAL writes now invoke a separate read-only architect before any worktree writer starts. The architect receives the bounded Task Envelope and Context Firewall evidence, resolves the cross-cutting decision into structured constraints, and those constraints are injected into the writer envelope. A failed or malformed required preflight blocks the task instead of letting a builder guess. Resume checkpoints preserve the architect decision so it is not repeatedly re-spent after interruption.


## Project-aware validator discovery

Validator discovery no longer treats whatever tools happen to be installed in the caller's environment as project policy. Ruff and mypy run only when the repository declares their configuration; pytest runs when tests/configuration are present; compiler/parser checks remain deterministic defaults. Validation cache artifacts such as `.pytest_cache`, `__pycache__`, mypy/ruff caches, and coverage output are excluded from write-scope accounting so a failed first validation attempt cannot poison the next merge gate.


## Capability profile files

Concrete model names remain runtime configuration rather than routing policy. Repositories can now supply validated capability profiles either inline as `model_profiles` in `.cascade.json` or through a repository-contained `model_profiles_file`. Each entry declares a capability class, supported reasoning efforts, local/cloud placement, availability, and relative cost/latency weights. Invalid JSON, duplicate capability entries, attempts to redefine the deterministic `no-model` tier, empty/invalid reasoning declarations, or profile paths escaping the repository fail closed. Environment/`capability_map` overrides may replace only the model identifier; they do not lower the capability class or bypass security/risk floors.

See `examples/model-profiles.example.json` for a provider-neutral fixture.


## Monorepo-aware validator discovery

Validator specifications now carry an explicit repository-relative working directory. Cascade discovers root and conventional nested Python projects, parses npm/yarn/pnpm workspace package patterns, and runs each declared test/lint/typecheck command in the owning subproject rather than assuming the repository root. Workspace paths are resolved inside the repository and traversal patterns are ignored. This keeps validation deterministic while supporting common monorepo layouts without executing undeclared framework-specific commands.

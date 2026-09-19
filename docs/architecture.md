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

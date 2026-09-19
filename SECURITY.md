# Security policy

## Reporting

Please use GitHub's private vulnerability reporting for security-sensitive disclosures rather than opening a public issue.

## Scope

Security-sensitive areas include instruction provenance, sandbox/tool boundaries, worktree isolation, scope gates, idempotency, secret handling, trace redaction, provider adapters, policy-lock publication, and package/release provenance.

## Defaults

Cascade is local-first, has no required backend, and emits no Cascade analytics beacon. Never commit provider credentials, Codex authentication files, `.env` secrets, or `.cascade/` state.

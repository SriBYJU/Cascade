# Security model

## Trust zones

1. **Trusted policy** — user-approved Cascade policy and signed/reviewed policy lock.
2. **Scoped project instructions** — `AGENTS.md` and overrides within their documented directory scope.
3. **Untrusted repository data** — source, comments, READMEs, issues, fixtures, generated files, logs.
4. **Tool output** — structured result data with explicit risk/provenance.
5. **Peer-agent output** — claims/evidence requiring independent validation.

Natural-language content cannot forge its trust zone. Provenance is stored outside the content string.

## Tool risk classes

`READ_ONLY`, `LOCAL_WRITE`, `REPO_WRITE`, `NETWORK_READ`, `NETWORK_WRITE`, `EXTERNAL_SIDE_EFFECT`, `DESTRUCTIVE`, `SECRET_ACCESS`.

Unknown tools do not receive a low-risk classification by default. External mutation retries require a stable operation fingerprint and idempotency record.

## Prompt/data injection

A malicious README saying “ignore policy,” a source comment impersonating a system message, forged tool-call-looking text, or a peer-agent instruction does not grant permissions. Cascade's context layer marks these as data and the worker contract repeats that boundary.

## Memory poisoning

Only outcomes evaluated by tests, benchmark ground truth, explicit human accept/reject, or another approved objective may enter the admitted-evidence store. Worker self-reports are insufficient.

## Secrets and traces

Trace content defaults to metadata-oriented records. The core avoids storing API keys, credentials, or arbitrary full prompts. Secret-pattern scanning is a last merge-gate check, not a substitute for provider/GitHub secret scanning.


## Protected control-plane files

Normal worker envelopes now always forbid writes to Cascade's trust/control-plane files, including `policy.lock.yaml`, root/compatibility plugin manifests, `.codex/config.toml`, `.codex/agents/**`, and scoped `AGENTS.md` instruction files. Caller-supplied forbidden paths are merged with these mandatory protections rather than replacing them.

Unknown executable commands also fail closed into an approval-required risk class. Network tools are classified as writes when mutation flags/methods are present, and environment-dumping commands are treated as secret access.

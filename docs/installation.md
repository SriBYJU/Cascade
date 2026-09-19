# Installation and Codex integration

## Python CLI

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
optimizer doctor
```

## Codex plugin

Cascade includes `.codex-plugin/plugin.json` plus `skills/` and six agent definitions. Current Codex plugin tooling validates manifests from that path. During local plugin iteration, use the current official Codex plugin creator/validator and marketplace update flow rather than manually inventing marketplace metadata.

The public repository does not commit a user-specific personal marketplace file because that belongs under each user's Codex home. A future curated/repo marketplace can reference the released plugin artifact without changing the portable engine.

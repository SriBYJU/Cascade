# Installation and Codex integration

## Python CLI

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
optimizer doctor
```

## Codex plugin

Cascade includes the current portable root `plugin.json`, a `.codex-plugin/plugin.json` compatibility fallback, `skills/`, and six project agent definitions. Current OpenAI plugin documentation makes the root portable manifest canonical for new packages and continues to support the compatibility manifest. During local plugin iteration, use the current official plugin creator/validator and marketplace update flow rather than inventing marketplace metadata.

The public repository does not commit a user-specific personal marketplace file because that belongs under each user's Codex home. A future curated/repo marketplace can reference the released plugin artifact without changing the portable engine.


## Platform verification — 2026-09-19

Cascade's platform assumptions were checked against current official OpenAI documentation:

- Portable Agent Plugins use a root `plugin.json` with `$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`; `.codex-plugin/plugin.json` remains supported as a compatibility fallback.
- Portable plugins auto-discover `skills/`.
- Project custom agents live in `.codex/agents/` and require `name`, `description`, and `developer_instructions`; model, `model_reasoning_effort`, and `sandbox_mode` are supported configuration overrides.
- `[agents].max_concurrent_threads_per_session` is a supported bounded-concurrency setting.
- `codex exec --json` emits JSONL and `turn.completed` usage includes input, cached-input, output, and reasoning-output token fields.

Official references:
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/docs/agent-configuration/subagents
- https://developers.openai.com/docs/non-interactive-mode

Release CI should re-check these surfaces before a stable release because the plugin and custom-agent formats are still evolving.


## Long-running goal compatibility

Current Codex documentation exposes long-running `/goal` support through `[features] goals = true`. Cascade enables that supported feature in the project config, but it does **not** declare an undocumented native goal-token-budget key. Cascade's own hard reservation budgets remain the authoritative safety mechanism unless a future Codex release documents a native budget surface and `optimizer doctor` can feature-probe it.


## Safe project-scoped skill and agent install

Codex currently discovers repository skills under `.agents/skills` and project custom agents under `.codex/agents`. Cascade can materialize both into a target repository without requiring user-global state:

```bash
optimizer project-install --target /path/to/repo --dry-run
optimizer project-install --target /path/to/repo
optimizer project-status --target /path/to/repo
```

The install receipt is stored locally under `.cascade/project-install.json`. Existing conflicting files are never overwritten unless `--overwrite` is explicitly supplied; overwritten files receive local backups. Uninstall removes only files still matching the installed hash, restores backups when present, and preserves files changed by the user after installation.

```bash
optimizer project-uninstall --target /path/to/repo
```

This direct project integration is complementary to plugin-marketplace installation: the plugin exposes the reusable Cascade skill, while project installation is the explicit path for the six project-scoped custom-agent TOML definitions documented by Codex.


## Repository marketplace smoke path

Cascade now includes `.agents/plugins/marketplace.json` as a one-plugin repository marketplace. With a current Codex CLI, the supported marketplace workflow is:

```bash
codex plugin marketplace add ./
codex plugin marketplace list
codex
# then open /plugins, select "Cascade Local", and install Cascade
```

After installation, start a new Codex session so the plugin skill is discovered. The repository marketplace points directly at the repository root, where the portable `plugin.json` and `skills/` live. The six custom agents remain a separate project-scoped Codex surface and are installed with `optimizer project-install`.

To remove the added marketplace from Codex configuration:

```bash
codex plugin marketplace remove cascade-local
```

The marketplace catalog is validated in CI together with both plugin manifests and the packaged skill/agent resources.

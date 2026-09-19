# Naming and distribution identity

**Display brand:** Cascade  
**Repository:** `SriBYJU/Cascade`  
**Python distribution:** `cascade-codex`  
**Plugin machine name:** `cascade-codex`  
**CLI commands:** `optimizer` and `cascade`

“Cascade” is a common software/project name and is already used by unrelated developer and AI-agent projects. The project keeps the user-facing Cascade brand and repository name, while machine-facing distribution identifiers use `cascade-codex` to reduce package/plugin collision risk.

The plugin manifests intentionally keep `extensions.com.openai.interface.displayName = "Cascade"`, so users still see **Cascade** in supported plugin surfaces even though the stable machine identifier is `cascade-codex`.

Do not publish a second package or plugin under the bare machine name `cascade` without a new collision review.

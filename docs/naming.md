# Naming and distribution identity

**Display brand:** Cascade  
**Repository:** `SriBYJU/Cascade`  
**Python distribution:** `cascade-codex`  
**Plugin machine name:** `cascade-codex`  
**CLI commands:** `optimizer` and `cascade`

“Cascade” is a common software/project name and is already used by unrelated developer and AI-agent projects. The project keeps the user-facing Cascade brand and repository name, while machine-facing distribution identifiers use `cascade-codex` to reduce package/plugin collision risk.

The plugin manifests intentionally keep `extensions.com.openai.interface.displayName = "Cascade"`, so users still see **Cascade** in supported plugin surfaces even though the stable machine identifier is `cascade-codex`.

Do not publish a second package or plugin under the bare machine name `cascade` without a new collision review.


## Collision review

A final web/package-name sweep was run on 2026-09-19 before release-candidate hardening. It confirmed that the bare **Cascade** name is already used by unrelated developer/agent projects, including other Codex-adjacent tooling, so Cascade keeps that as the display brand rather than relying on it as a unique machine identifier.

The same sweep did not surface an obvious exact-match public Python/GitHub project using the full `cascade-codex` machine name. That is why the Python distribution and plugin identifier use `cascade-codex`.

This is a practical package/repository collision check, **not** trademark or legal clearance. Re-run the search immediately before a public package release because registries can change.

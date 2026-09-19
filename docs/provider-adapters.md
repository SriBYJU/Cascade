# Provider adapters

Launch order is Codex-native first. The adapter interface keeps the engine portable without turning Cascade into a generic inference gateway.

- `CodexAdapter`: executes `codex exec --json`, optionally selecting a resolved runtime model and independently overriding `model_reasoning_effort`.
- `OllamaAdapter`: optional localhost `/api` support for low-risk local work.
- `VLLMAdapter`: optional OpenAI-compatible local Responses boundary.
- `OpenAIAdapter`: reserved optional direct Responses integration; not a v0.1 dependency.

Local mode must fail closed according to user policy rather than loop on out-of-memory or incompatible tool behavior.

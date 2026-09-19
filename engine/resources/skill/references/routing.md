# Routing

Capability classes: `no-model`, `quick`, `explore`, `build`, `debug`, `deep`, `critical`.

Route every meaningful trajectory step. Choose the minimum safe capability floor from risk/scope/validation, then score available candidates using expected verified success, weighted usage, latency, context transfer, retry risk, quota pressure, privacy/tool risk, and cache affinity. If evidence is weak and validation is weak, bias upward. If validation is strong, a cheaper first attempt is acceptable.

Do not hard-code public model names into policy. Resolve capability classes against what `optimizer doctor` finds, with optional user overrides.

# Caching

Use exact cache before semantic cache. Exact entries key on normalized task, relevant repository fingerprint, constraints, tool versions, and capability profile. Reuse only while fingerprints and validation assumptions remain valid. Prompt-cache affinity is part of routing economics; do not switch tiers if the expected savings are smaller than cache value plus retry cost.

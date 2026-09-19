# Contributing

Cascade welcomes narrowly scoped contributions that make the optimizer more measurable, safe, portable, or useful.

Good contribution surfaces include validator/framework discovery, model capability profiles, benchmark tasks, routing heuristics, language-aware repository indexing, local inference adapters, security regression fixtures, and trace visualization.

Before opening a PR:

```bash
python -m pytest
python -m compileall -q engine
python -m engine.cli benchmark
```

Do not add performance marketing numbers without reproducible raw traces and a committed benchmark definition. Do not add hosted telemetry, mandatory accounts, unsupported credential interception, or autonomous write paths that bypass permission/merge gates.


## New contributors

Start with the repository's **good first issue** label. Those issues are intentionally scoped so a contributor can improve validator discovery, benchmark coverage, observability, or security fixtures without having to redesign the routing architecture. Keep additions deterministic, local-first, and covered by tests.

# Release gate

Do not call Cascade 1.0 until all of the following are true:

- clean install succeeds on macOS, Linux, and Windows;
- core acceptance tests pass;
- benchmark is reproducible from the release commit;
- no known unsafe worktree, merge, or external-side-effect behavior remains;
- privacy defaults are verified;
- package publication uses trusted publishing/provenance;
- docs distinguish measured results from targets;
- current Codex plugin/agent/config interfaces are re-verified against official OpenAI docs/source.

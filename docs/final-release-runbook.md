# Final release runbook

Cascade's engineering gate is automated. The final release evidence requires two real-environment checks that CI cannot truthfully synthesize.

## 1. Fresh ChatGPT desktop Codex plugin check

1. Open the ChatGPT desktop app.
2. Select **Codex** from the top-left menu.
3. Open the Cascade repository as the local project.
4. In a Codex terminal, run:

```bash
codex plugin marketplace add SriBYJU/Cascade
codex plugin marketplace list
```

5. Restart the ChatGPT desktop app.
6. Open **Plugin Directory**.
7. Select **Cascade Local**.
8. Install **Cascade**.
9. Start a fresh Codex conversation.
10. Confirm the Cascade skill is discoverable and the repository project integration exposes all six agent definitions after:

```bash
optimizer project-install --target . --dry-run
optimizer project-install --target .
optimizer project-status --target .
```

11. Run one read-only `plan` and one bounded write `plan`.
12. Uninstall the project integration and confirm user files remain untouched:

```bash
optimizer project-uninstall --target .
```

## 2. Repeated real-model benchmark

Do not use placeholder model IDs. Use only model IDs that the current authenticated Codex environment actually accepts.

From the Cascade repository:

```bash
optimizer doctor
optimizer models
```

Create a real provider-neutral profile JSON based on the available models, then run:

```bash
optimizer release-benchmark \
  --profiles /path/to/real-model-profiles.json \
  --repeats 3
```

The command produces:

- `live/report.json`
- `live/report.md`
- `live/savings.json`
- `live/savings.txt`
- `parallel-live.json`
- `bundle.json`
- metadata-only raw trajectories by default

Then run the explicit release gate:

```bash
optimizer release-gate \
  --benchmark-report .cascade/release-benchmark/live/report.json \
  --parallel-report .cascade/release-benchmark/parallel-live.json
```

Do not publish a performance percentage unless the measured report supports it. Keep failed runs, exact commit, environment/toolchain metadata, model profiles, policy-lock metadata, and raw trajectory references with the release evidence.

## One prompt for ChatGPT desktop Codex

Paste this into a Codex conversation opened on the Cascade repository:

```text
Finish Cascade's final release evidence without inventing any numbers.

1. Run optimizer doctor and optimizer models.
2. Verify the Cascade Local marketplace/plugin in this fresh desktop Codex
   environment and confirm the Cascade skill plus six project agents are
   discoverable.
3. Build a real model profile file using only model IDs that this authenticated
   environment actually accepts. Do not guess unavailable model IDs.
4. Run optimizer release-benchmark with 3 repeats.
5. Run optimizer release-gate using the generated live and parallel reports.
6. If any hard gate fails, diagnose and fix the implementation, rerun the
   affected checks, and do not claim completion until the gate passes.
7. Show the measured savings and quality numbers exactly as generated, including
   failed-run counts and any target misses.
```

This is the only remaining path from an engineering release candidate to a fully measured release.

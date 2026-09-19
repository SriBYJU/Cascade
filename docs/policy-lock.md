# Policy lock

`policy.lock.yaml` is intentionally written in the JSON subset of YAML so the core requires no YAML library.

The active policy is inspectable and reviewable. Learning never mutates it silently.

Workflow:

`observed runs → trusted evaluator admits outcomes → frozen evidence snapshot → candidate policy → benchmark + safety regression → explicit publish → active policy`

Hard safety floors, budget limits, and critical-task rules remain outside any later learned router.


## CLI workflow

```bash
optimizer policy status
optimizer policy propose \
  --benchmark-suite routing-regression-v2 \
  --quality-delta 0.00 \
  --weighted-usage-delta -0.20
optimizer policy diff
optimizer policy activate --approve-digest <exact-proposal-digest>
```

Deterministically validated runtime attempts can enter the admitted-evidence store through the `approved-objective` evaluator. Worker self-reports remain inadmissible. A proposal is written separately, diffed against the active lock, and cannot activate unless it carries measured benchmark fields and the operator supplies the exact proposal digest.


## Certificate from measured A/B report

Prefer deriving a policy certificate directly from the live benchmark report rather than typing deltas by hand:

```bash
optimizer policy propose \
  --from-report .cascade/benchmarks/live/report.json
```

The compiler requires a measured report with equal non-empty baseline/candidate trial counts and a positive baseline weighted-usage measurement. It derives quality delta and weighted-usage delta from the report, while activation still requires exact digest approval.

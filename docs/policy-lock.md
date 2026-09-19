# Policy lock

`policy.lock.yaml` is intentionally written in the JSON subset of YAML so the core requires no YAML library.

The active policy is inspectable and reviewable. Learning never mutates it silently.

Workflow:

`observed runs → trusted evaluator admits outcomes → frozen evidence snapshot → candidate policy → benchmark + safety regression → explicit publish → active policy`

Hard safety floors, budget limits, and critical-task rules remain outside any later learned router.

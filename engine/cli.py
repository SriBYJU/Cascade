from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .benchmarks import BenchmarkRunner
from .config import CascadeConfig
from .context.repo_map import build_repo_map
from .doctor import doctor
from .evaluation.harness import EvaluationHarness
from .evaluation.models import load_cases
from .evaluation.parallel_benchmark import run_scheduler_benchmark
from .evaluation.parallel_live import (
    ParallelLiveHarness,
    load_parallel_scenarios,
)
from .evaluation.report import load_report, measured_policy_certificate
from .observability.render import (
    render_plan,
    render_stats,
    render_trace,
    render_why,
)
from .policy_lock import load_policy, policy_digest, write_proposal
from .router.learner import AdmittedEvidenceStore
from .router.policy_compiler import (
    activate_policy,
    activation_ready,
    compile_policy_proposal,
    policy_diff,
)
from .schemas import ReasoningEffort
from .scheduler.dag import TaskNode
from .scheduler.executor import ParallelTaskSpec, compile_safe_dag, execute_dag
from .runtime import CascadeRuntime
from .validation.discover import discover_validators
from .workspace.worktree import WorktreeManager


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="optimizer",
        description="Cascade adaptive Codex orchestration engine",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="repository root (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="initialize local Cascade state")
    sub.add_parser(
        "doctor",
        help="detect Codex, local models, toolchain, validators, and hardware",
    )

    p = sub.add_parser(
        "plan",
        help="preview route, risk, context and expected worker",
    )
    p.add_argument("task", nargs="+", help="task text")
    p.add_argument(
        "--write",
        action="append",
        default=[],
        help="predicted/allowed write path glob; repeatable",
    )
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("run", help="execute the optimization workflow")
    p.add_argument("task", nargs="+", help="task text")
    p.add_argument(
        "--write",
        action="append",
        default=[],
        help="predicted/allowed write path glob; repeatable",
    )
    p.add_argument(
        "--forbid",
        action="append",
        default=[],
        help="forbidden path glob; repeatable",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="after merge gates pass, integrate into a clean current checkout",
    )

    p = sub.add_parser(
        "shadow",
        help="show what Cascade would route without executing",
    )
    p.add_argument("task", nargs="+", help="task text")
    p.add_argument("--write", action="append", default=[])
    p.add_argument("--json", action="store_true")

    p = sub.add_parser(
        "resume",
        help="resume a persisted run, or list resumable runs",
    )
    p.add_argument("run_id", nargs="?")
    p.add_argument(
        "--apply",
        action="store_true",
        help="integrate after successful resumed validation",
    )

    sub.add_parser(
        "status",
        help="show local tasks, worktrees and budgets",
    )

    p = sub.add_parser("trace", help="show execution event tree")
    p.add_argument("run_id", nargs="?")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("why", help="explain most recent route")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser(
        "stats",
        help="report head and total model usage plus routing outcomes",
    )
    p.add_argument("--json", action="store_true")
    sub.add_parser("models", help="show resolved capability profile")

    p = sub.add_parser("cache", help="inspect or clear exact cache")
    p.add_argument(
        "action",
        nargs="?",
        choices=["stats", "clear"],
        default="stats",
    )

    p = sub.add_parser(
        "batch",
        help="compile and execute an explicit task DAG from JSON",
    )
    p.add_argument(
        "spec",
        help="JSON file containing a list of task objects",
    )
    p.add_argument(
        "--plan-only",
        action="store_true",
        help="print the safe DAG without executing",
    )

    p = sub.add_parser(
        "benchmark",
        help="run reproducible local benchmark fixtures",
    )
    p.add_argument(
        "--suite",
        default="micro",
        choices=["micro", "live", "parallel", "parallel-live"],
    )
    p.add_argument(
        "--output",
        default=".cascade/benchmarks/latest.json",
    )
    p.add_argument(
        "--manifest",
        default="benchmarks/fixtures/live_tasks.json",
        help="live benchmark manifest",
    )
    p.add_argument(
        "--configs",
        default="plain,cascade",
        help="comma-separated live configs",
    )
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--model", default="auto")
    p.add_argument(
        "--effort",
        choices=[effort.value for effort in ReasoningEffort],
        default=ReasoningEffort.MEDIUM.value,
    )

    policy = sub.add_parser(
        "policy",
        help="inspect, propose, diff, or explicitly activate routing policy",
    )
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("status", help="show active policy and digest")

    pp = policy_sub.add_parser(
        "propose",
        help="compile a reviewable policy proposal from admitted evidence",
    )
    pp.add_argument("--minimum-samples", type=int, default=20)
    pp.add_argument("--success-floor", type=float, default=0.95)
    pp.add_argument("--benchmark-suite")
    pp.add_argument("--quality-delta", type=float)
    pp.add_argument("--weighted-usage-delta", type=float)
    pp.add_argument(
        "--from-report",
        help="derive the certificate from a measured live benchmark report",
    )
    pp.add_argument(
        "--output",
        default=".cascade/policy-proposal.json",
    )

    pd = policy_sub.add_parser("diff", help="diff proposal against active lock")
    pd.add_argument(
        "--proposal",
        default=".cascade/policy-proposal.json",
    )

    pa = policy_sub.add_parser(
        "activate",
        help="activate an evaluated proposal after exact digest approval",
    )
    pa.add_argument(
        "--proposal",
        default=".cascade/policy-proposal.json",
    )
    pa.add_argument(
        "--approve-digest",
        required=True,
        help="exact proposal digest printed by policy propose/diff",
    )

    sub.add_parser(
        "cleanup",
        help="prune stale worktrees and local transient state",
    )
    sub.add_parser(
        "repo-map",
        help="print incremental repository map summary",
    )
    sub.add_parser(
        "validators",
        help="show deterministic validators discovered",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    runtime = CascadeRuntime(repo)

    if args.command == "init":
        cfg = CascadeConfig.load(repo)
        _print(
            {
                "status": "initialized",
                "state_dir": str(cfg.state_dir),
                "db": str(cfg.db_path),
            }
        )
        return 0
    if args.command == "doctor":
        _print(doctor(repo))
        return 0
    if args.command in {"plan", "shadow"}:
        task = " ".join(args.task)
        planned = runtime.plan(task, write_paths=args.write or None)
        data = planned.to_dict()
        data["mode"] = args.command
        if args.json:
            _print(data)
        else:
            print(render_plan(data, mode=args.command))
        return 0
    if args.command == "run":
        task = " ".join(args.task)
        result = runtime.run(
            task,
            write_paths=args.write or None,
            allowed_paths=args.write or None,
            forbidden_paths=args.forbid or None,
            apply=args.apply,
        )
        _print(result)
        return (
            0
            if result.get("status")
            in {"verified", "merged", "blocked", "completed-read-only"}
            else 1
        )
    if args.command == "resume":
        if args.run_id:
            result = runtime.resume(args.run_id, apply=args.apply)
            _print(result)
            return (
                0
                if result.get("status")
                in {
                    "verified",
                    "merged",
                    "blocked",
                    "completed-read-only",
                    "not-found",
                }
                else 1
            )
        _print(runtime.checkpoints.resumable())
        return 0
    if args.command == "status":
        snapshot = runtime.budgets.snapshot()
        _print(
            {
                "resumable": runtime.checkpoints.resumable(),
                "budgets": {
                    "reserved_total_tokens": snapshot.total_tokens,
                    "reserved_head_tokens": snapshot.head_tokens,
                    "reserved_context_tokens": snapshot.context_tokens,
                    "active_reservations": list(snapshot.reservations),
                },
                "cache": runtime.cache.stats(),
            }
        )
        return 0
    if args.command == "trace":
        trace = runtime.trace(args.run_id)
        if args.json:
            _print(trace)
        else:
            print(render_trace(trace))
        return 0
    if args.command == "why":
        why = runtime.why()
        if args.json:
            _print(why or {"message": "no route recorded yet"})
        else:
            print(render_why(why))
        return 0
    if args.command == "stats":
        stats = runtime.stats()
        if args.json:
            _print(stats)
        else:
            print(render_stats(stats))
        return 0
    if args.command == "models":
        _print(
            [
                p.model_dump(mode="json")
                for p in runtime.registry.all()
            ]
        )
        return 0
    if args.command == "cache":
        if args.action == "clear":
            runtime.cache.clear()
            _print({"status": "cleared"})
        else:
            _print(runtime.cache.stats())
        return 0
    if args.command == "batch":
        raw = json.loads((repo / args.spec).read_text())
        if not isinstance(raw, list):
            raise ValueError("batch spec must be a JSON list")
        specs = [
            ParallelTaskSpec(
                task_id=str(item.get("id") or f"batch-{i+1}"),
                task=str(item["task"]),
                depends_on=set(item.get("depends_on", [])),
                write_patterns=tuple(item.get("write", [])),
                metadata={
                    "forbid": list(item.get("forbid", []))
                },
            )
            for i, item in enumerate(raw)
        ]
        dag = compile_safe_dag(specs)
        dag_view = [
            [
                {
                    "task_id": node.task_id,
                    "depends_on": sorted(node.depends_on),
                    "read_only": node.read_only,
                    "write_patterns": list(node.write_patterns),
                }
                for node in level
            ]
            for level in dag.levels()
        ]
        if args.plan_only:
            _print({"levels": dag_view})
            return 0

        def run_node(node: TaskNode) -> dict[str, Any]:
            return runtime.run(
                str(node.metadata["task"]),
                write_paths=list(node.write_patterns) or None,
                allowed_paths=list(node.write_patterns) or None,
                forbidden_paths=list(
                    node.metadata.get("forbid", [])
                )
                or None,
                apply=False,
            )

        results = execute_dag(
            dag,
            run_node,
            max_workers=runtime.config.max_concurrent_workers,
        )
        _print({"levels": dag_view, "results": results})
        ok = all(
            r.get("status")
            in {"verified", "blocked", "completed-read-only"}
            for r in results.values()
        )
        return 0 if ok else 1
    if args.command == "benchmark":
        if args.suite == "micro":
            runner = BenchmarkRunner(repo)
            result = runner.run_micro()
            out = repo / args.output
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2, sort_keys=True))
            _print({"output": str(out), **result["summary"]})
            return 0 if result["summary"]["failures"] == 0 else 1

        if args.suite == "parallel":
            result = run_scheduler_benchmark(
                repeats=args.repeats,
                max_workers=runtime.config.max_concurrent_workers,
            )
            out = repo / args.output
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2, sort_keys=True))
            _print({"output": str(out), **result})
            return 0

        if args.suite == "parallel-live":
            manifest = (
                repo / args.manifest
                if args.manifest != "benchmarks/fixtures/live_tasks.json"
                else repo / "benchmarks/fixtures/parallel_live.json"
            )
            scenarios = load_parallel_scenarios(manifest)
            parallel_harness = ParallelLiveHarness(repo)
            result = parallel_harness.run(
                scenarios,
                repeats=args.repeats,
                model=args.model,
                max_workers=runtime.config.max_concurrent_workers,
            )
            out = repo / args.output
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2, sort_keys=True))
            _print(
                {
                    "output": str(out),
                    "measured": result.get("measured"),
                    "status": result.get("status"),
                    "summary": result.get("summary"),
                }
            )
            return 0 if result.get("measured") else 2

        manifest = repo / args.manifest
        cases = load_cases(manifest)
        configs = [
            item.strip()
            for item in args.configs.split(",")
            if item.strip()
        ]
        output_arg = Path(args.output)
        live_dir = (
            output_arg
            if output_arg.suffix == ""
            else output_arg.parent / output_arg.stem
        )
        live_harness = EvaluationHarness(repo)
        report = live_harness.run(
            cases,
            configs=configs,
            repeats=args.repeats,
            output_dir=live_dir,
            model=args.model,
            effort=ReasoningEffort(args.effort),
        )
        _print(
            {
                "output": str(live_dir / "report.json"),
                "measured": report.get("measured"),
                "status": report.get("status"),
                "summary": report.get("summary"),
                "reason": report.get("reason"),
            }
        )
        return 0 if report.get("measured") else 2
    if args.command == "policy":
        active_path = repo / "policy.lock.yaml"
        current = load_policy(active_path)
        if args.policy_command == "status":
            ready, reasons = activation_ready(current)
            _print(
                {
                    "digest": policy_digest(current),
                    "policy": current.model_dump(mode="json"),
                    "activation_ready": ready,
                    "activation_blockers": reasons,
                }
            )
            return 0

        proposal_path = repo / args.proposal if hasattr(args, "proposal") else None
        if args.policy_command == "propose":
            store = AdmittedEvidenceStore(runtime.db)
            benchmark_suite = args.benchmark_suite
            quality_delta = args.quality_delta
            weighted_usage_delta = args.weighted_usage_delta
            if args.from_report:
                report = load_report(repo / args.from_report)
                certificate = measured_policy_certificate(report)
                benchmark_suite = certificate.benchmark_suite
                quality_delta = certificate.quality_delta
                weighted_usage_delta = certificate.weighted_usage_delta
            if not benchmark_suite:
                raise ValueError(
                    "--benchmark-suite or --from-report is required"
                )
            candidate = compile_policy_proposal(
                current,
                store,
                minimum_samples=args.minimum_samples,
                success_floor=args.success_floor,
                benchmark_suite=benchmark_suite,
                quality_delta=quality_delta,
                weighted_usage_delta=weighted_usage_delta,
            )
            out = repo / args.output
            write_proposal(candidate, out)
            ready, reasons = activation_ready(candidate)
            _print(
                {
                    "output": str(out),
                    "digest": policy_digest(candidate),
                    "diff": policy_diff(current, candidate),
                    "activation_ready": ready,
                    "activation_blockers": reasons,
                }
            )
            return 0

        if proposal_path is None:
            raise ValueError("proposal path is required")
        candidate = load_policy(proposal_path)
        if args.policy_command == "diff":
            ready, reasons = activation_ready(candidate)
            _print(
                {
                    "digest": policy_digest(candidate),
                    "diff": policy_diff(current, candidate),
                    "activation_ready": ready,
                    "activation_blockers": reasons,
                }
            )
            return 0

        activated = activate_policy(
            active_path=active_path,
            proposal_path=proposal_path,
            approval_digest=args.approve_digest,
        )
        _print(
            {
                "status": "activated",
                "digest": policy_digest(activated),
                "version": activated.version,
            }
        )
        return 0

    if args.command == "cleanup":
        manager = WorktreeManager(repo)
        manager.prune()
        _print(
            {
                "status": "cleanup complete",
                "worktree_root": str(manager.worktrees_dir),
            }
        )
        return 0
    if args.command == "repo-map":
        m = build_repo_map(repo)
        _print(
            {
                "root": m.root,
                "fingerprint": m.fingerprint,
                "files": len(m.files),
                "languages": sorted({f.language for f in m.files}),
            }
        )
        return 0
    if args.command == "validators":
        _print(
            [
                {
                    "name": v.name,
                    "command": list(v.command),
                    "category": v.category,
                }
                for v in discover_validators(repo)
            ]
        )
        return 0
    parser.error("unhandled command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

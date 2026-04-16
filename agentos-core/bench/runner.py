"""Benchmark runner with ablations and slice-aware metrics."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentos.config import Settings  # noqa: E402
from agentos.eval.scorer import score_expected  # noqa: E402
from agentos.llm import build_llm  # noqa: E402
from agentos.memory.store import MemoryStore  # noqa: E402
from agentos.runtime import TraceStore, run_agent  # noqa: E402
from agentos.tools.registry import build_default_registry  # noqa: E402


ABLATIONS = {
    "full": {},
    "no-memory": {"enable_memory": False},
    "no-planner": {"enable_planner": False},
    "no-tools": {"enable_tools": False},
    "no-reflection": {"enable_reflection": False},
}


async def run_benchmark(label: str, profile: str, tasks_file: Path,
                        db_path: str, max_tasks: int | None = None) -> dict:
    overrides = ABLATIONS[label]
    settings = Settings(profile=profile, db_path=db_path, **overrides)
    settings.apply_profile()

    llm = build_llm(settings)
    memory = MemoryStore(settings.db_path)
    tools = build_default_registry(settings)
    traces = TraceStore(settings.db_path, config=settings)

    tasks_data = json.loads(tasks_file.read_text())
    tasks = tasks_data["tasks"]
    if max_tasks:
        tasks = tasks[:max_tasks]

    results = []
    start_all = time.perf_counter()
    for i, task in enumerate(tasks, 1):
        memory.clear()
        seeded_ids = _seed_memory(memory, task.get("setup_memory", []))
        tstart = time.perf_counter()
        try:
            result = await run_agent(
                task["prompt"],
                llm=llm,
                tools=tools,
                memory=memory,
                traces=traces,
                config=settings,
                expected=task,
            )
            elapsed = time.perf_counter() - tstart

            scorable_output = result.status if task.get("expected_status") else result.answer
            sc = score_expected(scorable_output, task)
            sc = sc if sc is not None else result.score

            called_tools = [tc.get("tool") for tc in result.tool_calls]
            expected_tool = task.get("expected_tool")
            tool_ok = expected_tool in called_tools if expected_tool else None
            used_retrieval = any(f"memory:{entry_id}" in result.context_ids for entry_id in seeded_ids)

            results.append({
                "task_id": task["id"],
                "category": task["category"],
                "difficulty": task.get("difficulty"),
                "prompt": task["prompt"],
                "answer": result.answer,
                "score": sc,
                "heuristic_score": result.score,
                "tool_calls": called_tools,
                "expected_tool": expected_tool,
                "tool_match": tool_ok,
                "expected_behavior": task.get("expected_behavior"),
                "status": result.status,
                "steps": result.steps,
                "latency_ms": int(elapsed * 1000),
                "run_id": result.run_id,
                "error": result.error,
                "slices": task.get("slices", []),
                "setup_memory_ids": seeded_ids,
                "context_ids": result.context_ids,
                "retrieval_candidates": result.retrieval_candidates,
                "used_retrieval": used_retrieval,
                "reflection_count": result.reflection_count,
                "reflection_roi": result.reflection_roi,
                "initial_score": result.initial_score,
                "final_score": result.score,
            })
            print(
                f"  [{i}/{len(tasks)}] {task['id']:<14} score={sc:.2f} "
                f"{result.status:<8} {int(elapsed * 1000)}ms"
            )
        except Exception as exc:
            results.append({
                "task_id": task["id"],
                "error": str(exc),
                "score": 0.0,
                "status": "crash",
                "slices": task.get("slices", []),
            })
            print(f"  [{i}/{len(tasks)}] {task['id']:<14} CRASH: {exc}")

    total_elapsed = time.perf_counter() - start_all
    by_cat = _group_scores(results, "category")
    by_slice = _group_slices(results)

    summary = {
        "label": label,
        "profile": profile,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task_count": len(results),
        "overall_score": _avg([r.get("score", 0.0) for r in results]),
        "success_rate": sum(1 for r in results if (r.get("score") or 0) >= 0.6) / max(len(results), 1),
        "tool_call_success_rate": _tool_success_rate(results),
        "tool_precision": _tool_precision(results),
        "tool_recall": _tool_recall(results),
        "context_utility_rate": _context_utility(results),
        "reflection_roi": _reflection_roi(results),
        "mean_latency_ms": int(_avg([r.get("latency_ms", 0) for r in results])),
        "total_runtime_s": round(total_elapsed, 2),
        "flags": settings.describe()["flags"],
        "by_category": by_cat,
        "by_slice": by_slice,
        "results": results,
    }
    return summary


def _seed_memory(memory: MemoryStore, seeds: list[dict]) -> list[int]:
    ids: list[int] = []
    for seed in seeds:
        ids.append(
            memory.add(
                seed["text"],
                kind=seed.get("kind", "semantic"),
                salience=seed.get("salience", 0.8),
                meta=seed.get("meta"),
                ttl_seconds=seed.get("ttl_seconds"),
                source_run_id=seed.get("source_run_id"),
                tool_used=seed.get("tool_used"),
                verifier_score=seed.get("verifier_score"),
            )
        )
    return ids


def _avg(xs: list[float]) -> float:
    xs = [x for x in xs if isinstance(x, (int, float))]
    return sum(xs) / len(xs) if xs else 0.0


def _group_scores(results: list[dict], key: str) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for result in results:
        grouped.setdefault(result.get(key, "unknown"), []).append(result)
    return {
        name: {
            "n": len(items),
            "avg_score": round(_avg([item.get("score", 0.0) for item in items]), 3),
        }
        for name, items in grouped.items()
    }


def _group_slices(results: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for result in results:
        for slice_name in result.get("slices", []):
            grouped.setdefault(slice_name, []).append(result)
    return {
        name: {
            "n": len(items),
            "avg_score": round(_avg([item.get("score", 0.0) for item in items]), 3),
        }
        for name, items in grouped.items()
    }


def _tool_success_rate(results: list[dict]) -> float | None:
    checked = [r for r in results if r.get("expected_tool")]
    if not checked:
        return None
    return sum(1 for r in checked if r.get("tool_match")) / len(checked)


def _tool_precision(results: list[dict]) -> float | None:
    tp = 0
    fp = 0
    for result in results:
        called = result.get("tool_calls") or []
        expected = result.get("expected_tool")
        if expected:
            if expected in called:
                tp += 1
                fp += sum(1 for tool in called if tool != expected)
            else:
                fp += len(called)
        else:
            fp += len(called)
    denom = tp + fp
    return tp / denom if denom else None


def _tool_recall(results: list[dict]) -> float | None:
    tp = 0
    fn = 0
    for result in results:
        expected = result.get("expected_tool")
        if not expected:
            continue
        called = result.get("tool_calls") or []
        if expected in called:
            tp += 1
        else:
            fn += 1
    denom = tp + fn
    return tp / denom if denom else None


def _context_utility(results: list[dict]) -> float | None:
    retrieval_tasks = [r for r in results if r.get("setup_memory_ids")]
    if not retrieval_tasks:
        return None
    helpful = sum(
        1
        for result in retrieval_tasks
        if result.get("used_retrieval") and (result.get("score") or 0.0) >= 0.6
    )
    return helpful / len(retrieval_tasks)


def _reflection_roi(results: list[dict]) -> float | None:
    reflected = [r for r in results if (r.get("reflection_count") or 0) > 0]
    if not reflected:
        return None
    return _avg([r.get("reflection_roi", 0.0) for r in reflected])


def save(summary: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"{summary['label']}_{ts}.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    return out


def print_summary(summary: dict) -> None:
    print()
    print(f"=== {summary['label']} | profile={summary['profile']} ===")
    print(f"  tasks:              {summary['task_count']}")
    print(f"  overall score:      {summary['overall_score']:.3f}")
    print(f"  success rate:       {summary['success_rate']:.2%}")
    if summary["tool_call_success_rate"] is not None:
        print(f"  tool-call hit:      {summary['tool_call_success_rate']:.2%}")
    if summary["tool_precision"] is not None:
        print(f"  tool precision:     {summary['tool_precision']:.2%}")
    if summary["tool_recall"] is not None:
        print(f"  tool recall:        {summary['tool_recall']:.2%}")
    if summary["context_utility_rate"] is not None:
        print(f"  context utility:    {summary['context_utility_rate']:.2%}")
    if summary["reflection_roi"] is not None:
        print(f"  reflection ROI:     {summary['reflection_roi']:.3f}")
    print(f"  mean latency:       {summary['mean_latency_ms']} ms")
    print(f"  runtime:            {summary['total_runtime_s']}s")
    print(f"  flags:              {summary['flags']}")
    print("  by category:")
    for cat, s in summary["by_category"].items():
        print(f"    - {cat:<18} n={s['n']:<3} avg={s['avg_score']}")
    if summary["by_slice"]:
        print("  by slice:")
        for name, s in summary["by_slice"].items():
            print(f"    - {name:<18} n={s['n']:<3} avg={s['avg_score']}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="minimal", choices=["minimal", "full"])
    ap.add_argument("--ablation", default="full", choices=list(ABLATIONS.keys()))
    ap.add_argument("--tasks", default=str(ROOT / "bench" / "tasks.json"))
    ap.add_argument("--db", default=str(ROOT / "data" / "bench.db"))
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--all-ablations", action="store_true",
                    help="Run every ablation back-to-back.")
    args = ap.parse_args()

    out_dir = ROOT / "bench" / "results"
    tasks_file = Path(args.tasks)

    labels = list(ABLATIONS.keys()) if args.all_ablations else [args.ablation]
    for label in labels:
        db = str(Path(args.db).with_name(f"bench_{label}.db"))
        Path(db).unlink(missing_ok=True)
        summary = await run_benchmark(label, args.profile, tasks_file, db, args.max_tasks)
        out = save(summary, out_dir)
        print_summary(summary)
        print(f"  saved:              {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())

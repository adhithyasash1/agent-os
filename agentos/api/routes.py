"""HTTP API for agentos-core."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import Settings, settings
from ..llm import build_llm
from ..llm.protocol import LLM
from ..memory.store import MemoryStore
from ..runtime import TraceStore, run_agent
from ..tools.registry import ToolRegistry, build_default_registry


@dataclass
class Components:
    settings: Settings
    llm: LLM
    memory: MemoryStore
    tools: ToolRegistry
    traces: TraceStore


_components: Components | None = None


def get_components() -> Components:
    global _components
    if _components is None:
        _components = Components(
            settings=settings,
            llm=build_llm(settings),
            memory=MemoryStore(settings.db_path),
            tools=build_default_registry(settings),
            traces=TraceStore(settings.db_path, config=settings),
        )
    return _components


api_router = APIRouter()


class RunRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=4000)


class ConfigPatch(BaseModel):
    enable_memory: bool | None = None
    enable_planner: bool | None = None
    enable_tools: bool | None = None
    enable_reflection: bool | None = None
    enable_otel: bool | None = None


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    kinds: list[str] | None = None
    min_salience: float | None = Field(default=None, ge=0.0, le=1.0)


class RunFeedbackRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


@api_router.post("/runs")
async def create_run(req: RunRequest):
    c = get_components()
    result = await run_agent(
        req.input,
        llm=c.llm,
        tools=c.tools,
        memory=c.memory,
        traces=c.traces,
        config=c.settings,
    )
    return {
        "run_id": result.run_id,
        "answer": result.answer,
        "score": result.score,
        "steps": result.steps,
        "status": result.status,
        "tool_calls": result.tool_calls,
        "latency_ms": result.total_latency_ms,
        "error": result.error,
        "memory_hits": result.memory_hits,
        "context_ids": result.context_ids,
        "retrieval_candidates": result.retrieval_candidates,
        "reflection_count": result.reflection_count,
        "reflection_roi": result.reflection_roi,
        "rl_transition_count": result.rl_transition_count,
        "prompt_version": result.prompt_version,
        "verification": result.verification,
        "initial_score": result.initial_score,
    }


@api_router.get("/runs")
async def list_runs(limit: int = 50):
    c = get_components()
    return c.traces.list_runs(limit=limit)


@api_router.get("/runs/{run_id}")
async def get_run(run_id: str):
    c = get_components()
    run = c.traces.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@api_router.post("/runs/{run_id}/feedback")
async def leave_feedback(run_id: str, req: RunFeedbackRequest):
    c = get_components()
    if not c.traces.get_run(run_id):
        raise HTTPException(404, "run not found")
    feedback = req.model_dump(exclude_none=True)
    c.traces.record_feedback(run_id, feedback)
    return {"run_id": run_id, "feedback": feedback}


@api_router.get("/traces/{run_id}")
async def get_trace(run_id: str):
    return await get_run(run_id)


@api_router.get("/memory/stats")
async def memory_stats():
    c = get_components()
    return c.memory.stats()


@api_router.post("/memory/search")
async def memory_search(req: MemorySearchRequest):
    c = get_components()
    return {
        "results": c.memory.search(
            req.query,
            k=req.k,
            kinds=req.kinds,
            min_salience=req.min_salience,
        )
    }


@api_router.get("/tools")
async def list_tools():
    c = get_components()
    return [
        {"name": t.name, "description": t.description, "args": t.args_schema}
        for t in c.tools.list()
    ]


@api_router.get("/config")
async def get_config():
    c = get_components()
    return c.settings.describe()


@api_router.post("/config")
async def patch_config(patch: ConfigPatch):
    c = get_components()
    changed = {}
    for field, val in patch.model_dump(exclude_none=True).items():
        old = getattr(c.settings, field)
        setattr(c.settings, field, val)
        changed[field] = {"old": old, "new": val}
    c.tools = build_default_registry(c.settings)
    c.traces = TraceStore(c.settings.db_path, config=c.settings)
    return {"updated": changed, "current": c.settings.describe()}


@api_router.get("/health")
async def health():
    c = get_components()
    deps = {"memory": "ok", "traces": "ok"}
    try:
        _ = c.memory.count()
    except Exception:
        deps["memory"] = "error"

    if c.settings.llm_backend == "ollama":
        import httpx

        try:
            async with httpx.AsyncClient(timeout=2) as client:
                r = await client.get(f"{c.settings.ollama_base_url}/api/tags")
            deps["ollama"] = "ok" if r.status_code == 200 else "error"
        except Exception:
            deps["ollama"] = "unreachable"
    else:
        deps["llm"] = f"mock ({c.settings.llm_backend})"

    deps["otel"] = "enabled" if c.traces.otel_enabled else "disabled"
    all_ok = all(v.startswith(("ok", "mock")) or v == "disabled" for v in deps.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "dependencies": deps,
        "config": c.settings.describe(),
    }

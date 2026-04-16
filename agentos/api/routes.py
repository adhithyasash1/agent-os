"""HTTP API for agentos-core.

Components are built once at application startup (see `agentos.main`) and
stashed on `app.state`. Every request pulls them via the `Depends(...)`
mechanism, so we never mutate a process-global singleton under async load.
A `_config_lock` serializes `/config` patches — the handler builds a fresh
`Components` bundle from the patched settings and atomically swaps it in.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import Settings
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


def build_components(settings: Settings) -> Components:
    return Components(
        settings=settings,
        llm=build_llm(settings),
        memory=MemoryStore(settings.db_path),
        tools=build_default_registry(settings),
        traces=TraceStore(settings.db_path, config=settings),
    )


def get_components(request: Request) -> Components:
    components = getattr(request.app.state, "components", None)
    if components is None:
        raise HTTPException(500, "components not initialized")
    return components


_config_lock = asyncio.Lock()

api_router = APIRouter()


class RunRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=4000)


class ConfigPatch(BaseModel):
    enable_memory: bool | None = None
    enable_planner: bool | None = None
    enable_tools: bool | None = None
    enable_reflection: bool | None = None
    enable_llm_judge: bool | None = None
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
async def create_run(req: RunRequest, c: Components = Depends(get_components)):
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
async def list_runs(limit: int = 50, c: Components = Depends(get_components)):
    return c.traces.list_runs(limit=limit)


@api_router.get("/runs/{run_id}")
async def get_run(run_id: str, c: Components = Depends(get_components)):
    run = c.traces.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@api_router.post("/runs/{run_id}/feedback")
async def leave_feedback(
    run_id: str,
    req: RunFeedbackRequest,
    c: Components = Depends(get_components),
):
    if not c.traces.get_run(run_id):
        raise HTTPException(404, "run not found")
    feedback = req.model_dump(exclude_none=True)
    c.traces.record_feedback(run_id, feedback)
    return {"run_id": run_id, "feedback": feedback}


@api_router.get("/traces/{run_id}")
async def get_trace(run_id: str, c: Components = Depends(get_components)):
    run = c.traces.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@api_router.get("/memory/stats")
async def memory_stats(c: Components = Depends(get_components)):
    return c.memory.stats()


@api_router.post("/memory/search")
async def memory_search(
    req: MemorySearchRequest,
    c: Components = Depends(get_components),
):
    return {
        "results": c.memory.search(
            req.query,
            k=req.k,
            kinds=req.kinds,
            min_salience=req.min_salience,
        )
    }


@api_router.get("/tools")
async def list_tools(c: Components = Depends(get_components)):
    return [
        {"name": t.name, "description": t.description, "args": t.args_schema}
        for t in c.tools.list()
    ]


@api_router.get("/config")
async def get_config(c: Components = Depends(get_components)):
    return c.settings.describe()


@api_router.post("/config")
async def patch_config(patch: ConfigPatch, request: Request):
    """Patch feature flags atomically.

    Builds a fresh Settings + Components bundle from the patched values
    and swaps `app.state.components` under a lock. In-flight requests keep
    the components reference they already resolved through Depends, so
    they finish with consistent settings rather than half-patched state.
    """
    async with _config_lock:
        current: Components = request.app.state.components
        changes = patch.model_dump(exclude_none=True)
        if not changes:
            return {"updated": {}, "current": current.settings.describe()}

        updates: dict[str, dict[str, Any]] = {
            field: {"old": getattr(current.settings, field), "new": val}
            for field, val in changes.items()
        }
        new_settings = _clone_settings(current.settings, changes)

        new_components = Components(
            settings=new_settings,
            llm=current.llm,  # LLM swap is not exposed through this endpoint
            memory=current.memory,
            tools=build_default_registry(new_settings),
            traces=TraceStore(new_settings.db_path, config=new_settings),
        )
        request.app.state.components = new_components
        return {"updated": updates, "current": new_settings.describe()}


def _clone_settings(settings: Settings, overrides: dict[str, Any]) -> Settings:
    data = settings.model_dump()
    data.update(overrides)
    clone = Settings(**data)
    clone.apply_profile()
    # apply_profile may undo some overrides (e.g. forcing mock in minimal);
    # re-apply explicit overrides so patch intent wins.
    for key, value in overrides.items():
        setattr(clone, key, value)
    return clone


@api_router.get("/health")
async def health(c: Components = Depends(get_components)):
    deps = {"memory": "ok", "traces": "ok"}
    try:
        _ = c.memory.count()
    except Exception:
        deps["memory"] = "error"

    if c.settings.llm_backend == "ollama":
        import httpx

        headers = {}
        if c.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {c.settings.ollama_api_key}"
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                r = await client.get(
                    f"{c.settings.ollama_base_url}/api/tags",
                    headers=headers,
                )
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

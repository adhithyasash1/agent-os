from fastapi import APIRouter
from .chat import router as chat_router
from .runs import router as runs_router
from .memory import router as memory_router
from .tools import router as tools_router

api_router = APIRouter()

@api_router.get("/health")
async def health():
    """Health check with dependency status."""
    from app.memory.hybrid import memory
    from app.core.config import settings
    import httpx

    deps = {}

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            deps["ollama"] = "ok" if r.status_code == 200 else "error"
    except Exception:
        deps["ollama"] = "unreachable"

    # Chroma
    try:
        deps["chroma"] = "ok" if memory.vector_count() >= 0 else "error"
    except Exception:
        deps["chroma"] = "error"

    # Neo4j
    if memory.graph_driver:
        try:
            memory.graph_driver.verify_connectivity()
            deps["neo4j"] = "ok"
        except Exception:
            deps["neo4j"] = "error"
    else:
        deps["neo4j"] = "disabled"

    # Mem0 / Qdrant
    try:
        _ = memory.episodic_count()
        deps["mem0"] = "ok"
    except Exception:
        deps["mem0"] = "error"

    # Tavily
    deps["tavily"] = "configured" if settings.TAVILY_API_KEY else "missing_key"

    all_ok = all(v in ("ok", "configured", "disabled") for v in deps.values())
    return {"status": "ok" if all_ok else "degraded", "dependencies": deps}

api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(runs_router, prefix="/runs", tags=["runs"])
api_router.include_router(memory_router, prefix="/memory", tags=["memory"])
api_router.include_router(tools_router, prefix="/tools", tags=["tools"])

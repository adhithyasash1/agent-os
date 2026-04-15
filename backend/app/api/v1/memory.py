from fastapi import APIRouter, HTTPException
from app.memory.hybrid import memory
from app.memory.consolidation import consolidate_memories

router = APIRouter()


@router.post("/consolidate")
async def trigger_consolidation():
    """Trigger offline memory consolidation (dreaming).

    Deduplicates vectors, resolves graph contradictions, prunes low-value
    nodes, and compresses verbose episodic memories.
    """
    try:
        report = await consolidate_memories(memory)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consolidation failed: {e}")


@router.get("/stats")
async def memory_stats():
    """Return counts from all 3 memory tiers."""
    vector_count = memory.vector_count()
    episodic_count = memory.episodic_count()

    graph_nodes = 0
    graph_edges = 0
    if memory.graph_driver:
        try:
            result = memory.graph_run("MATCH (n) RETURN count(n) AS count")
            graph_nodes = result[0]["count"] if result else 0
        except Exception:
            pass
        try:
            result = memory.graph_run("MATCH ()-[r]->() RETURN count(r) AS count")
            graph_edges = result[0]["count"] if result else 0
        except Exception:
            pass

    return {
        "vector_count": vector_count,
        "episodic_count": episodic_count,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
    }


@router.get("/search")
async def search_memory(query: str):
    """Search across all 3 memory tiers."""
    # Vector search
    vector_results = []
    try:
        results = await memory.vector_store.asimilarity_search(query, k=5)
        vector_results = [{"content": r.page_content, "metadata": r.metadata} for r in results]
    except Exception:
        pass

    # Episodic search
    episodic_results = await memory.search_episodes(query, limit=3)

    # Graph search
    graph_results = await memory.search_graph(query, limit=3)

    return {
        "vector": vector_results,
        "episodic": episodic_results,
        "graph": graph_results,
    }

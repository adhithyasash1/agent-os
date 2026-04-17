from ..core import tool

@tool(
    name="search_memory",
    description="Search the agent's persistent long-term semantic memory for concepts, facts, or instructions.",
    args_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "the search term"},
            "k": {"type": "integer", "description": "optional number of results to fetch"}
        },
        "required": ["query"]
    },
    profiles=["full"]
)
async def _search_memory(args: dict, ctx: dict) -> dict:
    query = (args or {}).get("query", "").strip()
    k = (args or {}).get("k", 5)
    
    if not query:
        return {"status": "error", "error": "query is required"}
        
    memory_store = ctx.get("memory")
    if not memory_store:
        return {"status": "error", "error": "No memory store injected in context."}
        
    try:
        results = memory_store.search(query, k=k)
        return {
            "status": "ok", 
            "output": [
                {
                    "content": hit["text"],
                    "kind": hit["kind"],
                    "salience": hit.get("salience", 0.0)
                } for hit in results
            ]
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

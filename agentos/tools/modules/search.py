import httpx
from ..core import tool

@tool(
    name="tavily_search",
    description="Web search via Tavily API.",
    args_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "search query"}
        },
        "required": ["query"]
    },
    profiles=["full"]
)
async def _tavily_search(args: dict, ctx: dict) -> dict:
    query = (args or {}).get("query", "").strip()
    if not query:
        return {"status": "error", "error": "query is required"}
        
    cfg = ctx.get("config")
    api_key = getattr(cfg, "tavily_api_key", None) if cfg else None
    if not api_key:
        return {"status": "error", "error": "tavily_api_key not found in context configuration."}
        
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": 5},
            )
            r.raise_for_status()
            data = r.json()
            
        results = [
            {"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content", "")[:400]}
            for x in data.get("results", [])
        ]
        return {"status": "ok", "output": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}

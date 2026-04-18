import httpx
import asyncio
from typing import List, Dict, Any
from ..core import tool
from ..sanitizer import sanitize_output

@tool(
    name="hn_api",
    description="Comprehensive Hacker News research tool. Fetches stories and their top comments simultaneously (automatically sanitized).",
    args_schema={
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string", 
                "enum": ["top", "new", "item"],
                "description": "API endpoint: 'top' (ids), 'new' (ids), or 'item' (details/comments)"
            },
            "item_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of IDs to fetch."
            },
            "include_comments": {
                "type": "boolean",
                "description": "If true, also fetches top comments for each story provided in item_ids."
            },
            "max_comments": {
                "type": "integer",
                "description": "Maximum number of comments to fetch per item. Default is 3.",
                "default": 3
            }
        },
        "required": ["endpoint"]
    },
    profiles=["full"],
    requires_internet=True
)
@sanitize_output
async def _hn_api(args: dict, ctx: dict) -> dict:
    endpoint = (args or {}).get("endpoint")
    item_ids = (args or {}).get("item_ids", [])
    include_comments = (args or {}).get("include_comments", False)
    max_comments = (args or {}).get("max_comments", 3)
    
    base = "https://hacker-news.firebaseio.com/v0"
    sem = asyncio.Semaphore(5)
    
    async def safe_get(client, url):
        async with sem:
            for attempt in range(2):
                try:
                    r = await client.get(url, timeout=10)
                    r.raise_for_status()
                    return r.json()
                except Exception:
                    if attempt == 1: raise
                    await asyncio.sleep(0.5)
            return None

    if endpoint == "top":
        url = f"{base}/topstories.json"
        async with httpx.AsyncClient() as client:
            res = await safe_get(client, url)
            ids = res[:30] if res else []
            return {
                "status": "ok", 
                "output": ids,
                "observation_summary": f"Fetched {len(ids)} top story IDs from Hacker News."
            }

    elif endpoint == "item":
        if not item_ids:
            return {"status": "error", "error": "item_ids required"}
            
        async with httpx.AsyncClient() as client:
            story_tasks = [safe_get(client, f"{base}/item/{i}.json") for i in item_ids[:10]]
            stories = await asyncio.gather(*story_tasks)
            
            results = []
            comment_tasks = []
            
            for story in stories:
                if not story or not isinstance(story, dict):
                    continue
                
                story_data = {
                    "id": story.get("id"),
                    "title": story.get("title"),
                    "url": story.get("url"),
                    "score": story.get("score"),
                    "by": story.get("by"),
                    "descendants": story.get("descendants"),
                    "text": story.get("text", "")[:500],
                    "comments": []
                }
                
                if include_comments and story.get("kids"):
                    for cid in story["kids"][:max_comments]:
                        comment_tasks.append((story_data, f"{base}/item/{cid}.json"))
                
                results.append(story_data)
            
            if comment_tasks:
                actual_tasks = [safe_get(client, url) for _, url in comment_tasks]
                comments = await asyncio.gather(*actual_tasks)
                
                idx = 0
                for story_data, _ in comment_tasks:
                    comment = comments[idx]
                    if comment and isinstance(comment, dict):
                        story_data["comments"].append({
                            "by": comment.get("by"),
                            "text": (comment.get("text") or "")[:300]
                        })
                    idx += 1
            
            summary = f"Successfully fetched details for {len(results)} items: {item_ids[:len(results)]}. "
            if include_comments:
                summary += f"Includes top {max_comments} comment threads per item."
                    
            return {
                "status": "ok", 
                "output": results,
                "observation_summary": summary
            }

    return {"status": "error", "error": "Unknown endpoint"}

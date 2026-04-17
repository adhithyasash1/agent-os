import httpx
from ..core import tool

@tool(
    name="http_fetch",
    description="Fetch the body of an HTTP(S) URL (bounded to 50KB).",
    args_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "http(s) URL"}
        },
        "required": ["url"]
    },
    profiles=["full"]
)
async def _http_fetch(args: dict, ctx: dict) -> dict:
    url = (args or {}).get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        return {"status": "error", "error": "valid http(s) url required"}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "agentos-core/0.1"})
        body = r.text[:50000]
        return {"status": "ok", "output": {"status_code": r.status_code, "body": body, "url": str(r.url)}}
    except Exception as e:
        return {"status": "error", "error": str(e)}

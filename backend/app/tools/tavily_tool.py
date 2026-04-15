from tavily import TavilyClient
from app.core.config import settings

_client = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


async def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using Tavily and return clean, structured results."""
    client = _get_client()
    response = client.search(query, max_results=max_results, search_depth="advanced")
    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        })
    return results


async def tavily_extract(url: str) -> str:
    """Extract clean text content from a URL using Tavily."""
    client = _get_client()
    response = client.extract(urls=[url])
    results = response.get("results", [])
    if results:
        return results[0].get("raw_content", "") or results[0].get("text", "")
    return ""

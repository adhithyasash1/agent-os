import re
import json
from functools import wraps

def sanitize_output(func):
    """Decorator to apply the 2026 Golden Rule: Tools handle their own noise reduction."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        res = await func(*args, **kwargs)
        
        if res.get("status") != "ok" or "output" not in res:
            return res
            
        output = res["output"]
        
        # 1. Clean HTML if present (common in fallback scrapers)
        if isinstance(output, str) and ("<html" in output.lower() or "<body" in output.lower()):
            output = _strip_html(output)
            
        # 2. Compact JSON lists
        if isinstance(output, list) and len(output) > 5:
            # If it's a list of dicts, ensure they are pruned
            output = [_prune_dict(item) if isinstance(item, dict) else item for item in output]
            
        res["output"] = output
        return res
    return wrapper

def _strip_html(text: str) -> str:
    # Remove script and style tags completely
    text = re.sub(r'<(script|style).*?>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove all other tags
    text = re.sub(r'<.*?>', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:50000] # Safety cap

def _prune_dict(d: dict) -> dict:
    """Remove known noise fields from common APIs."""
    NOISE_FIELDS = {
        "kids", "descendants", "parent", "deleted", "dead", # HN
        "raw_content", "images", "videos", "metadata", # Search
        "headers", "cookies", "response_headers" # HTTP
    }
    return {k: v for k, v in d.items() if k not in NOISE_FIELDS}

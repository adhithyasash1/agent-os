"""Built-in tools.

- calculator:    pure Python, no deps, safe eval for arithmetic
- http_fetch:    GET a URL, return the text body (bounded)
- tavily_search: optional web search (requires API key + flag)
"""
from __future__ import annotations

import ast
import operator as op
import re
from typing import Any

import httpx

from .registry import Tool


# ---------- calculator ----------

_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Mod: op.mod, ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos,
    ast.FloorDiv: op.floordiv,
}


def _safe_eval(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"unsupported expression: {ast.dump(node)}")
    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body)


async def _calculator(args: dict) -> dict:
    expr = (args or {}).get("expression", "").strip()
    if not expr:
        return {"status": "error", "output": None, "error": "expression is required"}
    # Strip letters — be forgiving of natural-language garnish
    expr = re.sub(r"[A-Za-z_]", "", expr)
    try:
        value = _safe_eval(expr)
        return {"status": "ok", "output": value}
    except Exception as e:
        return {"status": "error", "output": None, "error": str(e)}


def calculator_tool() -> Tool:
    return Tool(
        name="calculator",
        description="Evaluate an arithmetic expression (+, -, *, /, %, //, **).",
        args_schema={"expression": "string, e.g. '2 + 2 * 3'"},
        fn=_calculator,
    )


# ---------- http_fetch ----------

async def _http_fetch(args: dict) -> dict:
    url = (args or {}).get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        return {"status": "error", "output": None, "error": "valid http(s) url required"}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "agentos-core/0.1"})
        body = r.text[:5000]
        return {"status": "ok", "output": {"status_code": r.status_code, "body": body, "url": str(r.url)}}
    except Exception as e:
        return {"status": "error", "output": None, "error": str(e)}


def http_fetch_tool() -> Tool:
    return Tool(
        name="http_fetch",
        description="Fetch the body of an HTTP(S) URL (bounded to 5KB).",
        args_schema={"url": "string, http(s) URL"},
        fn=_http_fetch,
    )


# ---------- tavily_search (optional) ----------

def tavily_search_tool(api_key: str) -> Tool:
    async def _search(args: dict) -> dict:
        query = (args or {}).get("query", "").strip()
        if not query:
            return {"status": "error", "output": None, "error": "query is required"}
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
            return {"status": "error", "output": None, "error": str(e)}

    return Tool(
        name="tavily_search",
        description="Web search via Tavily API (optional, off by default).",
        args_schema={"query": "string, search query"},
        fn=_search,
    )

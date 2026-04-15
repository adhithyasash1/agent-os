"""
MCP Server Manager — connects to external MCP servers via FastMCP client.

Servers integrated:
  - Excel MCP        (npx @negokaz/excel-mcp-server)       — read/write Excel files
  - Markdownify MCP  (npx @zcaceres/markdownify-mcp)       — convert anything to markdown
  - GitHub MCP       (npx @github/mcp-server)               — GitHub API access
  - HuggingFace MCP  (npx @llmindset/hf-mcp-server)        — HF Hub & inference
  - TradingView MCP  (python tradingview-mcp-server)        — market data & analysis
"""

import asyncio
from typing import Any
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from app.core.config import settings

# ---------------------------------------------------------------------------
# Transport definitions for each MCP server
# ---------------------------------------------------------------------------

def _excel_transport():
    return StdioTransport(
        command="npx",
        args=["--yes", "@negokaz/excel-mcp-server"],
    )

def _markdownify_transport():
    return StdioTransport(
        command="npx",
        args=["--yes", "@zcaceres/markdownify-mcp"],
    )

def _github_transport():
    return StdioTransport(
        command="npx",
        args=["--yes", "@github/mcp-server"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": settings.GITHUB_TOKEN},
    )

def _huggingface_transport():
    return StdioTransport(
        command="npx",
        args=["--yes", "@llmindset/hf-mcp-server"],
        env={"DEFAULT_HF_TOKEN": settings.HF_TOKEN} if settings.HF_TOKEN else {},
    )

def _tradingview_transport():
    return StdioTransport(
        command="tradingview-mcp-server",
        args=[],
    )


# ---------------------------------------------------------------------------
# Registry of available servers
# ---------------------------------------------------------------------------

SERVER_REGISTRY = {
    "excel": {
        "transport": _excel_transport,
        "description": "Read/write Excel files, create tables, format cells",
        "keywords": ["excel", "xlsx", "spreadsheet", "csv", "workbook"],
    },
    "markdownify": {
        "transport": _markdownify_transport,
        "description": "Convert webpages, PDFs, YouTube, DOCX, PPTX to Markdown",
        "keywords": ["markdown", "convert", "pdf", "youtube", "docx", "pptx", "webpage"],
    },
    "github": {
        "transport": _github_transport,
        "description": "Search code, manage repos, issues, PRs on GitHub",
        "keywords": ["github", "repo", "repository", "issue", "pull request", "pr", "code"],
        "requires": "GITHUB_TOKEN",
    },
    "huggingface": {
        "transport": _huggingface_transport,
        "description": "Query HuggingFace Hub models, datasets, spaces, run inference",
        "keywords": ["huggingface", "hf", "model", "dataset", "space", "inference", "ml"],
    },
    "tradingview": {
        "transport": _tradingview_transport,
        "description": "Market data, technical analysis, stock screening, backtesting",
        "keywords": ["stock", "market", "trading", "finance", "price", "chart", "analysis", "crypto"],
    },
}


# ---------------------------------------------------------------------------
# Public API — call any MCP server tool by name
# ---------------------------------------------------------------------------

async def call_mcp_tool(server_name: str, tool_name: str, arguments: dict[str, Any] = None) -> Any:
    """Connect to an MCP server, call a tool, and return the result."""
    entry = SERVER_REGISTRY.get(server_name)
    if not entry:
        return {"error": f"Unknown MCP server: {server_name}"}

    # Check credentials
    required = entry.get("requires")
    if required and not getattr(settings, required, ""):
        return {"error": f"Missing credential: {required}. Set it in .env"}

    transport = entry["transport"]()
    async with Client(transport) as client:
        result = await client.call_tool(tool_name, arguments or {})
        return result


async def list_mcp_tools(server_name: str) -> list[dict]:
    """List all tools available on an MCP server."""
    entry = SERVER_REGISTRY.get(server_name)
    if not entry:
        return [{"error": f"Unknown MCP server: {server_name}"}]

    transport = entry["transport"]()
    async with Client(transport) as client:
        tools = await client.list_tools()
        return [{"name": t.name, "description": t.description} for t in tools]


def match_servers(text: str) -> list[str]:
    """Given user text, return which MCP servers are relevant."""
    text_lower = text.lower()
    matches = []
    for name, info in SERVER_REGISTRY.items():
        if any(kw in text_lower for kw in info["keywords"]):
            # Skip if credentials missing
            required = info.get("requires")
            if required and not getattr(settings, required, ""):
                continue
            matches.append(name)
    return matches

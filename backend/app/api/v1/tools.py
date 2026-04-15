from fastapi import APIRouter, HTTPException
from app.tools.mcp_servers import SERVER_REGISTRY, list_mcp_tools, call_mcp_tool
from app.core.config import settings
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter()


@router.get("/")
async def list_servers():
    """List all registered MCP servers and their status."""
    servers = []
    for name, info in SERVER_REGISTRY.items():
        required = info.get("requires")
        has_creds = True
        if required:
            has_creds = bool(getattr(settings, required, ""))

        servers.append({
            "name": name,
            "description": info["description"],
            "keywords": info["keywords"],
            "available": has_creds,
            "requires": required,
        })
    return servers


@router.get("/{server_name}/tools")
async def get_server_tools(server_name: str):
    """List all tools exposed by a specific MCP server."""
    if server_name not in SERVER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown server: {server_name}")

    entry = SERVER_REGISTRY[server_name]
    required = entry.get("requires")
    if required and not getattr(settings, required, ""):
        raise HTTPException(
            status_code=403,
            detail=f"Missing credential: {required}. Set it in .env",
        )

    try:
        tools = await list_mcp_tools(server_name)
        return {"server": server_name, "tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect: {e}")


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Optional[dict[str, Any]] = None


@router.post("/{server_name}/call")
async def call_server_tool(server_name: str, req: ToolCallRequest):
    """Call a specific tool on an MCP server."""
    if server_name not in SERVER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown server: {server_name}")

    try:
        result = await call_mcp_tool(server_name, req.tool_name, req.arguments or {})
        return {"server": server_name, "tool": req.tool_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool call failed: {e}")

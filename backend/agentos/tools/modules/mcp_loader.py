import os
import json
import asyncio
import logging
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from ..core import _REGISTERED_TOOLS, Tool

logger = logging.getLogger("agentos.mcp")

# Configuration for MCP servers – could move to a JSON file later
DEFAULT_SERVERS = {
    "sequential_thinking": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "enabled": True
    },
    "fetch": {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "enabled": False # We have native http_fetch, but this is a backup
    }
}

class MCPBridge:
    """Manages connections to external MCP servers."""
    
    def __init__(self, server_name: str, config: dict):
        self.server_name = server_name
        self.command = config["command"]
        self.args = config["args"]
        self.env = config.get("env", None)
        
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **(self.env or {})}
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    res = await session.call_tool(tool_name, arguments=arguments or {})
                    
                    if res.isError:
                        return {"status": "error", "error": f"MCP Error: {res.content}"}
                    
                    # Consolidate content blocks
                    text_parts = []
                    for content in res.content:
                        if hasattr(content, "text"):
                            text_parts.append(content.text)
                    
                    return {
                        "status": "ok", 
                        "output": "\n".join(text_parts) if text_parts else "Success (no text output)"
                    }
        except Exception as e:
            logger.error(f"Failed to execute MCP tool {tool_name} on {self.server_name}: {e}")
            return {"status": "error", "error": f"MCP Connect Failure: {str(e)}"}

def register_mcp_servers():
    """Discover and register MCP tools into the AgentOS registry."""
    
    # 1. Register Configured Global Servers
    for name, cfg in DEFAULT_SERVERS.items():
        if not cfg.get("enabled"):
            continue
            
        bridge = MCPBridge(name, cfg)
        
        # In a real implementation, we would query the server for its tool list
        # For the POC, we register the primary tools we know exist
        if name == "sequential_thinking":
            _register_manual_mcp_tool(
                name="sequential_thinking",
                description="A detailed, step-by-step thinking process for complex problem solving.",
                bridge=bridge,
                origin=name
            )

    # 2. Local Script Discovery (Legacy support)
    _MCP_DIR = "agentos/mcp_servers"
    if os.path.isdir(_MCP_DIR):
        # This part still exists for custom local python scripts
        pass

def _register_manual_mcp_tool(name, description, bridge, origin):
    async def _mcp_fn(args: dict, ctx: dict) -> dict:
        return await bridge.call_tool(name, args)
        
    _REGISTERED_TOOLS.append(Tool(
        name=f"mcp_{name}",
        description=description,
        args_schema={"__dynamic__": "Generic MCP arguments mapping"},
        fn=_mcp_fn,
        profiles=["full"]
    ))

# Execute registration on import
register_mcp_servers()

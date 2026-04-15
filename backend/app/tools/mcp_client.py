from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, Any

class MCPClient:
    def __init__(self, command: str, args: list):
        self.server_params = StdioServerParameters(
            command=command,
            args=args
        )
        self.session = None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.content

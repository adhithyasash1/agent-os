"""
Core Tool specifications and decorators.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

ToolFn = Callable[[dict, dict], Awaitable[dict]]

@dataclass
class Tool:
    name: str
    description: str
    args_schema: dict
    fn: ToolFn
    profiles: list[str] = field(default_factory=lambda: ["full"])
    requires_internet: bool = False


# Global decorator registry
_REGISTERED_TOOLS: list[Tool] = []

def tool(name: str, description: str, args_schema: dict, profiles: list[str] | None = None, requires_internet: bool = False):
    """
    Decorator to register a function as an AgentOS Tool.
    
    The decorated function should have the signature:
        async def my_tool(args: dict, ctx: dict) -> dict | str | any
    
    If the function returns a dict containing "status", it is returned directly.
    Otherwise, the return value is automatically wrapped in {"status": "ok", "output": ...}.
    """
    def decorator(func: Callable):
        async def wrapper(args: dict, ctx: dict) -> dict:
            try:
                if inspect.iscoroutinefunction(func):
                    result = await func(args or {}, ctx)
                else:
                    import asyncio
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, func, args or {}, ctx
                    )
                    
                if not isinstance(result, dict) or "status" not in result:
                    result = {"status": "ok", "output": result}
                return result
            except Exception as e:
                return {"status": "error", "error": str(e), "output": None}

        t = Tool(
            name=name,
            description=description,
            args_schema=args_schema,
            fn=wrapper,
            profiles=profiles or ["full"],
            requires_internet=requires_internet
        )
        _REGISTERED_TOOLS.append(t)
        return wrapper
    return decorator

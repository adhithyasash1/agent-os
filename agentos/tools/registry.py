"""Tool registry.

A Tool is a small async callable with a name, description, and argument
schema. The registry decides which tools are available at runtime based on
feature flags.

Every tool returns a dict:
  {"status": "ok" | "error", "output": <any>, "error": <str|None>}

This makes the loop's error-recovery logic uniform.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

ToolFn = Callable[[dict], Awaitable[dict]]


@dataclass
class Tool:
    name: str
    description: str
    args_schema: dict  # {arg_name: "type description"}
    fn: ToolFn


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        if not self._tools:
            return ""
        out = []
        for t in self._tools.values():
            args = ", ".join(f"{k}: {v}" for k, v in t.args_schema.items()) or "(no args)"
            out.append(f"- {t.name}({args}) — {t.description}")
        return "\n".join(out)

    async def call(self, name: str, args: dict) -> dict:
        tool = self._tools.get(name)
        if not tool:
            return {"status": "error", "output": None,
                    "error": f"unknown tool: {name}"}
        try:
            if inspect.iscoroutinefunction(tool.fn):
                result = await tool.fn(args or {})
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, tool.fn, args or {}
                )
            if not isinstance(result, dict) or "status" not in result:
                result = {"status": "ok", "output": result}
            return result
        except Exception as e:
            return {"status": "error", "output": None, "error": str(e)}


def build_default_registry(settings) -> ToolRegistry:
    """Assemble the registry based on feature flags."""
    from .builtin import http_fetch_tool, calculator_tool, tavily_search_tool

    reg = ToolRegistry()
    if not settings.enable_tools:
        return reg

    # Calculator is always safe and useful
    reg.register(calculator_tool())

    if settings.enable_http_fetch:
        reg.register(http_fetch_tool())

    if settings.enable_tavily and settings.tavily_api_key:
        reg.register(tavily_search_tool(settings.tavily_api_key))

    return reg

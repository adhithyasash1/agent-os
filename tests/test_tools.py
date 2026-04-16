import pytest

from agentos.tools.builtin import calculator_tool, http_fetch_tool
from agentos.tools.registry import ToolRegistry


async def test_calculator_basic():
    tool = calculator_tool()
    reg = ToolRegistry()
    reg.register(tool)
    r = await reg.call("calculator", {"expression": "2 + 2 * 3"})
    assert r["status"] == "ok"
    assert r["output"] == 8


async def test_calculator_rejects_empty():
    reg = ToolRegistry()
    reg.register(calculator_tool())
    r = await reg.call("calculator", {"expression": ""})
    assert r["status"] == "error"


async def test_calculator_safe_eval():
    """Tool must not execute arbitrary Python."""
    reg = ToolRegistry()
    reg.register(calculator_tool())
    r = await reg.call("calculator", {"expression": "__import__('os').system('ls')"})
    # Letters are stripped so either parses to nothing / fails cleanly
    assert r["status"] == "error"


async def test_unknown_tool():
    reg = ToolRegistry()
    r = await reg.call("does_not_exist", {})
    assert r["status"] == "error"
    assert "unknown tool" in r["error"]


async def test_describe():
    reg = ToolRegistry()
    reg.register(calculator_tool())
    d = reg.describe()
    assert "calculator" in d
    assert "arithmetic" in d.lower()


async def test_default_registry_respects_flags(settings):
    from agentos.tools.registry import build_default_registry
    settings.enable_tools = False
    reg = build_default_registry(settings)
    assert reg.list() == []

    settings.enable_tools = True
    settings.enable_http_fetch = False
    reg = build_default_registry(settings)
    names = reg.names()
    assert "calculator" in names
    assert "http_fetch" not in names

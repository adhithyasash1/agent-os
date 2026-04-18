from agentos.tools.modules import workspace
from agentos.tools.registry import build_default_registry


async def test_calculator_basic(tools):
    # tools fixture already registered discovered tools
    r = await tools.call("calculator", {"expression": "2 + 2 * 3"})
    assert r["status"] == "ok"
    assert r["output"] == 8


async def test_calculator_rejects_empty(tools):
    r = await tools.call("calculator", {"expression": ""})
    assert r["status"] == "error"


async def test_calculator_safe_eval(tools):
    """Tool must not execute arbitrary Python."""
    r = await tools.call("calculator", {"expression": "__import__('os').system('ls')"})
    # Letters are stripped so it fails to parse or returns error safely
    assert r["status"] == "error"


async def test_unknown_tool(tools):
    r = await tools.call("does_not_exist", {})
    assert r["status"] == "error"
    assert "unknown tool" in r["error"]


async def test_describe(tools):
    desc = tools.describe()
    assert "calculator" in desc
    assert "arithmetic" in desc.lower()


async def test_default_registry_respects_flags(tools, settings):
    assert "calculator" in tools.names()

    settings.enable_tools = False
    reg = build_default_registry(settings)
    assert reg.list() == []

    settings.enable_tools = True
    settings.enable_http_fetch = False
    reg = build_default_registry(settings)
    names = reg.names()
    assert "calculator" in names
    assert "http_fetch" not in names

    # With full profile and network enabled, http_fetch should appear
    settings.profile = "full"
    settings.enable_http_fetch = True
    settings.force_local_only = False
    reg = build_default_registry(settings)
    assert "http_fetch" in reg.names()


async def test_workspace_read_file_rejects_oversized_files(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    big_file = tmp_path / "huge.txt"
    big_file.write_text("x" * (workspace.MAX_READ_BYTES + 1), encoding="utf-8")

    result = await workspace._read_file({"path": "huge.txt"}, {})
    assert result["status"] == "error"
    assert "File too large" in result["error"]

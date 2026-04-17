import os
from pathlib import Path
from ..core import tool

# Ensure sandbox exists
WORKSPACE_DIR = Path("data/workspace").resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

def _resolve_safe_path(requested_path: str) -> Path | None:
    """Resolve and validate a path to ensure it stays within the workspace sandbox."""
    try:
        # Resolve makes it absolute and resolves dots
        target = (WORKSPACE_DIR / requested_path).resolve()
        # Ensure the resolved target is sub-directory of sandbox
        if not str(target).startswith(str(WORKSPACE_DIR)):
            return None
        return target
    except Exception:
        return None

@tool(
    name="read_file",
    description="Read the contents of a file within the workspace sandbox.",
    args_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file (e.g. 'notes.txt')"}
        },
        "required": ["path"]
    },
    profiles=["full"]
)
async def _read_file(args: dict, ctx: dict) -> dict:
    path_str = (args or {}).get("path", "")
    if not path_str:
        return {"status": "error", "error": "path is required"}
        
    target = _resolve_safe_path(path_str)
    if not target or not target.exists() or not target.is_file():
        return {"status": "error", "error": f"File not found or access denied: {path_str}"}
        
    try:
        content = target.read_text(encoding="utf-8")
        return {"status": "ok", "output": content}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(
    name="write_file",
    description="Write contents to a file within the workspace sandbox.",
    args_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file"},
            "content": {"type": "string", "description": "Text content to write"}
        },
        "required": ["path", "content"]
    },
    profiles=["full"]
)
async def _write_file(args: dict, ctx: dict) -> dict:
    path_str = (args or {}).get("path", "")
    content = (args or {}).get("content", "")
    
    if not path_str:
        return {"status": "error", "error": "path is required"}
        
    target = _resolve_safe_path(path_str)
    if not target:
        return {"status": "error", "error": f"Access denied. Path escapes workspace sandbox: {path_str}"}
        
    try:
        # Create parent directories inside sandbox if needed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"status": "ok", "output": f"Successfully wrote to {path_str}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

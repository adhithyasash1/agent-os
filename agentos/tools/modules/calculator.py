import ast
import operator as op
import re
from ..core import tool

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

@tool(
    name="calculator",
    description="Evaluate an arithmetic expression (+, -, *, /, %, //, **).",
    args_schema={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "e.g. '2 + 2 * 3'"}
        },
        "required": ["expression"]
    },
    profiles=["minimal", "full"]
)
async def _calculator(args: dict, ctx: dict) -> dict:
    expr = (args or {}).get("expression", "").strip()
    if not expr:
        return {"status": "error", "error": "expression is required"}
    expr = re.sub(r"[a-df-zA-DF-Z_]", "", expr)
    try:
        value = _safe_eval(expr)
        return {"status": "ok", "output": value}
    except Exception as e:
        return {"status": "error", "error": str(e)}

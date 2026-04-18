from ..core import tool

@tool(
    name="sequential_thinking",
    description="A structured internal thought sandbox. Use this to break down complex problems, simulate outcomes, and maintain context across long research loops.",
    args_schema={
        "type": "object",
        "properties": {
            "thought": {"type": "string", "description": "The current line of reasoning"},
            "thought_number": {"type": "integer"},
            "total_thoughts": {"type": "integer"},
            "next_thought_needed": {"type": "boolean"},
            "is_revision": {"type": "boolean"},
            "revises_thought": {"type": "integer"}
        },
        "required": ["thought", "thought_number", "total_thoughts", "next_thought_needed"]
    },
    profiles=["full"]
)
async def _sequential_thinking(args: dict, ctx: dict) -> dict:
    # In 2026, thinking is a first-class citizen.
    # We log these thoughts to the 'working' memory automatically.
    thought = args["thought"]
    thought_num = args["thought_number"]
    total = args["total_thoughts"]
    
    memory_store = ctx.get("memory")
    if memory_store:
        memory_store.add(
            f"Thinking Step {thought_num}/{total}: {thought}",
            kind="working",
            salience=0.4
        )
        
    return {
        "status": "ok",
        "output": f"Thought {thought_num}/{total} registered. " + ("Continue thinking." if args['next_thought_needed'] else "Ready for action.")
    }

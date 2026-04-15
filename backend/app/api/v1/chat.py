from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.agents.graph import agent_executor
from app.core.config import settings
from langchain_core.messages import HumanMessage
import uuid
import json
import logging

logger = logging.getLogger("agentos.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


@router.post("/")
async def chat(request: ChatRequest):
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "task_id": request.task_id,
        "current_plan": "",
        "tool_outputs": [],
        "memory_context": "",
        "episodic_context": "",
        "graph_context": "",
        "eval_score": 0.0,
        "eval_critique": "",
        "is_complete": False,
        "iteration": 0,
        "context_chars": 0,
    }

    try:
        result = await agent_executor.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise HTTPException(status_code=502, detail=f"Agent execution failed: {e}")

    return {
        "response": result["messages"][-1].content,
        "score": result.get("eval_score", 0.0),
        "task_id": result["task_id"],
        "iteration": result.get("iteration", 1),
        "context_chars": result.get("context_chars", 0),
    }


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint — sends progress events as the agent works."""
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "task_id": request.task_id,
        "current_plan": "",
        "tool_outputs": [],
        "memory_context": "",
        "episodic_context": "",
        "graph_context": "",
        "eval_score": 0.0,
        "eval_critique": "",
        "is_complete": False,
        "iteration": 0,
        "context_chars": 0,
    }

    async def event_stream():
        try:
            async for event in agent_executor.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name in (
                    "executor", "planner", "evaluator", "memory_manager"
                ):
                    yield f"data: {json.dumps({'type': 'step', 'node': name})}\n\n"

                elif kind == "on_chain_end" and name == "planner":
                    output = event.get("data", {}).get("output", {})
                    plan = output.get("current_plan", "")
                    if plan:
                        yield f"data: {json.dumps({'type': 'response', 'content': plan})}\n\n"

                elif kind == "on_chain_end" and name == "evaluator":
                    output = event.get("data", {}).get("output", {})
                    yield f"data: {json.dumps({'type': 'eval', 'score': output.get('eval_score', 0), 'critique': output.get('eval_critique', '')})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

from typing import Annotated, List, TypedDict, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    task_id: str
    current_plan: str
    tool_outputs: List[Dict[str, Any]]
    # Memory context from all 3 tiers
    memory_context: str           # vector (Chroma) similarity results
    episodic_context: str         # episodic (Mem0) past experiences
    graph_context: str            # graph (Neo4j) entity-relationship traversal
    # Evaluation
    eval_score: float
    eval_critique: str            # LLM Council critique before scoring
    is_complete: bool
    iteration: int
    # Observability
    context_chars: int            # total chars of context fed to planner

from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import planner_node, executor_node, memory_node, evaluator_node


def create_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("executor", executor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("memory_manager", memory_node)

    # Executor runs FIRST — fetch web data before the planner needs it
    workflow.set_entry_point("executor")

    # executor → planner → evaluator → memory_manager
    workflow.add_edge("executor", "planner")
    workflow.add_edge("planner", "evaluator")
    workflow.add_edge("evaluator", "memory_manager")

    def should_continue(state: AgentState):
        if state.get("is_complete", False):
            return "end"
        return "executor"

    workflow.add_conditional_edges(
        "memory_manager",
        should_continue,
        {
            "end": END,
            "executor": "executor",
        },
    )

    return workflow.compile()


agent_executor = create_agent_graph()

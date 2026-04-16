"""End-to-end tests of the agent loop against the mock LLM."""
import pytest

from agentos.runtime import run_agent


async def test_loop_answers_simple_question(llm, tools, memory, traces, settings):
    result = await run_agent(
        "What is the capital of France?",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "ok"
    assert "Paris" in result.answer
    assert result.score > 0
    assert result.prompt_version == settings.prompt_version


async def test_loop_uses_calculator(llm, tools, memory, traces, settings):
    result = await run_agent(
        "Calculate 2 + 2 * 3",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "ok"
    assert any(tc["tool"] == "calculator" for tc in result.tool_calls)
    assert result.rl_transition_count > 0


async def test_loop_rejects_empty_input(llm, tools, memory, traces, settings):
    result = await run_agent(
        "   ",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "rejected"
    assert result.answer == ""


async def test_loop_records_trace_events(llm, tools, memory, traces, settings):
    result = await run_agent(
        "What is the capital of France?",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    run = traces.get_run(result.run_id)
    kinds = [e["kind"] for e in run["events"]]
    assert "understand" in kinds
    assert "retrieve" in kinds
    assert "plan" in kinds
    assert "final" in kinds


async def test_loop_memory_disabled_still_works(llm, tools, memory, traces, settings):
    settings.enable_memory = False
    result = await run_agent(
        "What is the capital of France?",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "ok"
    run = traces.get_run(result.run_id)
    kinds = [e["kind"] for e in run["events"]]
    assert "retrieve" not in kinds


async def test_loop_tools_disabled(llm, tools, memory, traces, settings):
    settings.enable_tools = False
    from agentos.tools.registry import build_default_registry
    tools = build_default_registry(settings)
    result = await run_agent(
        "Calculate 2 + 2 * 3",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "ok"
    assert not any(tc["tool"] == "calculator" for tc in result.tool_calls)


async def test_loop_stores_verified_answer_in_durable_memory(llm, tools, memory, traces, settings):
    """Promotion requires a trustworthy verification mode (expected match
    or LLM judge). Heuristic scores alone must NOT promote."""
    before = memory.stats()["by_kind"].copy()
    result = await run_agent(
        "What is the capital of France?",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
        expected={"expected_contains": ["Paris"]},
    )
    run = traces.get_run(result.run_id)
    assert any(t["stage"] == "verify" for t in run["transitions"])
    stats = memory.stats()["by_kind"]
    assert stats["episodic"] >= before["episodic"] + 1
    assert stats["semantic"] >= before["semantic"] + 1


async def test_loop_does_not_promote_on_heuristic_only(llm, tools, memory, traces, settings):
    """Live runs with no ground truth and no LLM judge should not promote
    heuristic answers — the old scorer silently wrote fabricated facts to
    durable memory when an answer merely overlapped the context."""
    assert settings.enable_llm_judge is False
    result = await run_agent(
        "What is the capital of France?",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "ok"
    stats = memory.stats()["by_kind"]
    assert stats["episodic"] == 0
    assert stats["semantic"] == 0


async def test_loop_plan_events_include_richer_react_fields(llm, tools, memory, traces, settings):
    result = await run_agent(
        "Calculate 19 * 17",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    run = traces.get_run(result.run_id)
    plan_event = next(event for event in run["events"] if event["kind"] == "plan")
    assert "goal" in plan_event["output"]
    assert "confidence" in plan_event["output"]
    assert "stop_reason" in plan_event["output"]


async def test_loop_refuses_gibberish_without_promoting_durable_memory(llm, tools, memory, traces, settings):
    result = await run_agent(
        "asdkjf laksjdf lkasjdf lkajsdf random gibberish text with no meaning whatsoever",
        llm=llm, tools=tools, memory=memory, traces=traces, config=settings,
    )
    assert result.status == "ok"
    assert "don't have enough information" in result.answer.lower()
    stats = memory.stats()["by_kind"]
    assert stats["episodic"] == 0
    assert stats["semantic"] == 0

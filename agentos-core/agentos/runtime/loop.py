"""Core agent loop with tiered memory, context packing, and RL logging."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import Settings, settings as default_settings
from ..eval.reflection import reflect
from ..eval.scorer import score_answer_details
from ..llm.protocol import LLM
from ..memory.store import MemoryStore
from ..tools.registry import ToolRegistry
from .context_packer import pack_context
from .planner import PlanDecision, plan_next_step
from .trace import RLTransition, TraceEvent, TraceStore, Timer


@dataclass
class AgentResult:
    run_id: str
    answer: str
    score: float
    steps: int
    tool_calls: list[dict] = field(default_factory=list)
    total_latency_ms: int = 0
    total_tokens: int = 0
    status: str = "ok"
    error: str | None = None
    memory_hits: list[dict] = field(default_factory=list)
    context_ids: list[str] = field(default_factory=list)
    retrieval_candidates: list[str] = field(default_factory=list)
    reflection_count: int = 0
    reflection_roi: float = 0.0
    rl_transition_count: int = 0
    prompt_version: str = ""
    verification: dict[str, Any] = field(default_factory=dict)
    initial_score: float = 0.0


async def run_agent(
    user_input: str,
    *,
    llm: LLM,
    tools: ToolRegistry,
    memory: MemoryStore,
    traces: TraceStore,
    config: Settings | None = None,
    expected: dict | None = None,
) -> AgentResult:
    cfg = config or default_settings
    run_id = traces.start_run(
        user_input,
        cfg.profile,
        cfg.describe()["flags"],
        prompt_version=cfg.prompt_version,
    )

    step = 0
    transition_step = 0
    tool_results: list[dict] = []
    total_latency = 0
    total_tokens = 0
    critique = ""
    answer = ""
    score = 0.0
    initial_score_value: float | None = None
    reflection_gain = 0.0
    verification: dict[str, Any] = {}
    memory_hits: list[dict] = []
    prior_decisions: list[PlanDecision] = []
    reflection_baseline: float | None = None

    def next_step() -> int:
        nonlocal step
        step += 1
        return step

    def next_transition_step() -> int:
        nonlocal transition_step
        transition_step += 1
        return transition_step

    if not user_input or not user_input.strip():
        event_step = next_step()
        traces.log(
            TraceEvent(
                run_id,
                event_step,
                "error",
                "input",
                error="empty input",
                attributes={"prompt_version": cfg.prompt_version},
            )
        )
        traces.log_transition(
            RLTransition(
                run_id=run_id,
                step=next_transition_step(),
                stage="reject",
                state={"user_input": user_input},
                action={"type": "reject", "reason": "empty input"},
                observation={"error": "empty input"},
                reward=0.0,
                done=True,
                status="rejected",
                attributes={"prompt_version": cfg.prompt_version},
            )
        )
        traces.finish_run(run_id, "", 0.0, 0, 0, status="rejected")
        return AgentResult(
            run_id=run_id,
            answer="",
            score=0.0,
            steps=step,
            status="rejected",
            error="empty input",
            prompt_version=cfg.prompt_version,
            rl_transition_count=transition_step,
        )

    try:
        if cfg.enable_memory:
            memory.add(
                f"User request: {user_input}",
                kind="working",
                salience=0.64,
                ttl_seconds=cfg.working_memory_ttl_seconds,
                source_run_id=run_id,
                meta={"stage": "user_input"},
            )

        traces.log(
            TraceEvent(
                run_id,
                next_step(),
                "understand",
                "input",
                input=user_input[:2000],
                attributes={"prompt_version": cfg.prompt_version},
            )
        )

        if cfg.enable_memory:
            with Timer() as t:
                memory_hits = memory.search(
                    user_input,
                    k=cfg.memory_search_k,
                    min_salience=cfg.memory_min_salience,
                )
            initial_pack = pack_context(
                user_input=user_input,
                memory_hits=memory_hits,
                tool_results=tool_results,
                critique=critique,
                prior_decisions=prior_decisions,
                budget_chars=cfg.context_char_budget,
                prompt_version=cfg.prompt_version,
            )
            traces.log(
                TraceEvent(
                    run_id,
                    next_step(),
                    "retrieve",
                    "memory",
                    input=user_input,
                    output={
                        "hits": [
                            {
                                "id": hit["id"],
                                "kind": hit["kind"],
                                "salience": hit["salience"],
                                "utility_score": hit.get("utility_score"),
                                "text": hit["text"][:240],
                            }
                            for hit in memory_hits
                        ],
                        "packed_context": initial_pack.summary(),
                    },
                    latency_ms=t.ms,
                    attributes={
                        "prompt_version": cfg.prompt_version,
                        "context_ids": initial_pack.included_ids,
                        "retrieval_candidates": initial_pack.retrieval_candidates,
                    },
                )
            )

        current_pack = pack_context(
            user_input=user_input,
            memory_hits=memory_hits,
            tool_results=tool_results,
            critique=critique,
            prior_decisions=prior_decisions,
            budget_chars=cfg.context_char_budget,
            prompt_version=cfg.prompt_version,
        )

        for iteration in range(cfg.max_steps):
            current_pack = pack_context(
                user_input=user_input,
                memory_hits=memory_hits,
                tool_results=tool_results,
                critique=critique,
                prior_decisions=prior_decisions,
                budget_chars=cfg.context_char_budget,
                prompt_version=cfg.prompt_version,
            )
            state = {
                "user_input": user_input,
                "iteration": iteration + 1,
                "context_ids": current_pack.included_ids,
                "retrieval_candidates": current_pack.retrieval_candidates,
                "tool_results": [
                    {
                        "tool": item.get("tool"),
                        "status": item.get("status"),
                        "observation_summary": item.get("observation_summary"),
                    }
                    for item in tool_results[-4:]
                ],
                "critique": critique[:300],
                "previous_score": score,
            }

            decision = _direct_answer(user_input) if not cfg.enable_planner else None
            if decision is None:
                with Timer() as t:
                    decision = await plan_next_step(
                        llm,
                        tools,
                        user_input,
                        current_pack.rendered,
                        tool_results,
                        critique,
                    )
                total_latency += t.ms
                prior_decisions.append(decision)
                traces.log(
                    TraceEvent(
                        run_id,
                        next_step(),
                        "plan",
                        "planner",
                        input={
                            "critique": critique,
                            "context_ids": current_pack.included_ids,
                            "ctx_chars": len(current_pack.rendered),
                        },
                        output=decision.as_dict(),
                        latency_ms=t.ms,
                        attributes={
                            "prompt_version": cfg.prompt_version,
                            "context_ids": current_pack.included_ids,
                            "retrieval_candidates": current_pack.retrieval_candidates,
                            "confidence": decision.confidence,
                            "stop_reason": decision.stop_reason,
                            "observation_summary": decision.observation_summary,
                        },
                    )
                )
                traces.log_transition(
                    RLTransition(
                        run_id=run_id,
                        step=next_transition_step(),
                        stage="plan",
                        state=state,
                        action=decision.as_dict(),
                        observation={"packed_context": current_pack.summary()},
                        reward=None,
                        done=False,
                        status="planned",
                        attributes={
                            "prompt_version": cfg.prompt_version,
                            "context_ids": current_pack.included_ids,
                        },
                    )
                )

            if decision.action == "call_tool" and cfg.enable_tools and decision.tool:
                with Timer() as t:
                    result = await tools.call(decision.tool, decision.tool_args or {})
                total_latency += t.ms
                tool_result = {
                    "tool": decision.tool,
                    "args": decision.tool_args,
                    "status": result["status"],
                    "output": result.get("output", ""),
                    "observation_summary": decision.observation_summary,
                    "iteration": iteration + 1,
                    "latency_ms": t.ms,
                }
                tool_results.append(tool_result)
                if cfg.enable_memory:
                    memory.add(
                        _tool_memory_text(decision.tool, decision.tool_args or {}, result),
                        kind="working",
                        salience=0.72 if result["status"] == "ok" else 0.44,
                        ttl_seconds=cfg.working_memory_ttl_seconds,
                        source_run_id=run_id,
                        tool_used=decision.tool,
                        meta={"status": result["status"], "args": decision.tool_args or {}},
                    )
                traces.log(
                    TraceEvent(
                        run_id,
                        next_step(),
                        "tool_call",
                        decision.tool,
                        input=decision.tool_args,
                        output=result,
                        latency_ms=t.ms,
                        error=result.get("error"),
                        attributes={
                            "prompt_version": cfg.prompt_version,
                            "context_ids": current_pack.included_ids,
                            "tool_latency_ms": t.ms,
                        },
                    )
                )
                traces.log_transition(
                    RLTransition(
                        run_id=run_id,
                        step=next_transition_step(),
                        stage="tool_result",
                        state=state,
                        action={"tool": decision.tool, "tool_args": decision.tool_args},
                        observation=result,
                        reward=0.1 if result["status"] == "ok" else -0.1,
                        done=False,
                        status=result["status"],
                        attributes={
                            "prompt_version": cfg.prompt_version,
                            "tool_latency_ms": t.ms,
                        },
                    )
                )
                continue

            answer = (decision.answer or "").strip()
            if not answer:
                with Timer() as t:
                    answer = await llm.complete(
                        f"{current_pack.rendered}\n\nUser: {user_input}\n\nAnswer concisely:",
                        system="Produce a grounded answer from the context packet.",
                    )
                total_latency += t.ms

            verification = score_answer_details(
                user_input,
                answer,
                current_pack.grounding_context,
                expected=expected,
            )
            score = float(verification["score"])
            if initial_score_value is None:
                initial_score_value = score
            reflection_delta = None
            if reflection_baseline is not None:
                reflection_delta = round(score - reflection_baseline, 4)
                reflection_gain += max(reflection_delta, 0.0)
            verifier_disagreement = bool(decision.confidence >= 0.7 and score < cfg.eval_pass_threshold)
            verification["verifier_disagreement"] = verifier_disagreement
            verification["reflection_delta"] = reflection_delta

            traces.log(
                TraceEvent(
                    run_id,
                    next_step(),
                    "verify",
                    "scorer",
                    input={"answer_len": len(answer), "context_ids": current_pack.included_ids},
                    output=verification,
                    attributes={
                        "prompt_version": cfg.prompt_version,
                        "context_ids": current_pack.included_ids,
                        "verifier_score": score,
                        "reflection_delta": reflection_delta,
                        "verifier_disagreement": verifier_disagreement,
                    },
                )
            )
            traces.log_transition(
                RLTransition(
                    run_id=run_id,
                    step=next_transition_step(),
                    stage="verify",
                    state=state,
                    action={"type": "answer", "answer": answer[:400], "confidence": decision.confidence},
                    observation=verification,
                    reward=score,
                    done=score >= cfg.eval_pass_threshold,
                    status="pass" if score >= cfg.eval_pass_threshold else "retry",
                    attributes={
                        "prompt_version": cfg.prompt_version,
                        "context_ids": current_pack.included_ids,
                    },
                )
            )

            if score >= cfg.eval_pass_threshold or not cfg.enable_reflection:
                break

            with Timer() as t:
                critique = await reflect(llm, user_input, answer, current_pack.grounding_context)
            total_latency += t.ms
            reflection_baseline = score
            traces.log(
                TraceEvent(
                    run_id,
                    next_step(),
                    "reflect",
                    "reflection",
                    input={"score": score},
                    output={"critique": critique[:400]},
                    latency_ms=t.ms,
                    attributes={
                        "prompt_version": cfg.prompt_version,
                        "context_ids": current_pack.included_ids,
                        "reflection_delta": 0.0,
                    },
                )
            )
            traces.log_transition(
                RLTransition(
                    run_id=run_id,
                    step=next_transition_step(),
                    stage="reflection",
                    state={"answer": answer[:400], "score": score, "critique": critique[:300]},
                    action={"retry": True, "reason": "score_below_threshold"},
                    observation={"next_iteration": iteration + 2},
                    reward=0.0,
                    done=False,
                    status="retry",
                    attributes={"prompt_version": cfg.prompt_version},
                )
            )

        if cfg.enable_memory:
            memory.add(
                f"Candidate answer: {answer}",
                kind="working",
                salience=0.58,
                ttl_seconds=cfg.working_memory_ttl_seconds,
                source_run_id=run_id,
                tool_used=tool_results[-1]["tool"] if tool_results else None,
                verifier_score=score,
                meta={"stage": "final_candidate"},
            )
            if score >= cfg.eval_pass_threshold and answer.strip():
                memory.promote_verified_fact(
                    user_input=user_input,
                    answer=answer,
                    run_id=run_id,
                    tool_used=tool_results[-1]["tool"] if tool_results else None,
                    verifier_score=score,
                    salience=max(0.7, score),
                    episodic_ttl_seconds=cfg.episodic_memory_ttl_seconds,
                )

        final_pack = pack_context(
            user_input=user_input,
            memory_hits=memory_hits,
            tool_results=tool_results,
            critique=critique,
            prior_decisions=prior_decisions,
            budget_chars=cfg.context_char_budget,
            prompt_version=cfg.prompt_version,
        )
        traces.log(
            TraceEvent(
                run_id,
                next_step(),
                "final",
                "answer",
                output={"answer": answer[:2000], "score": score},
                attributes={
                    "prompt_version": cfg.prompt_version,
                    "context_ids": final_pack.included_ids,
                    "verifier_score": score,
                },
            )
        )
        traces.log_transition(
            RLTransition(
                run_id=run_id,
                step=next_transition_step(),
                stage="final",
                state={"user_input": user_input},
                action={"type": "finalize"},
                observation={"answer": answer[:400], "score": score},
                reward=score,
                done=True,
                status="ok",
                attributes={"prompt_version": cfg.prompt_version},
            )
        )

        traces.finish_run(run_id, answer, score, total_latency, total_tokens, status="ok")
        return AgentResult(
            run_id=run_id,
            answer=answer,
            score=score,
            steps=step,
            tool_calls=tool_results,
            total_latency_ms=total_latency,
            total_tokens=total_tokens,
            memory_hits=[
                {
                    "id": hit["id"],
                    "kind": hit["kind"],
                    "salience": hit["salience"],
                    "utility_score": hit.get("utility_score"),
                }
                for hit in memory_hits
            ],
            context_ids=final_pack.included_ids,
            retrieval_candidates=final_pack.retrieval_candidates,
            reflection_count=transition_step_count("reflection", traces.get_run(run_id)),
            reflection_roi=round(reflection_gain, 4),
            rl_transition_count=transition_step,
            prompt_version=cfg.prompt_version,
            verification=verification,
            initial_score=initial_score_value or 0.0,
        )

    except Exception as e:
        traces.log(
            TraceEvent(
                run_id,
                next_step(),
                "error",
                "loop",
                error=str(e),
                attributes={"prompt_version": cfg.prompt_version},
            )
        )
        traces.log_transition(
            RLTransition(
                run_id=run_id,
                step=next_transition_step(),
                stage="error",
                state={"user_input": user_input},
                action={"type": "error"},
                observation={"error": str(e)},
                reward=-1.0,
                done=True,
                status="error",
                attributes={"prompt_version": cfg.prompt_version},
            )
        )
        traces.finish_run(run_id, answer, score, total_latency, total_tokens, status="error")
        return AgentResult(
            run_id=run_id,
            answer=answer,
            score=score,
            steps=step,
            status="error",
            error=str(e),
            memory_hits=memory_hits,
            prompt_version=cfg.prompt_version,
            rl_transition_count=transition_step,
            verification=verification,
            initial_score=initial_score_value or 0.0,
        )


def _direct_answer(user_input: str) -> PlanDecision:
    return PlanDecision(
        goal="Answer the user directly because planning is disabled.",
        action="answer",
        tool=None,
        tool_args={},
        rationale="planner disabled",
        observation_summary="Planning is disabled, so the runtime will ask the LLM directly.",
        confidence=0.2,
        stop_reason="planner_disabled",
        answer=None,
    )


def _tool_memory_text(tool_name: str, tool_args: dict, result: dict) -> str:
    return (
        f"Tool {tool_name} was called with args {tool_args}. "
        f"Status: {result.get('status')}. Output: {str(result.get('output'))[:500]}"
    )


def transition_step_count(stage: str, run: dict | None) -> int:
    if not run:
        return 0
    return sum(1 for item in run.get("transitions", []) if item.get("stage") == stage)

"""Core agent loop with tiered memory, context packing, and RL logging.

The public entry point is `run_agent`. It builds a per-call `_AgentRun`
that owns all of the mutable state (step counters, tool results, the
reflection counter, verification details, etc.) so the individual phases
can read/write fields directly instead of passing everything through
nonlocal closures.

The phases mirror a ReAct loop:

    _emit_understand -> _retrieve -> iterate(
        _plan -> _handle_tool_or_answer -> _verify -> _maybe_reflect
    ) -> _promote_if_trustworthy -> _finalize

Each phase is small enough to read in one sitting. The orchestration lives
in `run()` and the helpers below it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import Settings, settings as default_settings
from ..eval.reflection import reflect
from ..eval.scorer import llm_judge, score_answer_details
from ..llm.protocol import LLM
from ..memory.salience import (
    FINAL_CANDIDATE_SALIENCE,
    PROMOTED_FACT_SALIENCE_FLOOR,
    TOOL_RESULT_ERROR_SALIENCE,
    TOOL_RESULT_OK_SALIENCE,
    USER_INPUT_SALIENCE,
)
from ..memory.store import MemoryStore
from ..tools.registry import ToolRegistry
from .context_packer import PackedContext, pack_context
from .planner import PlanDecision, plan_next_step
from .trace import RunTransition, TraceEvent, TraceStore, Timer


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
    run_transition_count: int = 0
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
    run = _AgentRun(
        user_input=user_input,
        llm=llm,
        tools=tools,
        memory=memory,
        traces=traces,
        cfg=config or default_settings,
        expected=expected,
    )
    return await run.run()


class _AgentRun:
    """One invocation of the agent loop.

    Holds every piece of mutable state the phases mutate (step counters,
    accumulated tool results, scoreboard values, reflection counter).
    Phases are methods on this class rather than nested closures so each
    one is small enough to read and test in isolation.
    """

    def __init__(
        self,
        *,
        user_input: str,
        llm: LLM,
        tools: ToolRegistry,
        memory: MemoryStore,
        traces: TraceStore,
        cfg: Settings,
        expected: dict | None,
    ) -> None:
        self.user_input = user_input
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.traces = traces
        self.cfg = cfg
        self.expected = expected

        self.run_id = traces.start_run(
            user_input,
            cfg.profile,
            cfg.describe()["flags"],
            prompt_version=cfg.prompt_version,
        )

        self._step = 0
        self._transition_step = 0

        self.tool_results: list[dict] = []
        self.prior_decisions: list[PlanDecision] = []
        self.memory_hits: list[dict] = []
        self.critique = ""
        self.answer = ""
        self.score = 0.0
        self.initial_score_value: float | None = None
        self.reflection_gain = 0.0
        self.reflection_count = 0
        self.reflection_baseline: float | None = None
        self.verification: dict[str, Any] = {}
        self.total_latency = 0
        self.total_tokens = 0
        self.current_pack: PackedContext | None = None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    async def run(self) -> AgentResult:
        if not self.user_input or not self.user_input.strip():
            return self._finalize_rejected()

        try:
            self._stash_user_input()
            self._emit_understand()
            self._retrieve()
            self.current_pack = self._pack()

            for iteration in range(self.cfg.max_steps):
                self.current_pack = self._pack()
                decision = await self._plan(iteration)
                if await self._maybe_run_tool(decision, iteration):
                    continue
                await self._produce_answer(decision)
                await self._verify(decision, iteration)
                if (
                    self.score >= self.cfg.eval_pass_threshold 
                    or not self.cfg.enable_reflection
                    or not self.cfg.enable_llm_judge
                ):
                    break
                await self._reflect()

            self._promote_if_trustworthy()
            final_pack = self._pack()
            return self._finalize_ok(final_pack)

        except Exception as exc:
            return self._finalize_error(exc)

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    def _next_step(self) -> int:
        self._step += 1
        return self._step

    def _next_transition(self) -> int:
        self._transition_step += 1
        return self._transition_step

    def _pack(self) -> PackedContext:
        return pack_context(
            user_input=self.user_input,
            memory_hits=self.memory_hits,
            tool_results=self.tool_results,
            critique=self.critique,
            prior_decisions=self.prior_decisions,
            budget_chars=self.cfg.context_char_budget,
            prompt_version=self.cfg.prompt_version,
            developer_ratio=self.cfg.context_developer_ratio,
            scratchpad_ratio=self.cfg.context_scratchpad_ratio,
            tool_ratio=self.cfg.context_tool_ratio,
        )

    def _current_state(self, iteration: int) -> dict[str, Any]:
        pack = self.current_pack
        return {
            "user_input": self.user_input,
            "iteration": iteration + 1,
            "context_ids": pack.included_ids if pack else [],
            "retrieval_candidates": pack.retrieval_candidates if pack else [],
            "tool_results": [
                {
                    "tool": item.get("tool"),
                    "status": item.get("status"),
                    "observation_summary": item.get("observation_summary"),
                }
                for item in self.tool_results[-4:]
            ],
            "critique": self.critique[:300],
            "previous_score": self.score,
        }

    # ------------------------------------------------------------------
    # Phase: empty-input rejection
    # ------------------------------------------------------------------
    def _finalize_rejected(self) -> AgentResult:
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "error",
                "input",
                error="empty input",
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="reject",
                state={"user_input": self.user_input},
                action={"type": "reject", "reason": "empty input"},
                observation={"error": "empty input"},
                score=0.0,
                done=True,
                status="rejected",
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )
        self.traces.finish_run(self.run_id, "", 0.0, 0, 0, status="rejected")
        return AgentResult(
            run_id=self.run_id,
            answer="",
            score=0.0,
            steps=self._step,
            status="rejected",
            error="empty input",
            prompt_version=self.cfg.prompt_version,
            run_transition_count=self._transition_step,
        )

    # ------------------------------------------------------------------
    # Phase: understand / retrieve
    # ------------------------------------------------------------------
    def _stash_user_input(self) -> None:
        if not self.cfg.enable_memory:
            return
        self.memory.add(
            f"User request: {self.user_input}",
            kind="working",
            salience=USER_INPUT_SALIENCE,
            ttl_seconds=self.cfg.working_memory_ttl_seconds,
            source_run_id=self.run_id,
            meta={"stage": "user_input"},
        )

    def _emit_understand(self) -> None:
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "understand",
                "input",
                input=self.user_input[:2000],
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )

    def _retrieve(self) -> None:
        if not self.cfg.enable_memory:
            return
        with Timer() as t:
            self.memory_hits = self.memory.search(
                self.user_input,
                k=self.cfg.memory_search_k,
                min_salience=self.cfg.memory_min_salience,
            )
        initial_pack = self._pack()
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "retrieve",
                "memory",
                input=self.user_input,
                output={
                    "hits": [
                        {
                            "id": hit["id"],
                            "kind": hit["kind"],
                            "salience": hit["salience"],
                            "utility_score": hit.get("utility_score"),
                            "text": hit["text"][:240],
                        }
                        for hit in self.memory_hits
                    ],
                    "packed_context": initial_pack.summary(),
                },
                latency_ms=t.ms,
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": initial_pack.included_ids,
                    "retrieval_candidates": initial_pack.retrieval_candidates,
                },
            )
        )

    # ------------------------------------------------------------------
    # Phase: plan
    # ------------------------------------------------------------------
    async def _plan(self, iteration: int) -> PlanDecision:
        if not self.cfg.enable_planner:
            return _direct_answer()

        with Timer() as t:
            decision = await plan_next_step(
                self.llm,
                self.tools,
                self.user_input,
                self.current_pack.rendered,
                self.tool_results,
                self.critique,
            )
        self.total_latency += t.ms
        self.prior_decisions.append(decision)

        pack = self.current_pack
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "plan",
                "planner",
                input={
                    "critique": self.critique,
                    "context_ids": pack.included_ids,
                    "ctx_chars": len(pack.rendered),
                },
                output=decision.as_dict(),
                latency_ms=t.ms,
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": pack.included_ids,
                    "retrieval_candidates": pack.retrieval_candidates,
                    "confidence": decision.confidence,
                    "stop_reason": decision.stop_reason,
                    "observation_summary": decision.observation_summary,
                },
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="plan",
                state=self._current_state(iteration),
                action=decision.as_dict(),
                observation={"packed_context": pack.summary()},
                score=None,
                done=False,
                status="planned",
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": pack.included_ids,
                },
            )
        )
        return decision

    # ------------------------------------------------------------------
    # Phase: tool dispatch
    # ------------------------------------------------------------------
    async def _maybe_run_tool(self, decision: PlanDecision, iteration: int) -> bool:
        if not (decision.action == "call_tool" and self.cfg.enable_tools and decision.tool):
            return False

        with Timer() as t:
            result = await self.tools.call(
                decision.tool, 
                decision.tool_args or {},
                context={"memory": self.memory, "config": self.cfg}
            )
        self.total_latency += t.ms

        tool_result = {
            "tool": decision.tool,
            "args": decision.tool_args,
            "status": result["status"],
            "output": result.get("output", ""),
            "observation_summary": decision.observation_summary,
            "iteration": iteration + 1,
            "latency_ms": t.ms,
        }
        self.tool_results.append(tool_result)

        if self.cfg.enable_memory:
            self.memory.add(
                _tool_memory_text(decision.tool, decision.tool_args or {}, result),
                kind="working",
                salience=(
                    TOOL_RESULT_OK_SALIENCE
                    if result["status"] == "ok"
                    else TOOL_RESULT_ERROR_SALIENCE
                ),
                ttl_seconds=self.cfg.working_memory_ttl_seconds,
                source_run_id=self.run_id,
                tool_used=decision.tool,
                meta={"status": result["status"], "args": decision.tool_args or {}},
            )

        pack = self.current_pack
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "tool_call",
                decision.tool,
                input=decision.tool_args,
                output=result,
                latency_ms=t.ms,
                error=result.get("error"),
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": pack.included_ids,
                    "tool_latency_ms": t.ms,
                },
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="tool_result",
                state=self._current_state(iteration),
                action={"tool": decision.tool, "tool_args": decision.tool_args},
                observation=result,
                score=0.1 if result["status"] == "ok" else -0.1,
                done=False,
                status=result["status"],
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "tool_latency_ms": t.ms,
                },
            )
        )
        return True

    # ------------------------------------------------------------------
    # Phase: answer
    # ------------------------------------------------------------------
    async def _produce_answer(self, decision: PlanDecision) -> None:
        self.answer = (decision.answer or "").strip()
        if self.answer:
            return
        with Timer() as t:
            self.answer = await self.llm.complete(
                f"{self.current_pack.rendered}\n\nUser: {self.user_input}\n\nAnswer concisely:",
                system="Produce a grounded answer from the context packet.",
            )
        self.total_latency += t.ms

    # ------------------------------------------------------------------
    # Phase: verify
    # ------------------------------------------------------------------
    async def _verify(self, decision: PlanDecision, iteration: int) -> None:
        pack = self.current_pack
        verification = score_answer_details(
            self.user_input,
            self.answer,
            pack.grounding_context,
            expected=self.expected,
        )
        # Kick the LLM judge in for live (no-ground-truth) runs when the
        # heuristic is all we have and the operator opted in.
        if (
            verification["mode"] == "heuristic"
            and self.cfg.enable_llm_judge
            and self.expected is None
        ):
            verification = await llm_judge(
                self.llm,
                self.user_input,
                self.answer,
                pack.grounding_context,
            )
        self._apply_verification(decision, verification, iteration)
        self._log_verification(decision, verification, iteration)

    def _apply_verification(
        self, decision: PlanDecision, verification: dict[str, Any], iteration: int,
    ) -> None:
        """Pure business-logic side of verification: update scores and state."""
        self.score = float(verification["score"])
        if self.initial_score_value is None:
            self.initial_score_value = self.score

        reflection_delta = None
        if self.reflection_baseline is not None:
            reflection_delta = round(self.score - self.reflection_baseline, 4)
            self.reflection_gain += max(reflection_delta, 0.0)

        verifier_disagreement = bool(
            decision.confidence >= 0.7 and self.score < self.cfg.eval_pass_threshold
        )
        verification["verifier_disagreement"] = verifier_disagreement
        verification["reflection_delta"] = reflection_delta
        self.verification = verification

    def _log_verification(
        self, decision: PlanDecision, verification: dict[str, Any], iteration: int,
    ) -> None:
        """Observability side of verification: emit trace event + RL transition."""
        pack = self.current_pack
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "verify",
                "scorer",
                input={"answer_len": len(self.answer), "context_ids": pack.included_ids},
                output=verification,
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": pack.included_ids,
                    "verifier_score": self.score,
                    "reflection_delta": verification.get("reflection_delta"),
                    "verifier_disagreement": verification.get("verifier_disagreement", False),
                },
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="verify",
                state=self._current_state(iteration=iteration),
                action={
                    "type": "answer",
                    "answer": self.answer[:400],
                    "confidence": decision.confidence,
                },
                observation=verification,
                score=self.score,
                done=self.score >= self.cfg.eval_pass_threshold,
                status="pass" if self.score >= self.cfg.eval_pass_threshold else "retry",
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": pack.included_ids,
                },
            )
        )

    # ------------------------------------------------------------------
    # Phase: reflect
    # ------------------------------------------------------------------
    async def _reflect(self) -> None:
        pack = self.current_pack
        with Timer() as t:
            self.critique = await reflect(
                self.llm,
                self.user_input,
                self.answer,
                pack.grounding_context,
            )
        self.total_latency += t.ms
        self.reflection_baseline = self.score
        self.reflection_count += 1

        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "reflect",
                "reflection",
                input={"score": self.score},
                output={"critique": self.critique[:400]},
                latency_ms=t.ms,
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": pack.included_ids,
                    "reflection_delta": 0.0,
                },
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="reflection",
                state={
                    "answer": self.answer[:400],
                    "score": self.score,
                    "critique": self.critique[:300],
                },
                action={"retry": True, "reason": "score_below_threshold"},
                observation={"next_iteration": len(self.prior_decisions) + 1},
                score=0.0,
                done=False,
                status="retry",
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )

    # ------------------------------------------------------------------
    # Phase: promotion
    # ------------------------------------------------------------------
    def _promote_if_trustworthy(self) -> None:
        if not self.cfg.enable_memory:
            return

        self.memory.add(
            f"Candidate answer: {self.answer}",
            kind="working",
            salience=FINAL_CANDIDATE_SALIENCE,
            ttl_seconds=self.cfg.working_memory_ttl_seconds,
            source_run_id=self.run_id,
            tool_used=self.tool_results[-1]["tool"] if self.tool_results else None,
            verifier_score=self.score,
            meta={"stage": "final_candidate"},
        )

        if (
            self.score >= self.cfg.eval_pass_threshold
            and self.answer.strip()
            and self.verification.get("trustworthy")
        ):
            self.memory.promote_verified_fact(
                user_input=self.user_input,
                answer=self.answer,
                run_id=self.run_id,
                tool_used=self.tool_results[-1]["tool"] if self.tool_results else None,
                verifier_score=self.score,
                salience=max(PROMOTED_FACT_SALIENCE_FLOOR, self.score),
                episodic_ttl_seconds=self.cfg.episodic_memory_ttl_seconds,
            )
            self.memory.record_experience(
                user_input=self.user_input,
                plan=[p.goal for p in self.prior_decisions if getattr(p, "goal", None)],
                tool_calls=[t["tool"] for t in self.tool_results],
                answer=self.answer,
                run_id=self.run_id,
                verifier_score=self.score,
            )
        elif self.score < self.cfg.eval_pass_threshold:
            self.memory.record_failure(
                user_input=self.user_input,
                plan=[p.goal for p in self.prior_decisions if getattr(p, "goal", None)],
                tool_calls=[t["tool"] for t in self.tool_results],
                error_or_answer=self.answer or "Exhausted retries without verified answer",
                run_id=self.run_id,
                score=self.score,
            )

    # ------------------------------------------------------------------
    # Phase: finalize (ok / error)
    # ------------------------------------------------------------------
    def _finalize_ok(self, final_pack: PackedContext) -> AgentResult:
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "final",
                "answer",
                output={"answer": self.answer[:2000], "score": self.score},
                attributes={
                    "prompt_version": self.cfg.prompt_version,
                    "context_ids": final_pack.included_ids,
                    "verifier_score": self.score,
                },
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="final",
                state={"user_input": self.user_input},
                action={"type": "finalize"},
                observation={"answer": self.answer[:400], "score": self.score},
                score=self.score,
                done=True,
                status="ok",
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )
        self.traces.finish_run(
            self.run_id,
            self.answer,
            self.score,
            self.total_latency,
            self.total_tokens,
            status="ok",
        )
        return AgentResult(
            run_id=self.run_id,
            answer=self.answer,
            score=self.score,
            steps=self._step,
            tool_calls=self.tool_results,
            total_latency_ms=self.total_latency,
            total_tokens=self.total_tokens,
            memory_hits=[
                {
                    "id": hit["id"],
                    "kind": hit["kind"],
                    "salience": hit["salience"],
                    "utility_score": hit.get("utility_score"),
                }
                for hit in self.memory_hits
            ],
            context_ids=final_pack.included_ids,
            retrieval_candidates=final_pack.retrieval_candidates,
            reflection_count=self.reflection_count,
            reflection_roi=round(self.reflection_gain, 4),
            run_transition_count=self._transition_step,
            prompt_version=self.cfg.prompt_version,
            verification=self.verification,
            initial_score=self.initial_score_value or 0.0,
        )

    def _finalize_error(self, exc: Exception) -> AgentResult:
        self.traces.log(
            TraceEvent(
                self.run_id,
                self._next_step(),
                "error",
                "loop",
                error=str(exc),
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )
        self.traces.log_transition(
            RunTransition(
                run_id=self.run_id,
                step=self._next_transition(),
                stage="error",
                state={"user_input": self.user_input},
                action={"type": "error"},
                observation={"error": str(exc)},
                score=-1.0,
                done=True,
                status="error",
                attributes={"prompt_version": self.cfg.prompt_version},
            )
        )
        self.traces.finish_run(
            self.run_id,
            self.answer,
            self.score,
            self.total_latency,
            self.total_tokens,
            status="error",
        )
        return AgentResult(
            run_id=self.run_id,
            answer=self.answer,
            score=self.score,
            steps=self._step,
            status="error",
            error=str(exc),
            memory_hits=self.memory_hits,
            prompt_version=self.cfg.prompt_version,
            run_transition_count=self._transition_step,
            verification=self.verification,
            initial_score=self.initial_score_value or 0.0,
        )


# ----------------------------------------------------------------------
# Public stateless helpers
# ----------------------------------------------------------------------

def _direct_answer() -> PlanDecision:
    """Synthetic PlanDecision used when the planner is disabled."""
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

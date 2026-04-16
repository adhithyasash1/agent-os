"""Planner for the ReAct-style agent loop."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..llm.protocol import LLM
from ..tools.registry import ToolRegistry


@dataclass
class PlanDecision:
    goal: str = ""
    action: str = "answer"  # "call_tool" | "answer"
    tool: str | None = None
    tool_args: dict = field(default_factory=dict)
    rationale: str = ""
    observation_summary: str = ""
    confidence: float = 0.0
    stop_reason: str = ""
    answer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "action": self.action,
            "tool": self.tool,
            "tool_args": self.tool_args,
            "rationale": self.rationale,
            "observation_summary": self.observation_summary,
            "confidence": self.confidence,
            "stop_reason": self.stop_reason,
            "answer": self.answer,
        }


PLANNER_PROMPT = """You are the planner for a local agent runtime.
Think in a ReAct-style loop: goal -> action -> observation -> answer.

Available tools:
{tool_list}

Context packet:
{context}

Prior tool results:
{tool_results}

Prior critique:
{critique}

User request: {user_input}

Respond in JSON only with this schema:
{{
  "goal": "<what must be solved right now>",
  "action": "call_tool" | "answer",
  "tool": "<tool_name or null>",
  "tool_args": {{...}},
  "rationale": "<brief reason for the action>",
  "observation_summary": "<what you expect to learn or what you already learned>",
  "confidence": <float 0..1>,
  "stop_reason": "<why this step should stop and hand off>",
  "answer": "<final answer if action=answer, else null>"
}}

Rules:
- Use "call_tool" only when a tool is clearly necessary.
- Prefer grounded answers from the supplied context packet when possible.
- Keep confidence honest.
- If you answer directly, set stop_reason to why another tool or step is unnecessary.
"""


async def plan_next_step(
    llm: LLM,
    tools: ToolRegistry,
    user_input: str,
    context: str,
    tool_results: list[dict],
    critique: str = "",
) -> PlanDecision:
    tool_list = tools.describe() or "(no tools enabled)"
    prompt = PLANNER_PROMPT.format(
        tool_list=tool_list,
        context=context[:4000] or "(none)",
        tool_results=_summarize_tool_results(tool_results),
        critique=critique or "(none)",
        user_input=user_input,
    )
    raw = await llm.complete(prompt, system="You output only valid JSON.")
    return _parse_decision(raw)


def _summarize_tool_results(results: list[dict]) -> str:
    if not results:
        return "(none)"
    out = []
    for r in results[-5:]:
        status = r.get("status", "?")
        tool = r.get("tool", "?")
        summary = str(r.get("output", ""))[:300]
        out.append(f"- {tool} [{status}]: {summary}")
    return "\n".join(out)


def _parse_decision(raw: str) -> PlanDecision:
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return PlanDecision(
                goal=str(data.get("goal") or "").strip(),
                action=str(data.get("action") or "answer").strip() or "answer",
                tool=data.get("tool") or None,
                tool_args=data.get("tool_args") or {},
                rationale=str(data.get("rationale") or "").strip(),
                observation_summary=str(data.get("observation_summary") or "").strip(),
                confidence=_as_confidence(data.get("confidence")),
                stop_reason=str(data.get("stop_reason") or "").strip(),
                answer=data.get("answer"),
            )
        except json.JSONDecodeError:
            pass
    return PlanDecision(
        goal="Answer the user directly.",
        action="answer",
        tool=None,
        tool_args={},
        rationale="planner parser fallback",
        observation_summary="No structured planner output was available.",
        confidence=0.2,
        stop_reason="fallback_to_plain_answer",
        answer=text,
    )


def _as_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0

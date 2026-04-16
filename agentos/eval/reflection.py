"""Optional reflection step.

Given the current answer and context, asks the LLM for a short critique that
the planner will feed back in on the next iteration.
"""
from __future__ import annotations

REFLECTION_PROMPT = """Review the answer below. Identify specific issues
(missing facts, unsupported claims, wrong tool selection). Keep the critique
to 1-3 sentences.

User request: {user_input}
Context:
{context}

Answer:
{answer}

Critique:"""


async def reflect(llm, user_input: str, answer: str, context: str) -> str:
    prompt = REFLECTION_PROMPT.format(
        user_input=user_input,
        context=(context or "(none)")[:1500],
        answer=answer[:1500],
    )
    try:
        return (await llm.complete(prompt, system="You are a brief critic.")).strip()[:500]
    except Exception as e:
        return f"(reflection unavailable: {e})"

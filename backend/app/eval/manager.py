"""
Evaluation Manager — LLM Council pattern: critique-then-score.

Instead of the same model rating its own output (self-grading),
we force a two-step process inspired by Karpathy's LLM Council:

  1. CRITIQUE: The LLM acts as a skeptical reviewer, listing specific
     flaws, missing information, and factual concerns.
  2. SCORE: Based on the critique, assign a 0.0-1.0 score.

This forces the model to identify weaknesses before assigning a number,
producing more honest and calibrated evaluations.
"""

import re
import logging
from app.core.llm import get_llm

logger = logging.getLogger("agentos.eval")

_eval_llm = None


def _get_eval_llm():
    global _eval_llm
    if _eval_llm is None:
        _eval_llm = get_llm()
    return _eval_llm


async def evaluate_response(
    input_text: str,
    actual_output: str,
    retrieval_context: list,
) -> tuple[float, str]:
    """Score a response using the critique-then-score pattern.

    Returns:
        (score, critique) — score is 0.0-1.0, critique is a text summary
        of strengths and weaknesses.
    """
    if not actual_output or not actual_output.strip():
        return 0.0, "Empty response — nothing to evaluate."

    # Filter out empty context strings
    context_text = "\n".join(c for c in retrieval_context if c and c.strip())

    # --- Step 1: Critique (peer review phase) ---
    critique_prompt = (
        "You are a SKEPTICAL REVIEWER. Your job is to find flaws.\n"
        "Examine whether the RESPONSE adequately answers the QUESTION.\n\n"
        "Check for:\n"
        "- Does it actually answer what was asked?\n"
        "- Are there factual claims that aren't supported by the context?\n"
        "- Is important information missing?\n"
        "- Is it clear and well-structured?\n"
        "- Does it hallucinate or make things up?\n\n"
        f"QUESTION: {input_text[:500]}\n\n"
        f"RESPONSE: {actual_output[:1500]}\n\n"
    )
    if context_text:
        critique_prompt += f"AVAILABLE CONTEXT:\n{context_text[:1000]}\n\n"

    critique_prompt += (
        "Write 2-4 bullet points about the response's strengths AND weaknesses. "
        "Be specific and honest. If the response is good, say so. "
        "If it has problems, name them."
    )

    try:
        llm = _get_eval_llm()
        critique_result = await llm.ainvoke(critique_prompt)
        critique = critique_result.content.strip()
    except Exception as e:
        logger.error(f"Critique generation failed: {e}")
        critique = "Unable to generate critique."

    # --- Step 2: Score (informed by the critique) ---
    score_prompt = (
        "Based on the critique below, rate the response quality from 0.0 to 1.0.\n\n"
        "Scoring guide:\n"
        "- 0.0-0.3: Wrong, irrelevant, or empty\n"
        "- 0.4-0.6: Partially answers but has significant gaps\n"
        "- 0.7-0.8: Good answer with minor issues\n"
        "- 0.9-1.0: Excellent, comprehensive answer\n\n"
        f"QUESTION: {input_text[:300]}\n\n"
        f"CRITIQUE:\n{critique[:800]}\n\n"
        "Return ONLY a number between 0.0 and 1.0 on the first line. "
        "Nothing else."
    )

    try:
        score_result = await llm.ainvoke(score_prompt)
        score_text = score_result.content.strip()
        score = _parse_score(score_text)
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        score = 0.0

    # Truncate critique for storage
    critique_short = critique[:500] if critique else "No critique generated."
    logger.info(f"  Eval: score={score:.2f}, critique={critique_short[:80]}...")

    return score, critique_short


def _parse_score(text: str) -> float:
    """Extract a float 0.0-1.0 from text, robust to model quirks."""
    # Find any float-like number in the first line
    first_line = text.split("\n")[0].strip()
    matches = re.findall(r"(\d+\.?\d*)", first_line)
    for m in matches:
        val = float(m)
        if 0.0 <= val <= 1.0:
            return val
        if 1 < val <= 10:
            return val / 10.0  # model returned 0-10 scale
        if 10 < val <= 100:
            return val / 100.0  # model returned percentage
    # If first line had no valid score, try full text
    matches = re.findall(r"(\d+\.?\d*)", text)
    for m in matches:
        val = float(m)
        if 0.0 <= val <= 1.0:
            return val
    return 0.0

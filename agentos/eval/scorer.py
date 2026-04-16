"""Scoring for agent answers.

Two modes:

- `expected`: used only in benchmarks when tasks carry `expected_contains` /
  `expected_status` / `expected_refusal`. Dead-simple string checks, fully
  reproducible.
- `heuristic`: fallback used in live runs when we don't know the ground truth.
  This is a **weak signal** — grounding overlap and refusal detection only.
  It is NOT used to decide whether to promote facts to durable memory.
- `llm-judge`: optional. Asks the LLM to rate factual accuracy and grounding
  against the retrieved context on a 0-1 scale. This is what actually gates
  memory promotion when enabled.

The heuristic scorer deliberately no longer awards a "length bonus" — the
earlier version rewarded verbose answers regardless of correctness, which
was biasing both the reflection trigger and the memory promotion gate.
"""
from __future__ import annotations

import json
import re
from typing import Any


REFUSAL_PHRASES = (
    "i don't know",
    "i cannot",
    "i'm unable",
    "i was unable",
    "i do not have",
    "i encountered an error",
    "i don't have enough information",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def score_expected(answer: str, expected: dict | None) -> float | None:
    """Benchmark-time scoring. Returns None when no expectation given."""
    if not expected:
        return None

    if expected.get("expected_status"):
        status = _norm(expected["expected_status"])
        hay = _norm(answer)
        return 1.0 if status and status in hay else 0.0

    if expected.get("expected_refusal") is True:
        hay = _norm(answer)
        return 1.0 if any(phrase in hay for phrase in REFUSAL_PHRASES) else 0.0

    contains = expected.get("expected_contains") or []
    if not contains:
        return 1.0 if answer.strip() else 0.0
    hay = _norm(answer)
    hits = sum(1 for c in contains if _norm(str(c)) in hay)
    return hits / len(contains)


def score_answer_details(
    user_input: str,
    answer: str,
    context: str,
    expected: dict | None = None,
) -> dict:
    """Synchronous, always-available scoring.

    Prefers `expected` if supplied; otherwise falls back to a conservative
    heuristic that is explicitly **not** a promotion gate on its own.
    """
    g = score_expected(answer, expected)
    if g is not None:
        return {
            "score": g,
            "mode": "expected",
            "grounding_overlap": 0.0,
            "refusal_detected": False,
            "trustworthy": True,
        }

    if not answer or not answer.strip():
        return {
            "score": 0.0,
            "mode": "heuristic",
            "grounding_overlap": 0.0,
            "refusal_detected": False,
            "trustworthy": False,
        }

    norm = _norm(answer)
    refusal_detected = any(p in norm for p in REFUSAL_PHRASES)
    if refusal_detected:
        return {
            "score": 0.3,
            "mode": "heuristic",
            "grounding_overlap": 0.0,
            "refusal_detected": True,
            "trustworthy": False,
        }

    overlap = 0.0
    if context:
        ctx_words = {w for w in re.findall(r"[A-Za-z0-9]{4,}", context.lower())}
        ans_words = {w for w in re.findall(r"[A-Za-z0-9]{4,}", norm)}
        if ctx_words:
            overlap = len(ctx_words & ans_words) / max(len(ctx_words), 1)

    # Conservative heuristic: 0.4 floor + bounded grounding bonus. No
    # length reward. Max without ground-truth evidence is 0.6.
    score = 0.4 + min(0.2, overlap * 2.0)

    return {
        "score": max(0.0, min(1.0, round(score, 4))),
        "mode": "heuristic",
        "grounding_overlap": round(overlap, 4),
        "refusal_detected": False,
        # Heuristic scores are never a standalone gate for promotion.
        "trustworthy": False,
    }


def score_answer(user_input: str, answer: str, context: str,
                 expected: dict | None = None) -> float:
    return float(score_answer_details(user_input, answer, context, expected=expected)["score"])


_JUDGE_SYSTEM = (
    "You are a strict grader. You rate assistant answers on two axes: "
    "factual correctness (is the answer accurate?) and grounding (is it "
    "supported by the provided context, or at minimum plausible given "
    "common knowledge?). Respond ONLY with valid JSON."
)

_JUDGE_PROMPT = """User request:
{user_input}

Retrieved context (may be empty):
{context}

Candidate answer:
{answer}

Return JSON with this exact shape:
{{"correct": <float 0..1>, "grounded": <float 0..1>, "reason": "<short>"}}

Scoring:
- 1.0 for clearly correct and directly supported.
- 0.6-0.8 for mostly correct but partial or weakly grounded.
- 0.3-0.5 for partially right / mixed.
- 0.0-0.2 for wrong, hallucinated, or dodging.
Respond in JSON only.
"""


async def llm_judge(
    llm: Any,
    user_input: str,
    answer: str,
    context: str,
) -> dict:
    """Ask the LLM to rate correctness + grounding. Returns a details dict.

    Fails soft: if the LLM is unavailable or emits malformed JSON, returns
    a heuristic result with `trustworthy=False` so callers don't
    accidentally promote to durable memory on a judge error.
    """
    if not answer or not answer.strip():
        return score_answer_details(user_input, answer, context)

    prompt = _JUDGE_PROMPT.format(
        user_input=user_input[:2000],
        context=(context or "(empty)")[:3000],
        answer=answer[:2000],
    )
    try:
        raw = await llm.complete(prompt, system=_JUDGE_SYSTEM)
    except Exception as exc:
        details = score_answer_details(user_input, answer, context)
        details["judge_error"] = str(exc)[:200]
        return details

    parsed = _parse_judge_json(raw)
    if parsed is None:
        details = score_answer_details(user_input, answer, context)
        details["judge_error"] = "unparseable judge response"
        details["judge_raw"] = (raw or "")[:240]
        return details

    correct = _clamp_unit(parsed.get("correct"))
    grounded = _clamp_unit(parsed.get("grounded"))
    score = round(0.7 * correct + 0.3 * grounded, 4)
    return {
        "score": score,
        "mode": "llm-judge",
        "judge_correct": correct,
        "judge_grounded": grounded,
        "judge_reason": str(parsed.get("reason", ""))[:300],
        "grounding_overlap": 0.0,
        "refusal_detected": False,
        # Only trust the judge when both sub-scores agree the answer is
        # at least passable. Otherwise don't promote.
        "trustworthy": correct >= 0.7 and grounded >= 0.5,
    }


def _parse_judge_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    # Strip common code-fence wrappers.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, count=1).strip()
        if text.endswith("```"):
            text = text[: -3].strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _clamp_unit(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))

"""Local scoring without requiring an LLM call."""
from __future__ import annotations

import re


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
    g = score_expected(answer, expected)
    if g is not None:
        return {
            "score": g,
            "mode": "expected",
            "grounding_overlap": 0.0,
            "refusal_detected": False,
            "fabrication_markers": [],
            "length_bonus": 0.0,
        }

    if not answer or not answer.strip():
        return {
            "score": 0.0,
            "mode": "heuristic",
            "grounding_overlap": 0.0,
            "refusal_detected": False,
            "fabrication_markers": [],
            "length_bonus": 0.0,
        }

    norm = _norm(answer)
    refusal_detected = any(p in norm for p in REFUSAL_PHRASES)
    if refusal_detected:
        return {
            "score": 0.3,
            "mode": "heuristic",
            "grounding_overlap": 0.0,
            "refusal_detected": True,
            "fabrication_markers": [],
            "length_bonus": 0.0,
        }

    score = 0.5
    overlap = 0.0
    if context:
        ctx_words = {w for w in re.findall(r"[A-Za-z0-9]{4,}", context.lower())}
        ans_words = {w for w in re.findall(r"[A-Za-z0-9]{4,}", norm)}
        if ctx_words:
            overlap = len(ctx_words & ans_words) / max(len(ctx_words), 1)
            score += min(0.3, overlap * 3)

    length_bonus = 0.1 if 40 <= len(answer) <= 2000 else 0.0
    score += length_bonus

    fab_markers = ["lorem ipsum", "placeholder", "as an ai language model"]
    triggered_markers = [marker for marker in fab_markers if marker in norm]
    if triggered_markers:
        score -= 0.2

    return {
        "score": max(0.0, min(1.0, score)),
        "mode": "heuristic",
        "grounding_overlap": round(overlap, 4),
        "refusal_detected": False,
        "fabrication_markers": triggered_markers,
        "length_bonus": length_bonus,
    }


def score_answer(user_input: str, answer: str, context: str,
                 expected: dict | None = None) -> float:
    return float(score_answer_details(user_input, answer, context, expected=expected)["score"])

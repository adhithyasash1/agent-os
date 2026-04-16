"""Deterministic mock LLM."""
from __future__ import annotations

import json
import re


class MockLLM:
    def __init__(self):
        self._calls = 0

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self._calls += 1
        p = prompt.lower()

        if "respond in json only" in p and "observation_summary" in p and "confidence" in p:
            return self._plan(prompt)

        if "critique" in p and ("answer" in p or "response" in p):
            return "The answer is a bit thin. Ground it more clearly in the available context."

        return self._direct_answer(prompt)

    def _plan(self, prompt: str) -> str:
        user_line = self._extract_user(prompt)
        user = user_line.lower()
        tool_section = _extract_section(prompt, "Prior tool results:", ("Prior critique:", "User request:"))
        has_prior_tool = tool_section.strip() not in ("(none)", "")

        if not has_prior_tool and _looks_like_arithmetic_request(user_line) and "calculator" in prompt:
            expr_match = re.search(r"[\d\s\+\-\*/\(\)\.]+", user_line)
            return json.dumps({
                "goal": "Compute the arithmetic result accurately.",
                "action": "call_tool",
                "tool": "calculator",
                "tool_args": {"expression": (expr_match.group(0) if expr_match else user_line).strip()},
                "rationale": "Arithmetic was detected and the calculator is safer than guessing.",
                "observation_summary": "Get the numeric result from the calculator.",
                "confidence": 0.92,
                "stop_reason": "Need the tool result before answering.",
                "answer": None,
            })

        url_match = re.search(r"https?://\S+", user_line)
        if not has_prior_tool and url_match and "http_fetch" in prompt:
            return json.dumps({
                "goal": "Fetch the page the user referenced.",
                "action": "call_tool",
                "tool": "http_fetch",
                "tool_args": {"url": url_match.group(0)},
                "rationale": "The answer depends on a URL that should be fetched.",
                "observation_summary": "Retrieve the page body for grounding.",
                "confidence": 0.88,
                "stop_reason": "Need the HTTP response before answering.",
                "answer": None,
            })

        if has_prior_tool:
            out_match = re.search(r"ok.*?:\s*(.+)", tool_section, re.IGNORECASE)
            tool_out = (out_match.group(1).strip() if out_match else tool_section.strip())[:220]
            return json.dumps({
                "goal": "Answer the user with the observed tool result.",
                "action": "answer",
                "tool": None,
                "tool_args": {},
                "rationale": "A relevant tool result is already available.",
                "observation_summary": tool_out,
                "confidence": 0.9,
                "stop_reason": "The tool result is sufficient to answer.",
                "answer": f"The result is {tool_out}.",
            })

        answer = self._direct_answer(user_line)
        if answer.startswith("I don't have enough"):
            ctx = _extract_section(prompt, "Context packet:", ("Prior tool results:", "Prior critique:", "User request:"))
            if ctx and ctx not in ("(none)", "(empty)"):
                candidate = _best_grounded_context_line(ctx)
                if candidate:
                    answer = candidate
        return json.dumps({
            "goal": "Answer the user from existing knowledge or retrieved context.",
            "action": "answer",
            "tool": None,
            "tool_args": {},
            "rationale": "The answer can be produced without another tool call.",
            "observation_summary": "Use the strongest matching context available.",
            "confidence": 0.62 if "don't have enough" not in answer.lower() else 0.34,
            "stop_reason": "No additional tool call is necessary.",
            "answer": answer,
        })

    def _extract_user(self, prompt: str) -> str:
        m = re.search(r"user request:\s*(.*)", prompt, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).split("\n")[0].strip()
        m = re.search(r"user:\s*(.*)", prompt, re.IGNORECASE)
        if m:
            return m.group(1).split("\n")[0].strip()
        return prompt.strip()[:500]

    def _direct_answer(self, prompt: str) -> str:
        q = self._extract_user(prompt).lower()
        table = {
            "capital of france": "The capital of France is Paris.",
            "binary search": "Binary search runs in O(log n) time.",
            "list and a tuple": "Lists are mutable; tuples are immutable in Python.",
            "acid": "ACID stands for Atomicity, Consistency, Isolation, and Durability.",
            "rest api": "A REST API exposes resources over HTTP using standard verbs.",
            "supervised": "Supervised learning uses labeled data, while unsupervised learning does not.",
            "median": "Sorted: 1, 2, 4, 5, 7, 8, 9. Median is 5.",
            "probability both are red": "3/10, which is 0.3 or 30%.",
            "answer to life": "42.",
            "center": "5.",
            "37 a prime": "37 is prime.",
        }
        for key, val in table.items():
            if key in q:
                return val
        return "I don't have enough information to answer confidently."


def _extract_section(prompt: str, header: str, next_headers: tuple[str, ...]) -> str:
    next_pattern = "|".join(re.escape(item) for item in next_headers)
    pattern = rf"(?ims)^{re.escape(header)}\s*(.*?)(?=^(?:{next_pattern})|\Z)"
    match = re.search(pattern, prompt)
    return match.group(1).strip() if match else ""


def _best_grounded_context_line(context: str) -> str:
    durable_memory_lines: list[str] = []
    tool_lines: list[str] = []
    in_memory_block = False
    capture_memory = False
    in_tool_block = False
    for line in context.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("<memory"):
            in_memory_block = True
            kind_match = re.search(r'kind="([^"]+)"', cleaned, re.IGNORECASE)
            kind = (kind_match.group(1).lower() if kind_match else "working")
            capture_memory = kind in {"episodic", "semantic"}
            continue
        if cleaned.startswith("</memory>"):
            in_memory_block = False
            capture_memory = False
            continue
        if cleaned.startswith("<tool_observation"):
            in_tool_block = True
            continue
        if cleaned.startswith("</tool_observation>"):
            in_tool_block = False
            continue
        if in_memory_block and capture_memory:
            durable_memory_lines.append(cleaned[:400])
            continue
        if in_tool_block and ":" in cleaned:
            label, value = cleaned.split(":", 1)
            if label.lower() in {"summary", "output"} and value.strip():
                tool_lines.append(value.strip()[:400])
    if durable_memory_lines:
        return durable_memory_lines[0]
    if tool_lines:
        return tool_lines[0]
    return ""


def _looks_like_arithmetic_request(user_line: str) -> bool:
    user = user_line.lower()
    if "calculate" in user:
        return True
    if any(word in user for word in ("sentence", "sentences", "version", "step")):
        return False
    expr = re.search(r"\b\d+\s*[\+\*/]\s*\d+", user)
    if expr:
        return True
    if re.search(r"\b\d+\s*-\s*\d+\b", user) and any(word in user for word in ("result", "equals", "what is")):
        return True
    return False

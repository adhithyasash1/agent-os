"""Context packing for the agent loop.

The packer turns a large, messy candidate set into a bounded context payload.
It keeps developer instructions stable, then budgets the remaining space across
retrieved memory, live tool observations, and a compressed scratchpad.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re
import json


DEFAULT_DEVELOPER_INSTRUCTIONS = """
You are agentos-core, a grounded local-first agent runtime.
Prefer verified context over guesses.
Use tools when they are clearly necessary.
Assume the environment is highly dynamic: if a past memory indicates a tool failed or had a limitation, YOU MUST ATTEMPT TO USE THE TOOL AGAIN ANYWAY. Do not assume past failures are permanent.
When the context is thin, say so directly instead of inventing facts.
Keep the final answer concise and useful.
""".strip()


# Fallback budget ratios when callers don't thread a Settings through.
# Kept in sync with the defaults on `agentos.config.Settings` so the two
# paths match. Changing production behavior should be done via env vars,
# Default ratios used when not provided by settings.
# Aligned with Settings defaults in config.py.
DEFAULT_DEVELOPER_RATIO = 0.15
DEFAULT_SCRATCHPAD_RATIO = 0.15
DEFAULT_TOOL_RATIO = 0.40


@dataclass
class ContextChunk:
    chunk_id: str
    section: str
    text: str
    utility: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class PackedContext:
    prompt_version: str
    rendered: str
    grounding_context: str
    included_ids: list[str]
    candidate_ids: list[str]
    retrieval_candidates: list[str]
    section_sizes: dict[str, int]
    chunk_count: int

    def summary(self) -> dict[str, Any]:
        return {
            "prompt_version": self.prompt_version,
            "included_ids": self.included_ids,
            "candidate_ids": self.candidate_ids,
            "retrieval_candidates": self.retrieval_candidates,
            "section_sizes": self.section_sizes,
            "chunk_count": self.chunk_count,
        }


def pack_context(
    *,
    user_input: str,
    memory_hits: list[dict],
    tool_results: list[dict],
    critique: str,
    prior_decisions: list[Any],
    budget_chars: int,
    prompt_version: str,
    developer_instructions: str | None = None,
    failed_attempts: list[dict] | None = None,
    developer_ratio: float = DEFAULT_DEVELOPER_RATIO,
    scratchpad_ratio: float = DEFAULT_SCRATCHPAD_RATIO,
    tool_ratio: float = DEFAULT_TOOL_RATIO,
    is_research_task: bool | None = None,
) -> PackedContext:
    budget = max(1200, int(budget_chars or 0))
    developer_text = (developer_instructions or DEFAULT_DEVELOPER_INSTRUCTIONS).strip()
    research_task = _is_research_task(user_input) if is_research_task is None else is_research_task

    # Dynamic Budgeting: if research-heavy task, rebalance for tools.
    if research_task:
        tool_ratio = 0.6
        # Re-verify sum
        scratchpad_ratio = 0.12 # slightly compress scratchpad
        developer_ratio = 0.14 # slightly compress dev instructions
    
    ratio_sum = developer_ratio + scratchpad_ratio + tool_ratio
    if ratio_sum >= 1.0:
        raise ValueError(
            f"Context budget ratios sum to {ratio_sum:.2f} (developer={developer_ratio}, "
            f"scratchpad={scratchpad_ratio}, tool={tool_ratio}). "
            f"They must sum to less than 1.0 to leave room for retrieved memory."
        )

    developer_budget = min(4000, max(420, int(budget * developer_ratio)))
    scratchpad_budget = min(10000, max(280, int(budget * scratchpad_ratio)))
    tool_budget = min(80000, max(0, int(budget * tool_ratio)))
    memory_budget = max(320, budget - developer_budget - scratchpad_budget - tool_budget - 180)

    import logging
    logging.getLogger("agentos").info(
        "Packing context: total=%d dev=%d scratch=%d tool=%d memory=%d",
        budget, developer_budget, scratchpad_budget, tool_budget, memory_budget
    )
    developer_chunk = ContextChunk(
        chunk_id="developer:instructions",
        section="developer_instructions",
        text=_truncate(developer_text, developer_budget),
        utility=99.0,
        meta={"stable": True},
    )

    memory_chunks = []
    experience_chunks = []
    semantic_chunks = []
    
    for hit in memory_hits:
        chunk = ContextChunk(
            chunk_id=f"memory:{hit['id']}",
            section="retrieved_memory",
            text=_memory_chunk_text(hit),
            utility=float(hit.get("utility_score") or 0.0),
            meta={
                "kind": hit.get("kind"),
                "salience": hit.get("salience"),
                "source_run_id": hit.get("source_run_id"),
            },
        )
        # Is this a semantic hit?
        if "semantic_similarity" in hit:
            chunk.section = "relevant_context_(semantic_retrieval)"
            semantic_chunks.append(chunk)
        elif hit.get("kind") == "experience":
            chunk.section = "past_successful_examples"
            experience_chunks.append(chunk)
        else:
            memory_chunks.append(chunk)

    tool_chunks = []
    for item in tool_results[-6:]:
        tool_chunks.append(
            ContextChunk(
                chunk_id=f"tool:{item.get('iteration', len(tool_chunks) + 1)}:{item.get('tool', 'unknown')}",
                section="live_tool_observations",
                text=_tool_chunk_text(item),
                utility=_tool_utility(item),
                meta={
                    "status": item.get("status"), 
                    "tool": item.get("tool"),
                    "raw_output": _prepare_truncation_input(item.get("output")),
                },
            )
        )

    scratchpad_text = _compress_scratchpad(critique, prior_decisions, tool_results, scratchpad_budget)
    scratchpad_chunk = ContextChunk(
        chunk_id="scratchpad:summary",
        section="compressed_scratchpad",
        text=scratchpad_text,
        utility=0.55 if scratchpad_text else 0.0,
        meta={"has_critique": bool(critique.strip())},
    )

    chosen_memory = _fit_chunks(memory_chunks, memory_budget)
    
    # Conditionally inject examples and semantic matches if under budget limits
    available_exp_budget = memory_budget - sum(len(c.text) for c in chosen_memory)
    chosen_experience = _fit_chunks(experience_chunks, max(available_exp_budget, 1000))[:2]
    
    available_sem_budget = available_exp_budget - sum(len(c.text) for c in chosen_experience)
    chosen_semantic = _fit_chunks(semantic_chunks, max(available_sem_budget, 800))[:3]
    
    chosen_tools = _fit_chunks(tool_chunks, tool_budget)
    chosen_scratchpad = [scratchpad_chunk] if scratchpad_text else []

    # Negative Signal Injection: Pass previous failed syntheses back as context.
    failed_chunk = None
    if failed_attempts:
        failed_text = _render_failed_attempts(failed_attempts)
        if failed_text:
            failed_chunk = ContextChunk(
                chunk_id="fails:history",
                section="previous_failed_attempts",
                text=failed_text,
                utility=0.9, # High utility to ensure it's included
            )

    # Recency Positioning: Tools are rendered last so they are closest to the prompt.
    included = [developer_chunk]
    if failed_chunk:
        included.append(failed_chunk)
    included.extend([*chosen_experience, *chosen_semantic, *chosen_memory, *chosen_scratchpad, *chosen_tools])
    
    rendered = _render_context(included)
    grounding = _render_context([*chosen_memory, *chosen_semantic, *chosen_tools, *chosen_scratchpad])

    return PackedContext(
        prompt_version=prompt_version,
        rendered=rendered[:budget],
        grounding_context=grounding[: max(400, budget - developer_budget)],
        included_ids=[chunk.chunk_id for chunk in included],
        candidate_ids=[chunk.chunk_id for chunk in [*memory_chunks, *tool_chunks, scratchpad_chunk] if chunk.text],
        retrieval_candidates=[chunk.chunk_id for chunk in memory_chunks],
        section_sizes=_section_sizes(included),
        chunk_count=len(included),
    )


def _fit_chunks(chunks: list[ContextChunk], budget: int) -> list[ContextChunk]:
    if budget <= 0:
        return []
    selected: list[ContextChunk] = []
    remaining = budget
    sorted_chunks = sorted(chunks, key=lambda item: item.utility, reverse=True)
    for i, chunk in enumerate(sorted_chunks):
        text = chunk.text.strip()
        if not text:
            continue
        
        # High-utility chunks (like fresh tool results) can claim 
        # up to 85% of the remaining budget to prevent accidental 
        # information loss of critical signal.
        fair_share = remaining // max(len(sorted_chunks) - i, 1)
        if chunk.utility > 0.7:
            max_per_chunk = min(remaining, max(fair_share, int(remaining * 0.85)))
        else:
            max_per_chunk = min(remaining, max(220, fair_share))
            
        # Use intelligent truncation which handles lists better than 
        # simple character slicing.
        output_data = chunk.meta.get("raw_output")
        if output_data:
            clipped = _intelligent_truncate(output_data, max_per_chunk)
            if len(clipped) < 20:
                clipped = _truncate(text, max_per_chunk)
        else:
            clipped = _truncate(text, max_per_chunk)
            
        if len(clipped) < 20:
            continue
            
        selected.append(ContextChunk(chunk.chunk_id, chunk.section, clipped, chunk.utility, chunk.meta))
        remaining -= len(clipped)
        if remaining <= 100:
            break
    return selected


def _memory_chunk_text(hit: dict) -> str:
    header = (
        f"<memory id=\"memory:{hit.get('id')}\" kind=\"{hit.get('kind', 'working')}\" "
        f"salience=\"{hit.get('salience', 0.0):.2f}\">"
    )
    footer = "</memory>"
    return f"{header}\n{(hit.get('text') or '').strip()}\n{footer}"


def _tool_chunk_text(item: dict) -> str:
    output = item.get("output")
    # We pass the raw output in meta so _fit_chunks can use _intelligent_truncate
    return (
        f"<tool_observation tool=\"{item.get('tool', 'unknown')}\" status=\"{item.get('status', '?')}\">\n"
        f"Summary: {(item.get('observation_summary') or 'No summary provided.').strip()}\n"
        f"Output: {str(output)[:1000]}... (Full output will be fitted by ContextPacker)\n"
        f"</tool_observation>"
    )


def _tool_utility(item: dict) -> float:
    status_bonus = 0.18 if item.get("status") == "ok" else 0.05
    freshness_bonus = 0.12 if item.get("iteration", 0) >= 1 else 0.0
    return round(0.52 + status_bonus + freshness_bonus, 3)


def _compress_scratchpad(
    critique: str,
    prior_decisions: list[Any],
    tool_results: list[dict],
    budget: int,
) -> str:
    lines: list[str] = []
    if critique.strip():
        lines.append(f"- Critique: {critique.strip()[:260]}")
    for decision in prior_decisions[-3:]:
        goal = getattr(decision, "goal", "") or "No explicit goal."
        action = getattr(decision, "action", "answer")
        stop_reason = getattr(decision, "stop_reason", "") or "not provided"
        lines.append(f"- Prior plan: action={action}; goal={goal[:120]}; stop_reason={stop_reason[:90]}")
    for tool in tool_results[-2:]:
        lines.append(
            f"- Observation: tool={tool.get('tool')} status={tool.get('status')} "
            f"summary={(tool.get('observation_summary') or '').strip()[:120]}"
        )
    if not lines:
        return ""
    text = "\n".join(lines)
    return _truncate(text, budget)


def _render_context(chunks: list[ContextChunk]) -> str:
    sections: dict[str, list[str]] = {}
    for chunk in chunks:
        sections.setdefault(chunk.section, []).append(chunk.text.strip())
    rendered: list[str] = []
    for section, values in sections.items():
        rendered.append(f"## {section.replace('_', ' ').title()}")
        rendered.extend(values)
        rendered.append("")
    return "\n".join(rendered).strip()


def _section_sizes(chunks: list[ContextChunk]) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for chunk in chunks:
        sizes[chunk.section] = sizes.get(chunk.section, 0) + len(chunk.text)
    return sizes


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: max(limit - 3, 0)].rstrip()
    return f"{clipped}..."


def _intelligent_truncate(data: Any, limit: int) -> str:
    """The 2026 Golden Rule: Breadth over Depth.
    
    For lists, we use Head-Middle-Tail (HMT) slicing to ensure deterministic
    coverage of the boundaries and a representative sample of the middle.
    """
    if isinstance(data, dict) and data.get("__prepared_output__"):
        if data["kind"] == "list":
            data = data["value"]
        else:
            return _truncate(data["value"], limit)

    if not isinstance(data, list):
        return _truncate(json.dumps(data) if not isinstance(data, str) else data, limit)
    
    if not data:
        return "[]"
        
    # Guard: No slicing needed if we're under the item count limit.
    # We estimate 120 chars per item overhead for safety.
    item_limit = max(3, limit // 120)
    if len(data) <= item_limit:
        return json.dumps(data)
        
    return _hmt_slice(data, item_limit)


def _hmt_slice(data: list, limit: int) -> str:
    """Deterministic Head-Middle-Tail slicing."""
    if len(data) <= limit:
        return json.dumps(data)
        
    # Head: 20% (min 1)
    # Tail: 20% (min 1)
    head_count = max(1, int(limit * 0.2))
    tail_count = max(1, int(limit * 0.2))
    middle_count = limit - head_count - tail_count
    
    if middle_count <= 0:
        # Fallback for very small limits
        return json.dumps(data[:limit-1] + ["... omitted ..."] + [data[-1]])

    head = data[:head_count]
    tail = data[-tail_count:]
    
    # Middle: Periodic sampling
    middle_pool = data[head_count:-tail_count]
    if len(middle_pool) <= middle_count:
        middle = middle_pool
    else:
        # Stride sampling
        stride = len(middle_pool) / middle_count
        middle = [middle_pool[int(i * stride)] for i in range(middle_count)]
        
    combined = head + ["... [SNIP] ..."] + middle + ["... [SNIP] ..."] + tail
    return json.dumps(combined)


def _prepare_truncation_input(data: Any) -> Any:
    if isinstance(data, list):
        return {"__prepared_output__": True, "kind": "list", "value": data}
    if isinstance(data, str):
        return {"__prepared_output__": True, "kind": "text", "value": data}
    try:
        rendered = json.dumps(data)
    except Exception:
        rendered = str(data)
    return {"__prepared_output__": True, "kind": "text", "value": rendered}

def _is_research_task(user_input: str) -> bool:
    """Robust regex-based research task classifier."""
    patterns = [
        r"\b(research|compare|summarize|analyze|contrast|technical|find and analyze)\b",
        r"\b(what are the top|tell me about|how does.*compare)\b"
    ]
    is_match = any(re.search(p, user_input.lower()) for p in patterns)
    
    # Negation check: if user says "don't summarize", ignore research task boost
    negations = [r"\b(don't|do not|skip|no need to)\s+(summarize|compare|research|analyze)\b"]
    if any(re.search(n, user_input.lower()) for n in negations):
        return False
        
    return is_match


def _render_failed_attempts(attempts: list[dict]) -> str:
    """Render previous failed syntheses and their critiques. 
    Capped at 2000 chars to protect the context window.
    """
    if not attempts:
        return ""
    
    out = ["## PREVIOUS FAILED ATTEMPTS\n(Do not repeat these errors:)\n"]
    for i, attempt in enumerate(attempts[-3:]): # Only last 3 attempts
        entry = (
            f"### Attempt {i+1}\n"
            f"Answer: {attempt.get('answer', '')[:400]}...\n"
            f"Critique: {attempt.get('critique', '')}\n"
        )
        out.append(entry)
        
    # Hard cap at 2000 chars
    full_text = "\n".join(out)
    if len(full_text) > 2000:
        return full_text[:1997] + "..."
    return full_text


import json
import re

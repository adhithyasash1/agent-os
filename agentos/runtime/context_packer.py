"""Context packing for the agent loop.

The packer turns a large, messy candidate set into a bounded context payload.
It keeps developer instructions stable, then budgets the remaining space across
retrieved memory, live tool observations, and a compressed scratchpad.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_DEVELOPER_INSTRUCTIONS = """
You are agentos-core, a grounded local-first agent runtime.
Prefer verified context over guesses.
Use tools when they are clearly necessary.
When the context is thin, say so directly instead of inventing facts.
Keep the final answer concise and useful.
""".strip()


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
) -> PackedContext:
    budget = max(1200, int(budget_chars or 0))
    developer_text = (developer_instructions or DEFAULT_DEVELOPER_INSTRUCTIONS).strip()

    developer_budget = min(1400, max(420, int(budget * 0.18)))
    scratchpad_budget = min(1200, max(280, int(budget * 0.16)))
    tool_budget = min(2400, max(0, int(budget * 0.28)))
    memory_budget = max(320, budget - developer_budget - scratchpad_budget - tool_budget - 180)

    developer_chunk = ContextChunk(
        chunk_id="developer:instructions",
        section="developer_instructions",
        text=_truncate(developer_text, developer_budget),
        utility=99.0,
        meta={"stable": True},
    )

    memory_chunks = [
        ContextChunk(
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
        for hit in memory_hits
    ]

    tool_chunks = []
    for item in tool_results[-6:]:
        tool_chunks.append(
            ContextChunk(
                chunk_id=f"tool:{item.get('iteration', len(tool_chunks) + 1)}:{item.get('tool', 'unknown')}",
                section="live_tool_observations",
                text=_tool_chunk_text(item),
                utility=_tool_utility(item),
                meta={"status": item.get("status"), "tool": item.get("tool")},
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
    chosen_tools = _fit_chunks(tool_chunks, tool_budget)
    chosen_scratchpad = [scratchpad_chunk] if scratchpad_text else []

    included = [developer_chunk, *chosen_memory, *chosen_tools, *chosen_scratchpad]
    rendered = _render_context(included)
    grounding = _render_context([*chosen_memory, *chosen_tools, *chosen_scratchpad])

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
    for chunk in sorted(chunks, key=lambda item: item.utility, reverse=True):
        text = chunk.text.strip()
        if not text:
            continue
        max_per_chunk = min(remaining, max(220, budget // max(len(chunks), 1)))
        clipped = _truncate(text, max_per_chunk)
        if len(clipped) < 40:
            continue
        selected.append(ContextChunk(chunk.chunk_id, chunk.section, clipped, chunk.utility, chunk.meta))
        remaining -= len(clipped)
        if remaining <= 140:
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
    output_text = output if isinstance(output, str) else str(output)
    return (
        f"<tool_observation tool=\"{item.get('tool', 'unknown')}\" status=\"{item.get('status', '?')}\">\n"
        f"Summary: {(item.get('observation_summary') or 'No summary provided.').strip()}\n"
        f"Output: {output_text[:700]}\n"
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

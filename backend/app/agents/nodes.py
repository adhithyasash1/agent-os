"""
Agent nodes — planner, executor, evaluator, memory manager.

Tier A improvements applied:
  1. SimpleMem pattern   → 3-tier memory retrieval + context budget management
  2. LLM Council pattern → critique-then-score evaluator
  3. EdgeQuake pattern   → GraphRAG-lite retrieval via Neo4j in planner
  4. FlashRank reranker  → cross-encoder reranking after vector retrieval
"""

import re
import asyncio
import logging
from typing import Dict, Any
from app.core.llm import get_llm
from app.core.config import settings
from app.agents.state import AgentState
from langchain_core.messages import SystemMessage, AIMessage
from langfuse import observe
from app.eval.manager import evaluate_response
from app.memory.hybrid import memory
from app.core.tasks import log_trajectory
from app.tools.tavily_tool import tavily_search, tavily_extract
from app.tools.browser_tool import browse_url
from app.tools.mcp_servers import match_servers, list_mcp_tools, call_mcp_tool

logger = logging.getLogger("agentos.nodes")

llm = get_llm()


# ---------------------------------------------------------------------------
# Planner — now queries all 3 memory tiers (SimpleMem + EdgeQuake patterns)
# ---------------------------------------------------------------------------

@observe()
async def planner_node(state: AgentState) -> Dict[str, Any]:
    iteration = state.get("iteration", 0) + 1
    logger.info(f"PLANNING (iteration {iteration})")
    messages = state["messages"]
    user_query = messages[-1].content if messages else ""

    # --- 3-tier memory retrieval (run in parallel) ---
    vector_task = _retrieve_vector(user_query)
    episodic_task = _retrieve_episodic(user_query)
    graph_task = _retrieve_graph(user_query)

    vector_ctx, episodic_ctx, graph_ctx = await asyncio.gather(
        vector_task, episodic_task, graph_task
    )

    # --- Collect tool outputs from executor ---
    tool_context = _build_tool_context(state.get("tool_outputs", []))

    # --- Context budget management (SimpleMem pattern) ---
    budget = settings.CONTEXT_BUDGET_CHARS
    context_sections = []
    total_chars = 0

    # Priority order: tool data > graph > episodic > vector
    for label, text in [
        ("Tool Results", tool_context),
        ("Graph Memory (related entities & past tasks)", graph_ctx),
        ("Past Experiences", episodic_ctx),
        ("Related Knowledge", vector_ctx),
    ]:
        if text and total_chars < budget:
            remaining = budget - total_chars
            trimmed = text[:remaining]
            context_sections.append(f"--- {label} ---\n{trimmed}")
            total_chars += len(trimmed)

    # --- Build system prompt ---
    system_parts = [
        "You are AgentOS, a helpful AI assistant with web search, browsing, and MCP tool capabilities.",
        "You have access to: Tavily (web search/extract), Excel, GitHub, HuggingFace, TradingView, and Markdownify tools.",
        "Answer the user's question directly and concisely using the provided data.",
    ]

    if context_sections:
        system_parts.append(
            "Below is context retrieved from your tools and memory. "
            "Use it to ground your answer in facts:\n\n"
            + "\n\n".join(context_sections)
        )

    # If we're on a retry iteration and got a low score, include the critique
    prev_critique = state.get("eval_critique", "")
    if iteration > 1 and prev_critique:
        system_parts.append(
            f"Your previous answer was critiqued. Address these issues:\n{prev_critique}"
        )

    system_msg = SystemMessage(content="\n".join(system_parts))

    # --- Call LLM with retry ---
    response = await _invoke_with_retry(llm, [system_msg] + list(messages))

    # Guard against empty response
    content = response.content
    if not content or not content.strip():
        content = "I was unable to generate a response. Please try rephrasing your question."
        response = AIMessage(content=content)

    return {
        "current_plan": content,
        "memory_context": vector_ctx,
        "episodic_context": episodic_ctx,
        "graph_context": graph_ctx,
        "messages": [response],
        "iteration": iteration,
        "context_chars": total_chars,
    }


async def _retrieve_vector(query: str) -> str:
    """Tier 1: Chroma vector similarity search + FlashRank reranking.

    Fetches 3x candidates, reranks with cross-encoder, keeps top-k.
    """
    try:
        from app.tools.reranker import rerank

        # Fetch more candidates than needed for reranking
        fetch_k = settings.VECTOR_SEARCH_K * settings.RERANK_FETCH_MULTIPLIER
        docs = await memory.vector_store.asimilarity_search(query, k=fetch_k)
        if not docs:
            return ""

        texts = [doc.page_content for doc in docs]

        # Rerank with cross-encoder (falls back to original order if unavailable)
        reranked = rerank(query, texts, top_k=settings.VECTOR_SEARCH_K)
        return "\n".join(reranked)
    except Exception as e:
        logger.warning(f"Vector search skipped: {e}")
    return ""


async def _retrieve_episodic(query: str) -> str:
    """Tier 2: Mem0 episodic memory — past successful interactions."""
    try:
        episodes = await memory.search_episodes(query, limit=settings.EPISODIC_SEARCH_K)
        if episodes:
            return "\n".join(
                f"- {ep['content']}" for ep in episodes if ep.get("content")
            )
    except Exception as e:
        logger.warning(f"Episodic search skipped: {e}")
    return ""


async def _retrieve_graph(query: str) -> str:
    """Tier 3: Neo4j graph traversal — entity relationships (EdgeQuake pattern).

    Prefers compiled truth summaries when available, falls back to raw
    task intents for entities that haven't been compiled yet.
    """
    try:
        graph_results = await memory.search_graph(query, limit=settings.GRAPH_SEARCH_K)
        if graph_results:
            lines = []
            seen_entities = set()
            for r in graph_results:
                if r.get("type") == "graph":
                    entity = r.get("entity", "?")
                    compiled = r.get("compiled_truth", "")

                    # Prefer compiled truth — one clean sentence per entity
                    if compiled and entity not in seen_entities:
                        lines.append(f"[{entity}] {compiled}")
                        seen_entities.add(entity)
                    else:
                        # Fallback to raw traversal data
                        parts = [f"Entity: {entity}"]
                        if r.get("related_task"):
                            parts.append(f"used in: \"{r['related_task'][:100]}\"")
                        if r.get("tools_used"):
                            parts.append(f"tools: {', '.join(r['tools_used'])}")
                        if r.get("related_entities"):
                            parts.append(f"related to: {', '.join(r['related_entities'][:5])}")
                        lines.append(" | ".join(parts))
                elif r.get("type") == "task":
                    lines.append(
                        f"Past task (score {r.get('score', 0):.1f}): {r.get('intent', '')[:100]}"
                    )
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Graph search skipped: {e}")
    return ""


def _build_tool_context(tool_outputs: list) -> str:
    """Build context string from executor tool outputs with truncation."""
    parts = []
    for t in tool_outputs:
        if t.get("status") != "success":
            continue
        if t.get("content"):
            source = t.get("url") or t.get("tool", "")
            parts.append(f"[{source}]\n{t['content'][:settings.TOOL_OUTPUT_MAX_CHARS]}")
        if t.get("results"):
            parts.append("Search Results:")
            for r in t["results"]:
                parts.append(
                    f"- [{r['title']}]({r['url']})\n  {r['content'][:settings.SEARCH_RESULT_PREVIEW]}"
                )
        if t.get("mcp_result"):
            parts.append(f"[{t['tool']}]\n{t['mcp_result'][:settings.MCP_RESULT_MAX_CHARS]}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Executor — orchestrates Tavily, browser, and MCP tools
# ---------------------------------------------------------------------------

@observe()
async def executor_node(state: AgentState) -> Dict[str, Any]:
    logger.info("EXECUTING")
    plan = state.get("current_plan", "")
    user_input = state["messages"][0].content if state["messages"] else ""
    combined_text = f"{user_input}\n{plan}"
    combined_lower = combined_text.lower()
    tool_outputs = []

    # --- 1. URL extraction (Tavily first, Playwright fallback) ---
    urls = re.findall(r"https?://[^\s\"'>)\]]+", combined_text)
    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    # Run URL extractions in parallel
    if urls:
        url_tasks = [_extract_url(url) for url in urls[:2]]
        url_results = await asyncio.gather(*url_tasks, return_exceptions=True)
        for result in url_results:
            if isinstance(result, dict):
                tool_outputs.append(result)

    # --- 2. Web search via Tavily ---
    search_triggers = [
        "search", "find", "latest", "news", "recent",
        "what is", "who is", "how to", "tell me about",
    ]
    if any(kw in combined_lower for kw in search_triggers):
        search_query = re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", user_input)).strip()
        if search_query:
            logger.info(f"  Searching: {search_query[:80]}")
            try:
                results = await tavily_search(search_query, max_results=5)
                tool_outputs.append({
                    "tool": "tavily_search", "query": search_query,
                    "status": "success", "results": results,
                })
            except Exception as e:
                tool_outputs.append({
                    "tool": "tavily_search", "query": search_query,
                    "status": "error", "error": str(e),
                })

    # --- 3. MCP servers (parallel dispatch) ---
    matched = match_servers(combined_text)
    if matched:
        mcp_tasks = [_call_mcp_server(name, combined_text, combined_lower) for name in matched]
        mcp_results = await asyncio.gather(*mcp_tasks, return_exceptions=True)
        for result in mcp_results:
            if isinstance(result, dict):
                tool_outputs.append(result)

    if not tool_outputs:
        tool_outputs.append({"tool": "none", "status": "success", "info": "No tools required."})

    return {"tool_outputs": tool_outputs}


async def _extract_url(url: str) -> dict:
    """Extract content from URL: Tavily first, Playwright fallback."""
    logger.info(f"  Extracting: {url}")
    try:
        content = await tavily_extract(url)
        if content and len(content) > 100:
            return {
                "tool": "tavily_extract", "url": url,
                "status": "success",
                "content": content[:settings.TOOL_OUTPUT_MAX_CHARS],
            }
        raise ValueError("Insufficient content from Tavily extract")
    except Exception:
        try:
            content = await browse_url(url)
            return {
                "tool": "browse_url", "url": url,
                "status": "success",
                "content": content[:settings.TOOL_OUTPUT_MAX_CHARS],
            }
        except Exception as e2:
            return {
                "tool": "browse_url", "url": url,
                "status": "error", "error": str(e2),
            }


async def _call_mcp_server(server_name: str, text: str, text_lower: str) -> dict:
    """Connect to an MCP server, pick the best tool, call it."""
    logger.info(f"  MCP matched: {server_name}")
    try:
        tools = await list_mcp_tools(server_name)
        if tools:
            best_tool = _pick_best_tool(tools, text_lower)
            if best_tool:
                logger.info(f"  Calling: {server_name}/{best_tool['name']}")
                result = await call_mcp_tool(
                    server_name, best_tool["name"], _build_args(best_tool, text)
                )
                return {
                    "tool": f"mcp:{server_name}/{best_tool['name']}",
                    "status": "success",
                    "mcp_result": str(result)[:settings.MCP_RESULT_MAX_CHARS],
                }
    except Exception as e:
        return {
            "tool": f"mcp:{server_name}",
            "status": "error", "error": str(e),
        }
    return {"tool": f"mcp:{server_name}", "status": "error", "error": "No tools found"}


def _pick_best_tool(tools: list[dict], query: str) -> dict | None:
    """Heuristic tool selection: weighted keyword overlap + description scoring."""
    best, best_score = None, 0
    query_words = set(query.split())
    for t in tools:
        desc = (t.get("description") or "").lower()
        name = (t.get("name") or "").lower()
        # Name match is worth 3x description match
        name_overlap = len(query_words & set(name.replace("_", " ").split())) * 3
        desc_overlap = len(query_words & set(desc.split()))
        score = name_overlap + desc_overlap
        if score > best_score:
            best, best_score = t, score
    return best if best_score > 0 else (tools[0] if tools else None)


def _build_args(tool: dict, text: str) -> dict:
    """Build minimal arguments for a tool call based on the query context."""
    args = {}
    name = tool.get("name", "").lower()
    if "search" in name or "query" in name:
        clean = re.sub(r"https?://\S+", "", text).strip()
        args["query"] = clean[:200]
    if "url" in name or "webpage" in name:
        urls = re.findall(r"https?://[^\s\"'>)\]]+", text)
        if urls:
            args["url"] = urls[0]
    if "symbol" in name or "ticker" in name:
        tickers = re.findall(r"\b[A-Z]{1,5}\b", text)
        if tickers:
            args["symbol"] = tickers[0]
    return args


# ---------------------------------------------------------------------------
# Evaluator — LLM Council pattern: critique-then-score
# ---------------------------------------------------------------------------

@observe()
async def evaluator_node(state: AgentState) -> Dict[str, Any]:
    logger.info("EVALUATING")
    iteration = state.get("iteration", 1)
    last_message = state["messages"][-1].content
    initial_input = state["messages"][0].content

    score, critique = await evaluate_response(
        initial_input, last_message, [
            state.get("memory_context", ""),
            state.get("episodic_context", ""),
            state.get("graph_context", ""),
        ]
    )

    context_used = {
        "vector": state.get("memory_context", ""),
        "episodic": state.get("episodic_context", ""),
        "graph": state.get("graph_context", "")
    }
    log_trajectory(
        task_id=state["task_id"], 
        trajectory=state["tool_outputs"], 
        score=score,
        context_used=context_used,
        final_answer=last_message,
        critique=critique
    )

    is_complete = score >= settings.EVAL_PASS_THRESHOLD or iteration >= settings.MAX_ITERATIONS
    if iteration >= settings.MAX_ITERATIONS and score < settings.EVAL_PASS_THRESHOLD:
        critique = f"Max iterations ({settings.MAX_ITERATIONS}) reached. {critique}"

    logger.info(
        f"  Score: {score:.2f} | Iteration: {iteration}/{settings.MAX_ITERATIONS} | "
        f"Complete: {is_complete} | Context: {state.get('context_chars', 0)} chars"
    )
    logger.info(f"  Critique: {critique[:120]}")

    return {
        "eval_score": score,
        "eval_critique": critique,
        "is_complete": is_complete,
    }


# ---------------------------------------------------------------------------
# Memory Manager
# ---------------------------------------------------------------------------

@observe()
async def memory_node(state: AgentState) -> Dict[str, Any]:
    logger.info("MEMORY MANAGEMENT")
    initial_input = state["messages"][0].content
    final_answer = state["messages"][-1].content
    score = state.get("eval_score", 0.0)
    
    # Smart Memory Manager Metaprompt
    prompt = f"""You are the AgentOS Memory Manager.
Review this interaction:
User: {initial_input}
Agent: {final_answer}
Eval Score: {score}

Decide if this interaction contains useful facts, user preferences, or successful tool usage worth remembering.
Respond ONLY in JSON format:
{{
   "utility_score": 5,
   "decision": "PROMOTE",
   "summary": "Distilled knowledge"
}}
- PROMOTE: Highly valuable facts or logic to save as structured knowledge.
- SUMMARIZE: Somewhat useful interaction to save as an episode.
- FORGET: No useful info, or score too low, do not memorize."""

    try:
        import json
        result = await llm.ainvoke([SystemMessage(content=prompt)])
        
        # Parse JSON robustly
        content = result.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        decision_data = json.loads(content)
        utility = decision_data.get("utility_score", 0)
        decision = decision_data.get("decision", "FORGET").upper()
        summary = decision_data.get("summary", "")
        
        logger.info(f"  Memory Decision: {decision} | Utility: {utility}")
        
        if decision == "PROMOTE":
            await memory.add_episode(initial_input, state["tool_outputs"], score)
            logger.info("  Promoted to graph and rich memory.")
            
        elif decision == "SUMMARIZE" and summary:
            # Store only semantic summary to save space
            try:
                memory.episodic.add(summary, user_id="agent_os")
                memory.vector_store.add_texts(
                    [f"{summary} -> score={score:.2f}"],
                    metadatas=[{"type": "episode", "score": score}],
                )
                logger.info("  Summarized into episodic memory.")
            except Exception as inner_e:
                logger.warning(f"  Failed to store summary: {inner_e}")
                
    except Exception as e:
        logger.warning(f"  Memory Manager failed parsing, fallback to default: {e}")
        if score >= settings.EVAL_PASS_THRESHOLD:
            await memory.add_episode(initial_input, state["tool_outputs"], score)
            
    return {}


# ---------------------------------------------------------------------------
# LLM invocation with retry (extracted for reuse)
# ---------------------------------------------------------------------------

async def _invoke_with_retry(llm_instance, messages, max_retries=None, delay=None):
    """Call LLM with exponential backoff retry on transient failures."""
    retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
    retry_delay = delay if delay is not None else settings.LLM_RETRY_DELAY
    last_error = None

    for attempt in range(retries + 1):
        try:
            return await llm_instance.ainvoke(messages)
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = retry_delay * (2 ** attempt)
                logger.warning(f"  LLM call failed (attempt {attempt + 1}), retrying in {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                logger.error(f"  LLM call failed after {retries + 1} attempts: {e}")

    # Final fallback: return an error message instead of crashing
    return AIMessage(
        content=f"I encountered an error generating a response. Please try again. (Error: {last_error})"
    )

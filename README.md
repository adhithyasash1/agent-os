# AgentOS

A production-grade, local-first AI agent platform built on a self-reflective execution loop with 3-tier hybrid memory, context-engineered planning, critique-based evaluation, and MCP tool orchestration — all running on your machine with Ollama.

---

## System Design

AgentOS is designed around a single principle: **agents improve by remembering what worked, critiquing what didn't, and adapting their context window to what matters most.**

The system implements a closed-loop architecture where every interaction flows through four coordinated stages — execution, planning, evaluation, and memory management — with conditional retry when quality falls below threshold. The memory system isn't just storage; it's an active participant that decides what to remember, what to compress, and what to forget.

```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │       Executor         │  ← Entry point
              │  Tavily · Browser ·    │    URL extraction, web search,
              │  MCP tool dispatch     │    MCP server calls (parallel)
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │       Planner          │  ← Context engineering
              │  3-tier memory recall  │    Budget-managed prompt assembly
              │  + tool data fusion    │    Critique injection on retry
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │      Evaluator         │  ← LLM Council pattern
              │  Critique → Score      │    Skeptical review then scoring
              │  Rich trajectory log   │    Logs full run to JSONL
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │   Memory Manager       │  ← Smart memory decisions
              │  PROMOTE / SUMMARIZE   │    LLM-driven triage:
              │  / FORGET              │    what's worth remembering?
              └───────────┬────────────┘
                          │
                   ┌──────┴──────┐
                   │             │
            score ≥ 0.7    score < 0.7
            or max iter    and iter < max
                   │             │
                   ▼             ▼
                 [END]     [Loop back to
                            Executor]
```

---

## Architecture

### LangGraph State Machine

The agent loop is implemented as a [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` with four nodes and a conditional edge that controls retry behavior:

```python
# backend/app/agents/graph.py
workflow = StateGraph(AgentState)

workflow.set_entry_point("executor")          # Executor runs FIRST

workflow.add_edge("executor", "planner")      # executor → planner
workflow.add_edge("planner", "evaluator")     # planner → evaluator
workflow.add_edge("evaluator", "memory_manager")  # evaluator → memory

# Conditional: loop back or terminate
workflow.add_conditional_edges("memory_manager", should_continue, {
    "end": END,
    "executor": "executor",
})
```

**Why executor-first?** The executor gathers external data (web search results, URL content, MCP tool outputs) *before* the planner needs it. This ensures the planner always has fresh tool data in its context window, rather than planning blindly and hoping data arrives later.

### Agent State

Every node reads from and writes to a shared typed state:

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    task_id: str
    current_plan: str
    tool_outputs: List[Dict[str, Any]]
    memory_context: str       # Chroma vector search results
    episodic_context: str     # Mem0 past experiences
    graph_context: str        # Neo4j entity relationships
    eval_score: float
    eval_critique: str        # Critique text from evaluator
    is_complete: bool
    iteration: int
    context_chars: int        # Total context budget consumed
```

### Node Responsibilities

| Node | Input | Output | Key Behavior |
|------|-------|--------|--------------|
| **Executor** | User query + current plan | `tool_outputs[]` | Parallel URL extraction, Tavily search, MCP dispatch via `asyncio.gather()` |
| **Planner** | Messages + tool data + 3-tier memory | LLM response + memory contexts | Context budget management, critique injection on retry |
| **Evaluator** | Initial input + final answer + all contexts | Score (0.0–1.0) + critique | Critique-then-score pattern, rich trajectory logging |
| **Memory Manager** | Full interaction record | Memory writes | LLM-driven PROMOTE/SUMMARIZE/FORGET decision |

---

## Tech Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI + Uvicorn | Async API server with SSE streaming |
| **Agent Engine** | LangGraph | State machine with conditional edges |
| **LLM** | Ollama (gemma4:31b-cloud) | Local inference, cloud model support |
| **Embeddings** | Ollama (nomic-embed-text-v2-moe) | 768-dim vectors for semantic search |
| **Vector Store** | ChromaDB | Similarity search over past knowledge |
| **Episodic Memory** | Mem0 + Qdrant | Structured episodic recall |
| **Graph Store** | Neo4j Aura | Entity-relationship traversal |
| **Web Search** | Tavily API | Search + content extraction |
| **Browser** | Crawl4AI + Playwright | AI-optimized web scraping with fallback |
| **Reranker** | FlashRank (ms-marco-MiniLM) | Cross-encoder reranking after vector retrieval |
| **Tool Protocol** | FastMCP (stdio) | 5 MCP server integrations |
| **Observability** | Langfuse | Trace every node with `@observe()` |
| **Config** | Pydantic Settings | Type-safe env-driven configuration |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Next.js 16 | React server components |
| **UI** | React 19 + Tailwind CSS 4 | Dark theme, responsive layout |
| **Streaming** | EventSource (SSE) | Real-time agent step visualization |
| **State** | React hooks | Client-side state management |

---

## 3-Tier Hybrid Memory

Memory is the core differentiator. Three complementary stores work together, each capturing a different temporal and structural dimension of the agent's experience:

```
┌──────────────────────────────────────────────────────────────────┐
│                       Hybrid Memory System                       │
├──────────────────┬───────────────────┬───────────────────────────┤
│   Tier 1: Vector │  Tier 2: Episodic │  Tier 3: Graph            │
│   (ChromaDB)     │  (Mem0 + Qdrant)  │  (Neo4j Aura)             │
├──────────────────┼───────────────────┼───────────────────────────┤
│ What: Semantic   │ What: Compressed  │ What: Entity-relationship │
│ similarity over  │ summaries of past │ knowledge graph with      │
│ past interactions│ successful runs   │ task, entity, tool nodes  │
├──────────────────┼───────────────────┼───────────────────────────┤
│ Write: Intent +  │ Write: Distilled  │ Write: Named entity       │
│ score metadata   │ atomic facts from │ extraction → MERGE nodes  │
│                  │ trajectory        │ + MENTIONS/USED edges     │
├──────────────────┼───────────────────┼───────────────────────────┤
│ Read: cosine     │ Read: Mem0 search │ Read: Two-hop Cypher      │
│ similarity top-k │ by user_id        │ traversal (EdgeQuake)     │
├──────────────────┼───────────────────┼───────────────────────────┤
│ Retrieval K: 3   │ Retrieval K: 2    │ Retrieval K: 3            │
└──────────────────┴───────────────────┴───────────────────────────┘
```

### Write Path (after each interaction)

1. **Semantic Compression**: Raw trajectory distilled to atomic facts
   ```
   "User asked: What is LangGraph | Searched via tavily_search: 5 results | Final score: 0.85"
   ```
2. **Episodic Store**: Compressed summary → Mem0 (backed by Qdrant vectors)
3. **Vector Store**: `{intent} -> score={score}` → ChromaDB with metadata
4. **Graph Store**: Extract capitalized entities + tool names → Neo4j nodes + edges
   - `Task` nodes (indexed on `intent`)
   - `Entity` nodes (indexed on `name`)
   - `Tool` nodes
   - `MENTIONS` edges (Task → Entity)
   - `USED` edges (Task → Tool)

### Read Path (during planning)

All three tiers are queried **in parallel** via `asyncio.gather()`, with cross-encoder reranking on vector results:

```python
vector_ctx, episodic_ctx, graph_ctx = await asyncio.gather(
    _retrieve_vector(user_query),     # Chroma top-9 → FlashRank rerank → top-3
    _retrieve_episodic(user_query),   # Mem0 search by user_id
    _retrieve_graph(user_query),      # Neo4j two-hop traversal + compiled truths
)
```

### FlashRank Reranking

Raw vector similarity (cosine distance) returns "vaguely related" results. A cross-encoder reranker re-scores each candidate against the actual query, producing dramatically better ordering:

```
Query: "python web framework"

Before reranking (cosine):           After reranking (cross-encoder):
1. Python is a language  (0.82)      1. FastAPI is a web framework  (0.9997)
2. Weather in Paris      (0.71)      2. Python is a language        (0.5184)
3. FastAPI is a framework(0.68)      3. (filtered out)
```

The reranker fetches 3× candidates from Chroma (default: 9), reranks with FlashRank's ms-marco-MiniLM-L-12-v2 model (~33MB, CPU-only, <50ms), and keeps the top-k. Falls back to original cosine ordering if FlashRank is unavailable.

### GraphRAG-Lite (EdgeQuake Pattern)

The graph retrieval performs two-hop entity traversal inspired by the EdgeQuake pattern:

```cypher
-- Extract entity names from query, then traverse:
UNWIND $words AS word
MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower(word)
OPTIONAL MATCH (t:Task)-[:MENTIONS]->(e)
OPTIONAL MATCH (t)-[:USED]->(tool:Tool)
OPTIONAL MATCH (t)-[:MENTIONS]->(related:Entity)
RETURN e.name, t.intent, t.score, collect(DISTINCT tool.name), collect(DISTINCT related.name)
```

This answers: *"What did the agent do last time it encountered this entity? Which tools worked? What other entities were involved?"*

### Smart Memory Manager

Instead of blindly storing everything, an LLM-driven metaprompt triages each interaction:

| Decision | Criteria | Storage |
|----------|----------|---------|
| **PROMOTE** | High-value facts, successful tool usage | All 3 tiers (graph + episodic + vector) |
| **SUMMARIZE** | Moderately useful interaction | Episodic + vector only |
| **FORGET** | Low score, no useful information | Nothing stored |

Fallback: if the LLM's JSON response fails to parse, interactions scoring ≥ 0.7 are promoted automatically.

### Compiled Truth (GBrain Pattern)

Raw graph traversal returns every historical task mentioning an entity — including outdated, contradictory, or low-quality references. The compiled truth pattern maintains a single authoritative summary per entity:

```
Before (raw traversal):
  Entity: SpaceX Starship | used in: "Tell me about SpaceX Starship" | tools: tavily_search

After (compiled truth):
  [SpaceX Starship] SpaceX Starship is a fully reusable transportation system
  designed by SpaceX for carrying crew and cargo to Earth orbit, the Moon, Mars,
  and beyond.
```

**How it works:**
1. When the Memory Manager PROBMOTEs an interaction, entities are extracted and stored in Neo4j
2. For each affected entity, the LLM gathers all linked tasks (sorted by score) and compiles a single-sentence truth
3. The truth is stored as `entity.summary` + `entity.compiled_at` on the Neo4j node
4. During graph retrieval, the planner reads the compiled truth instead of raw task links
5. Truths are recompiled incrementally on PROMOTE and in batch during consolidation

### Memory Consolidation (Dreaming)

Offline memory maintenance — the biological analog of sleep consolidation. Triggered manually via the Memory dashboard or `POST /api/v1/memory/consolidate`:

| Phase | Action | Example |
|-------|--------|---------|
| **Deduplicate** | Find near-identical vectors in Chroma, keep highest-scoring | Two entries for "What is Python?" merged into one |
| **Contradictions** | LLM checks if entity-linked tasks conflict, removes lower-scoring link | Old fact about a CEO replaced by newer, higher-scoring one |
| **Prune** | Remove Task nodes below score threshold (default 0.3) + orphaned entities | Failed runs (score 0.2) cleaned from graph |
| **Compress** | LLM shortens verbose episodic memories while preserving key facts | 800-char memory → 200-char summary |
| **Compile Truths** | Generate/regenerate `entity.summary` for all entities missing one | Backfill compiled truths for pre-existing entities |

### Contradiction Detection

During the graph write path, before linking an entity to a new task, the system checks for stale links — existing entity connections to much lower-scoring tasks (score difference > 0.3 AND absolute score < 0.3). Stale edges are removed automatically to prevent outdated information from polluting traversal results.

---

## Context Engineering

### The Problem

LLMs have finite context windows. Dumping everything — tool results, memory, search results, past critiques — produces bloated prompts where the model can't find what matters.

### SimpleMem Budget Management

AgentOS implements a **context budget** (default: 12,000 characters) with strict priority ordering:

```
Priority 1: Tool Results     (executor data — freshest, most relevant)
Priority 2: Graph Memory     (entity relationships from Neo4j)
Priority 3: Past Experiences  (episodic memory from Mem0)
Priority 4: Related Knowledge (vector similarity from Chroma)
```

Each tier is allocated remaining budget space. Lower-priority tiers get truncated or dropped entirely if the budget is exhausted by higher-priority data:

```python
for label, text in [
    ("Tool Results", tool_context),           # Priority 1
    ("Graph Memory", graph_ctx),              # Priority 2
    ("Past Experiences", episodic_ctx),        # Priority 3
    ("Related Knowledge", vector_ctx),         # Priority 4
]:
    if text and total_chars < budget:
        remaining = budget - total_chars
        trimmed = text[:remaining]
        context_sections.append(f"--- {label} ---\n{trimmed}")
        total_chars += len(trimmed)
```

### Tool Output Truncation

Individual tool outputs are capped before entering the budget:

| Source | Max Characters |
|--------|---------------|
| Tool output (Tavily/browser) | 5,000 |
| MCP server result | 3,000 |
| Search result preview | 300 per result |

### Critique Injection on Retry

When the evaluator scores below threshold and the loop retries, the planner receives the critique as additional context:

```python
if iteration > 1 and prev_critique:
    system_parts.append(
        f"Your previous answer was critiqued. Address these issues:\n{prev_critique}"
    )
```

This creates a focused retry: the model knows exactly what was wrong and can address specific weaknesses rather than regenerating blindly.

---

## Evaluation: LLM Council Pattern

### The Problem with Self-Grading

Having the same LLM rate its own output produces inflated scores. The model is biased toward defending its own work.

### Critique-Then-Score

Inspired by Karpathy's LLM Council, evaluation is split into two forced steps:

**Step 1 — Skeptical Review:**
```
You are a SKEPTICAL REVIEWER. Your job is to find flaws.
Check for:
- Does it actually answer what was asked?
- Are there unsupported factual claims?
- Is important information missing?
- Does it hallucinate?

Write 2-4 bullet points about strengths AND weaknesses.
```

**Step 2 — Informed Score:**
```
Based on the critique below, rate the response 0.0 to 1.0.

Scoring guide:
- 0.0-0.3: Wrong, irrelevant, or empty
- 0.4-0.6: Partially answers but has significant gaps
- 0.7-0.8: Good answer with minor issues
- 0.9-1.0: Excellent, comprehensive answer
```

The score is parsed robustly — handles 0–1, 0–10, and 0–100 scales that models sometimes produce.

### Retry Logic

```
score ≥ 0.7  →  Accept (pass threshold)
score < 0.7 AND iteration < 3  →  Retry with critique injected
score < 0.7 AND iteration = 3  →  Accept with warning (max iterations)
```

---

## MCP Tool Registry

Five external tool servers connected via [Model Context Protocol](https://modelcontextprotocol.io/) using FastMCP's stdio transport:

| Server | Transport | Capabilities | Credential |
|--------|-----------|-------------|------------|
| **Excel** | `npx @negokaz/excel-mcp-server` | Read/write Excel, tables, formatting | — |
| **Markdownify** | `npx @zcaceres/markdownify-mcp` | Convert PDF, YouTube, DOCX, PPTX → Markdown | — |
| **GitHub** | `npx @github/mcp-server` | Search code, manage repos, issues, PRs | `GITHUB_TOKEN` |
| **HuggingFace** | `npx @llmindset/hf-mcp-server` | Query models, datasets, spaces, inference | `HF_TOKEN` |
| **TradingView** | `tradingview-mcp-server` | Market data, technical analysis, screening | — |

### How Tool Selection Works

1. **Keyword Matching**: User query matched against server keyword lists
2. **Parallel Dispatch**: All matched servers called concurrently via `asyncio.gather()`
3. **Heuristic Tool Selection**: Within a server, the best tool is selected by weighted keyword overlap (name match = 3× weight vs. description match)
4. **Argument Building**: Arguments auto-constructed from query context (URLs, search terms, ticker symbols)

```python
# Matching flow
user_query → match_servers(text) → ["markdownify", "github"]
                                         │
                    ┌────────────────────┤
                    ▼                    ▼
            list_mcp_tools()     list_mcp_tools()
                    │                    │
            _pick_best_tool()    _pick_best_tool()
                    │                    │
            call_mcp_tool()      call_mcp_tool()
                    │                    │
                    └──────┬─────────────┘
                           ▼
                    tool_outputs[]  →  planner context
```

### Built-In Tools

| Tool | Purpose | Fallback |
|------|---------|----------|
| **Tavily Search** | Web search with 5 results | — |
| **Tavily Extract** | URL content extraction | Playwright browser |
| **Playwright Browse** | Full browser rendering | Used when Tavily extract insufficient |

URL extraction uses a cascade: Tavily first (faster, API-based), Playwright fallback (handles JS-rendered pages). Resource cleanup is guaranteed via try/finally.

---

## Trajectory Dataset

Every run produces a rich trajectory record stored in JSONL format — designed to be directly usable for preference learning (DPO/GRPO):

```json
{
  "run_id": "20260415143022",
  "task_id": "What is the latest news about...",
  "trajectory": [
    {"tool": "tavily_search", "query": "...", "status": "success", "results": [...]},
    {"tool": "tavily_extract", "url": "...", "status": "success", "content": "..."}
  ],
  "score": 0.85,
  "context_used": {
    "vector": "Related knowledge retrieved...",
    "episodic": "Past experience: ...",
    "graph": "Entity: X | used in: Y | tools: Z"
  },
  "final_answer": "Based on the latest information...",
  "critique": "• Answers the core question well\n• Could include more recent data...",
  "human_feedback": {"score": 1, "comment": ""},
  "timestamp": "2026-04-15T14:30:22.000000"
}
```

### Fields for Training

| Field | Training Use |
|-------|-------------|
| `trajectory` | Tool-use traces for action prediction |
| `score` | Reward signal for RLHF |
| `critique` | Natural language reward model training |
| `human_feedback` | Ground truth preference signal |
| `context_used` | RAG retrieval evaluation |
| `final_answer` + `score` | Preference pairs (high-score vs low-score responses) |

### Human Feedback Loop

Users can provide thumbs-up/thumbs-down feedback from the frontend. Feedback is attached to specific task IDs by rewriting the JSONL file atomically:

```
POST /api/v1/runs/{task_id}/feedback
Body: {"score": 1, "comment": "helpful answer"}
```

---

## Observability

### Langfuse Integration

Every agent node is decorated with `@observe()` for distributed tracing:

```python
@observe()
async def planner_node(state: AgentState) -> Dict[str, Any]:
    ...

@observe()
async def executor_node(state: AgentState) -> Dict[str, Any]:
    ...

@observe()
async def evaluator_node(state: AgentState) -> Dict[str, Any]:
    ...

@observe()
async def memory_node(state: AgentState) -> Dict[str, Any]:
    ...
```

This produces a full trace for each agent run showing: LLM latency, token usage, memory retrieval timing, tool execution duration, and evaluation scores.

### Structured Logging

All nodes emit structured logs with consistent format:

```
14:30:22 | agentos.nodes | INFO | EXECUTING
14:30:23 | agentos.nodes | INFO |   Extracting: https://example.com
14:30:24 | agentos.nodes | INFO |   Searching: latest AI news
14:30:25 | agentos.nodes | INFO | PLANNING (iteration 1)
14:30:28 | agentos.nodes | INFO | EVALUATING
14:30:30 | agentos.nodes | INFO |   Score: 0.85 | Iteration: 1/3 | Complete: True | Context: 4200 chars
14:30:30 | agentos.nodes | INFO |   Critique: Answers the core question well...
14:30:31 | agentos.nodes | INFO | MEMORY MANAGEMENT
14:30:32 | agentos.nodes | INFO |   Memory Decision: PROMOTE | Utility: 8
```

### Health Monitoring

The `/api/v1/health` endpoint checks all five dependencies:

| Dependency | Check Method | States |
|-----------|-------------|--------|
| Ollama | HTTP GET `/api/tags` | ok / unreachable |
| ChromaDB | `vector_count()` | ok / error |
| Neo4j | `verify_connectivity()` | ok / error / disabled |
| Mem0/Qdrant | `episodic_count()` | ok / error |
| Tavily | API key presence | configured / missing_key |

Returns `"ok"` if all deps healthy, `"degraded"` if any are down but system can still function.

---

## Guardrails & Resilience

### Input Validation
- Message length capped at 10,000 characters (configurable)
- Request validation via Pydantic models

### LLM Retry with Exponential Backoff
```python
async def _invoke_with_retry(llm, messages, max_retries=2, delay=2.0):
    for attempt in range(retries + 1):
        try:
            return await llm.ainvoke(messages)
        except Exception:
            wait = delay * (2 ** attempt)  # 2s, 4s, 8s...
            await asyncio.sleep(wait)
    return AIMessage(content="Error generating response. Please try again.")
```

Never crashes — always returns a graceful fallback message.

### Cloud Model Detection
```python
is_cloud = model.endswith(":cloud") or "-cloud" in model
if not is_cloud:
    kwargs["num_predict"] = 4096  # Only for local models
```

Cloud-proxied models (e.g., `gemma4:31b-cloud`) reject `num_predict`; detected automatically via name suffix.

### Memory Graceful Degradation
- Neo4j optional — system runs without graph memory if unavailable
- Mem0 failures logged and skipped, don't crash the agent loop
- ChromaDB errors caught per-query

### CORS Restriction
```python
allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"]
```

### Resource Cleanup
- Neo4j driver closed on application shutdown via FastAPI lifespan hook
- Playwright browser instances cleaned up via try/finally
- MCP server connections scoped to `async with Client(transport)`

---

## API Reference

### Chat

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/` | POST | Synchronous chat — returns full response with score |
| `/api/v1/chat/stream` | POST | SSE streaming — emits step/response/eval/done events |

**SSE Event Types:**
```
event: step     → {"step": "executor", "iteration": 1}
event: response → {"content": "...", "iteration": 1}
event: eval     → {"score": 0.85, "critique": "...", "iteration": 1}
event: done     → {"score": 0.85, "iterations": 1, "context_chars": 4200, "task_id": "..."}
event: error    → {"error": "..."}
```

### Runs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/runs/` | GET | List all runs |
| `/api/v1/runs/{run_id}` | GET | Get specific run details |
| `/api/v1/runs/{task_id}/feedback` | POST | Attach human feedback to a run |

### Memory

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/memory/stats` | GET | Memory statistics across all tiers |
| `/api/v1/memory/search?query=` | GET | Unified 3-tier memory search |

### Tools

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tools/` | GET | List all MCP servers + availability |
| `/api/v1/tools/{server}/tools` | GET | List tools on a specific server |
| `/api/v1/tools/{server}/call` | POST | Call a specific MCP tool |

### Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Dependency health check |

---

## Frontend Dashboard

Seven pages providing full visibility into the agent's behavior:

| Page | Route | Features |
|------|-------|----------|
| **Home** | `/` | System health, memory stats, dependency grid, architecture overview |
| **Chat** | `/chat` | SSE streaming chat with live step indicators, feedback widget |
| **Runs** | `/runs` | Expandable run history with answer, critique, trajectory, context, feedback |
| **Evals** | `/evals` | Score distribution chart, pass/fail counts, average score |
| **Traces** | `/traces` | Tabbed detail view: Trajectory / Answer / Critique / Context per run |
| **Memory** | `/memory` | 4 stat cards, unified 3-tier search with color-coded results |
| **Tools** | `/tools` | MCP server cards, expandable tool lists, availability indicators |

---

## Setup

### Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **Ollama** installed and running ([ollama.ai](https://ollama.ai))
- **Neo4j** instance (local, Docker, or [Neo4j Aura](https://neo4j.com/cloud/aura/) free tier)

### 1. Clone and configure

```bash
git clone https://github.com/AdhithyaSash/AgentOS.git
cd AgentOS
```

### 2. Backend setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Install Playwright browser (for fallback URL extraction)
playwright install chromium
```

### 3. Environment configuration

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials
```

Required environment variables:

```env
# LLM (required)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:31b-cloud
OLLAMA_EMBED_MODEL=nomic-embed-text-v2-moe

# Neo4j (required for graph memory)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Web Search (required for search capability)
TAVILY_API_KEY=tvly-xxxxx

# Optional — MCP servers
GITHUB_TOKEN=ghp_xxxxx
HF_TOKEN=hf_xxxxx

# Optional — Observability
LANGFUSE_PUBLIC_KEY=pk-xxxxx
LANGFUSE_SECRET_KEY=sk-xxxxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 4. Pull Ollama models

```bash
ollama pull gemma4:31b-cloud       # or your preferred model
ollama pull nomic-embed-text-v2-moe  # embeddings (768-dim)
```

### 5. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — the dashboard will show dependency health on the home page.

---

## Project Structure

```
AgentOS/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── graph.py          # LangGraph state machine definition
│   │   │   ├── nodes.py          # All 4 agent nodes (executor, planner, evaluator, memory)
│   │   │   └── state.py          # AgentState TypedDict
│   │   ├── api/v1/
│   │   │   ├── api.py            # Router registry + health endpoint
│   │   │   ├── chat.py           # Chat + SSE streaming endpoints
│   │   │   ├── runs.py           # Run history + feedback endpoints
│   │   │   ├── memory.py         # Memory stats + search endpoints
│   │   │   └── tools.py          # MCP server management endpoints
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic Settings — all tunable constants
│   │   │   ├── llm.py            # Ollama LLM + embeddings factory
│   │   │   └── tasks.py          # JSONL trajectory storage + feedback
│   │   ├── eval/
│   │   │   └── manager.py        # LLM Council critique-then-score evaluator
│   │   ├── memory/
│   │   │   └── hybrid.py         # 3-tier HybridMemory class
│   │   ├── tools/
│   │   │   ├── mcp_servers.py    # 5 MCP server definitions + dispatch
│   │   │   ├── mcp_client.py     # FastMCP client utilities
│   │   │   ├── tavily_tool.py    # Tavily search + extract wrappers
│   │   │   └── browser_tool.py   # Playwright URL extraction
│   │   └── main.py               # FastAPI app, CORS, lifespan hooks
│   ├── data/
│   │   ├── tasks.jsonl           # Rich trajectory dataset
│   │   └── chroma/               # ChromaDB persistent storage
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx              # Dashboard — health, stats, architecture
│   │   ├── chat/page.tsx         # Chat interface with SSE + feedback
│   │   ├── runs/page.tsx         # Run history with expandable details
│   │   ├── evals/page.tsx        # Evaluation analytics
│   │   ├── traces/page.tsx       # Tabbed trace viewer
│   │   ├── memory/page.tsx       # Memory search + stats
│   │   ├── tools/page.tsx        # MCP server management
│   │   ├── components/sidebar.tsx # Navigation sidebar
│   │   ├── layout.tsx            # Root layout
│   │   └── globals.css           # Dark theme + custom styles
│   ├── package.json
│   └── tsconfig.json
└── README.md
```

---

## Configuration Reference

All constants are centralized in `backend/app/core/config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `gemma4:31b-cloud` | LLM model name |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text-v2-moe` | Embedding model (768-dim) |
| `MAX_ITERATIONS` | `3` | Max retry loops before accepting |
| `EVAL_PASS_THRESHOLD` | `0.7` | Minimum score to accept response |
| `CONTEXT_BUDGET_CHARS` | `12000` | Total context budget for planner |
| `TOOL_OUTPUT_MAX_CHARS` | `5000` | Max chars per tool output |
| `MCP_RESULT_MAX_CHARS` | `3000` | Max chars per MCP result |
| `SEARCH_RESULT_PREVIEW` | `300` | Max chars per search result snippet |
| `VECTOR_SEARCH_K` | `3` | Number of Chroma results to retrieve |
| `EPISODIC_SEARCH_K` | `2` | Number of Mem0 results to retrieve |
| `GRAPH_SEARCH_K` | `3` | Number of Neo4j results to retrieve |
| `MAX_MESSAGE_LENGTH` | `10000` | Input message character limit |
| `LLM_MAX_RETRIES` | `2` | LLM call retry attempts |
| `LLM_RETRY_DELAY` | `2.0` | Initial retry delay (seconds, doubles each attempt) |

---

## Design Patterns

| Pattern | Origin | Implementation |
|---------|--------|----------------|
| **SimpleMem** | Context budget management | Priority-ordered memory allocation with hard char budget |
| **LLM Council** | Karpathy | Critique-then-score two-step evaluation |
| **EdgeQuake / GraphRAG-Lite** | Entity traversal | Neo4j two-hop Cypher queries for entity→task→tool graphs |
| **Smart Memory Manager** | LLM-as-judge | Metaprompt decides PROMOTE/SUMMARIZE/FORGET per interaction |
| **Semantic Compression** | Token efficiency | Trajectory distilled to atomic facts before memory storage |
| **Cascade Fallback** | Reliability | Tavily → Playwright for URL extraction; LLM retry → fallback message |

---

## License

MIT

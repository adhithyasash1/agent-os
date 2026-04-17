# agentos-core

A local-first agent orchestration runtime. 

agentos-core accepts a user request, retrieves matching context from 6 typed memory stores, packs the context, plans a next step, executes safely bordered tools, verifies the result, and records the flow. Everything happens on-machine using SQLite.

It is designed to be fully testable without external APIs. It prioritizes structure and logging robustness over black-box AI magic.

---

## What problem it solves

Most agent frameworks assume cloud infra (vector DBs, graph DBs, hosted
LLMs, observability SaaS). That makes them hard to reason about, hard to
debug locally, and hard to prove anything about.

agentos-core flips that:

- **local by default**: SQLite only; no Neo4j / Chroma / Qdrant needed
- **observable by default**: every phase of every run is a row in
  `trace_events`; every decision also emits a score-annotated row in
  `run_transitions`
- **testable by default**: a deterministic mock LLM runs the whole loop
  without a network
- **measurable by default**: one `python -m bench.runner --all-ablations`
  produces a report comparing full-system vs. each component off

---

## The agent loop

Every run walks a fixed sequence. Each step emits a `TraceEvent`.

```
understand  →  retrieve  →  plan  →  act  →  verify  →  (reflect & retry?)  →  final
```

| Phase        | What happens                                              | Gated by           |
|--------------|-----------------------------------------------------------|--------------------|
| `understand` | Record the raw user input, validate non-empty             | always             |
| `retrieve`   | Search `working`, `episodic`, and `semantic` memory, then rank and pack context | `enable_memory` |
| `plan`       | LLM emits ReAct JSON `{goal, action, tool, tool_args, observation_summary, confidence, stop_reason, answer}` | `enable_planner` |
| `act`        | Execute the chosen tool via the registry                  | `enable_tools`     |
| `verify`     | `expected_contains` match (benchmarks) → LLM-as-judge (live, opt-in) → heuristic fallback (weak) | always |
| `reflect`    | LLM critique → feed back into planner for next iteration  | `enable_reflection`|
| `final`      | Persist answer + score. Promote facts to durable memory **only** when the verification is trustworthy | always |

Max iterations and the pass threshold are configurable.

### Memory Architecture

The system utilizes 6 specialized memory stores implemented inside SQLite:

- `working`: Short-lived scratchpad for multi-turn conversational context. Decays rapidly.
- `episodic`: Long-term fact persistence. Written only conditionally upon verified execution.
- `semantic`: Deep domain rules or generalized abstractions.
- `experience`: Top-performing trajectories (planner logic and tools). Injected as dynamic Few-Shot examples into future prompts.
- `failure`: Recorded dead-ends from error recoveries, allowing the agent to avoid repeating exact mistakes. Kept at a carefully weighted lower-salience unless explicitly matched.
- `style`: End-user interaction requirements.

### What "trustworthy" means for memory promotion

The loop only promotes data to long-standing memory (`experience`, `episodic`, `semantic`) when the verification step scores `trustworthy=true`.

For trajectories to enter `experience` memory, they must pass strict scoring thresholds, converting the JSON tool calls and the outcome goal into structured few-shot lessons. The heuristic scorer is weak—meaning only explicit `expected_contains` benchmark matches or LLM-as-Judge loops will permanently promote an experience.

---

## Architecture

```
agentos/
├── config.py             # pydantic-settings; profiles + feature flags
├── main.py               # FastAPI entrypoint + lifespan + static UI mount
├── runtime/
│   ├── loop.py           # The phase-by-phase agent loop
│   ├── context_packer.py # Utility-ranked context budgeting
│   ├── planner.py        # LLM JSON-decision planner
│   └── trace.py          # SQLite TraceStore + TraceEvent
├── memory/store.py       # Tiered SQLite FTS5 memory
├── tools/
│   ├── registry.py       # Tool protocol + flag-aware registry
│   └── builtin.py        # calculator, http_fetch, tavily (optional)
├── llm/
│   ├── protocol.py       # LLM.complete(prompt, system=...)
│   ├── mock.py           # Deterministic mock for tests/minimal profile
│   ├── ollama.py         # Ollama chat backend (local + cloud models)
│   └── factory.py
├── eval/
│   ├── scorer.py         # expected / llm-judge / heuristic
│   └── reflection.py     # critique prompt
└── api/routes.py         # /runs, /traces, /memory, /tools, /config, /health
bench/                    # tasks + runner + report
console/                  # Next.js App Router operator console (primary UI)
tests/                    # pytest suite (uses MockLLM, no network)
ui/index.html             # minimal fallback trace viewer, unmaintained —
                          # kept only for zero-dep debugging via the API
```

Components are instantiated once at FastAPI lifespan startup and attached
to `app.state`. Every route receives them via `Depends(get_components)`,
so there is no mutable module-level singleton and no race under async
load. The `/config` patch endpoint builds a fresh bundle from the new
settings and swaps `app.state.components` atomically under an asyncio
lock.

---

## Quickstart (offline demo, zero external services)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e '.[dev]'

# run the API on http://localhost:8000
python -m agentos.main
# or
uvicorn agentos.main:app --reload
```

Open <http://localhost:8000/> for the trace viewer, or
<http://localhost:8000/docs> for the OpenAPI docs.

Try it:

```bash
curl -s http://localhost:8000/api/v1/runs \
  -H 'content-type: application/json' \
  -d '{"input": "Calculate 12 * 11"}' | jq
```

The default `minimal` profile uses MockLLM. **MockLLM is a stub, not a
model** — it's good enough to exercise the loop, memory, tools, and trace
writer, but the answers are hard-coded lookups. Treat MockLLM benchmark
numbers as smoke-test signal only.

### Optional Next.js console

```bash
cd console && npm install && npm run dev
```

Point it at the API by setting `NEXT_PUBLIC_AGENTOS_API_BASE=http://localhost:8000/api/v1`.

---

## Running with Ollama (real LLM, local + cloud models)

agentos-core talks to Ollama via the standard local daemon at
`http://localhost:11434`. Both on-device and cloud-served models work
through the same endpoint — cloud models just require a one-time
`ollama signin` first.

```bash
# once, to authenticate for cloud models
ollama signin
ollama pull gemma4:31b-cloud     # 31B cloud-served Gemma 4
ollama serve                     # leave running

# .env (or export)
AGENTOS_PROFILE=full
AGENTOS_OLLAMA_MODEL=gemma4:31b-cloud
# leave AGENTOS_OLLAMA_API_KEY empty — cloud-model auth goes through
# the local daemon, not the HTTP request.
```

`profile=full` auto-switches the backend to `ollama`, turns on the
**LLM-as-judge** verification path, and keeps tools available.

If instead you want to run a local model, pick any tag Ollama supports
(e.g. `gemma3:27b`, `qwen3:14b`, `llama3.2`) and drop the `-cloud`
suffix. On-device models do not need `ollama signin`.

When you're talking to an Ollama endpoint behind a reverse proxy that
enforces bearer auth, set `AGENTOS_OLLAMA_API_KEY` — the HTTP client
will send `Authorization: Bearer <key>` on every `/api/chat` call.

---

## Tests

```bash
pytest -q
```

The suite covers:

- **memory**: tiered storage, salience filters, verified promotion, TTL edge cases
- **tools**: calculator, flag gating, unknown tool handling, unsafe input
- **scorer**: expected-match, grounding heuristic, LLM-judge happy path, judge error fallbacks, trustworthy gate
- **trace**: run lifecycle, event listing, run_transitions persistence
- **loop**: happy path, tool path, empty-input rejection, planner schema,
  durable-memory promotion (positive + negative), trace completeness
- **api**: health, runs create/list/get, memory search, config patch
  roundtrip, feedback writes, empty input rejection

All tests run against MockLLM and a temporary SQLite DB with no network
and no model downloads.

---

## Benchmarks

```bash
# single profile
python -m bench.runner --profile minimal

# specific ablation
python -m bench.runner --ablation no-memory

# everything
python -m bench.runner --all-ablations

# markdown report across all saved results
python -m bench.report
```

### Read this before you trust the numbers

The default bench runs against **MockLLM**, whose `_direct_answer`
lookup table happens to contain the exact answer strings the benchmark
tasks check for. That is:

- Numbers produced by `profile=minimal` are not a measurement of
  reasoning quality. They measure whether the loop, tools, memory, and
  scoring plumbing all fire correctly end-to-end.
- Ablation deltas against MockLLM are uninformative — the mock bypasses
  the capability each ablation is supposed to stress. `no-memory ≈ full`
  under MockLLM is not a finding, it's a consequence of the mock.

For a real measurement, run benchmarks with the Ollama backend:

```bash
AGENTOS_PROFILE=full \
AGENTOS_LLM_BACKEND=ollama \
AGENTOS_OLLAMA_MODEL=gemma4:31b-cloud \
python -m bench.runner --profile full --all-ablations
```

### Tasks

`bench/tasks.json` ships a small, balanced set:

- `knowledge`: direct factual questions
- `tool_use`: must invoke the calculator
- `reasoning`: small arithmetic / logic puzzles
- `retrieval`: questions that require seeded memory
- `failure_handling`: empty input, nonsense, fabrication baiting

Tasks are also tagged by slice so you can track retrieval-required,
tool-required, multi-step, long-context, refusal-safety, and
reflection-roi behavior independently.

### Metrics tracked per run

- `overall_score`: mean of per-task scores
- `success_rate`: fraction scoring ≥ 0.6
- `tool_call_success_rate`: of tasks with `expected_tool`, how many called it
- `tool_precision` / `tool_recall`: correctness + completeness of tool use
- `context_utility_rate`: whether retrieved context actually improved solved retrieval tasks
- `reflection_roi`: score delta on tasks where reflection fired
- `mean_latency_ms`: wall-clock per task
- `by_category` and `by_slice`: score breakdowns
- `flags`: feature flags used for this run

### Ablations

| Label            | What's off       |
|------------------|------------------|
| `full`           | nothing          |
| `no-memory`      | FTS retrieval    |
| `no-planner`     | LLM planner      |
| `no-tools`       | tool execution   |
| `no-reflection`  | critique retry   |

`bench/report.py` emits a markdown report with a summary table and
deltas vs. `full`, so you can see whether a component is pulling its
weight — **when you use a real LLM**. See the disclaimer above.

---

## Logging & observability

Every run produces a complete trace:

```
GET /api/v1/runs/{run_id}
```

Returns the run row plus ordered `trace_events` and score-annotated run
log rows from `run_transitions`.

Each `trace_event` carries:

- `kind` — `understand | retrieve | plan | tool_call | verify | reflect | final | error`
- `name` — tool/node name or short label
- `input` / `output` — JSON strings (bounded to 8 KB)
- `latency_ms`, `tokens_in`, `tokens_out` (best-effort)
- `error` — populated if the step failed

Each row in `run_transitions` carries `(state, action, observation,
score)` plus metadata: `prompt_version`, `context_ids`,
`retrieval_candidates`, `tool_latency_ms`, `verifier_score`,
`reflection_delta`, optional `user_feedback`.

### What `run_transitions` is and isn't

The schema was chosen to make these rows easy to replay for future
offline RL work, but **no training loop consumes them today**. There is
no replay buffer, no policy update, no behavior change informed by past
scores. `reflection_roi` is computed for visibility but nothing feeds
it back into planner behavior on the next run.

In practice, `run_transitions` is **structured per-step run logs with
score annotation** — useful as an audit trail, a dataset for future
offline training, or an input to a dashboard. It is not reinforcement
learning.

### OpenTelemetry (optional)

When `AGENTOS_ENABLE_OTEL=true`, the trace store also dual-writes spans
through an OpenTelemetry bridge so the same run can be viewed in a
tracing backend such as Phoenix.

The Next.js console at `console/` is the maintained operator UI. The
static `ui/index.html` endpoint mounted at `/` is a minimal zero-dep
fallback — it renders the same rows but is not kept in sync with new
fields; prefer the console for day-to-day use.

---

## Reliability

- **Strict Tooling**: Tool arguments strictly abide by declared JSON Schemas. Malformed LLM parameters are blocked at the registry layer with localized error returns, forcing self-correction before arbitrary execution.
- **Sandboxed Workspace**: Any local file traversal occurs inside the heavily restricted `workspace_manager` tool, which intercepts and sanitizes local path manipulation.
- Planner output is parsed with a tolerant regex + JSON fallback — if the LLM ignores the schema, the raw text is treated as the final answer.
- Ollama backend retries with exponential backoff.
- Empty or whitespace-only input is rejected before the loop runs.
- `/config` patches build a fresh components bundle from the new settings and swap `app.state.components` atomically.
  routing flags (`enable_memory`, `enable_planner`, `enable_tools`,
  `enable_reflection`, `enable_llm_judge`, `enable_otel`); the LLM
  instance, memory store, and DB path are **not** swapped live — flip
  them by restarting with different env vars.
- Legacy memory DBs (pre-tiered schema) are migrated on startup: the
  old `memory_fts` virtual table is dropped and rebuilt with the new
  `(text, kind)` columns.

---

## Limitations (honest edition)

- **MockLLM is a stub, not a model.** Its `_direct_answer` table
  contains hard-coded strings that match the benchmark expectations.
  Real reasoning requires Ollama or another real backend.
- **The heuristic scorer is a weak signal.** It is no longer used as a
  promotion gate — only `expected_contains` or a passing LLM-judge
  verdict can promote to durable memory. But the score itself still
  drives the reflection trigger, which means reflection can fire
  spuriously on a verbose answer. Turn on `enable_llm_judge` for a
  meaningful verification signal.
- **Memory is still keyword-first.** Tiered working/episodic/semantic
  storage is in place, but retrieval uses SQLite FTS5 — not embeddings.
- **Tools are minimal.** Calculator + HTTP fetch + optional Tavily. The
  registry is designed so adding a tool is ~20 lines, not a refactor.
- **No multi-agent orchestration.** One loop, one agent.
- **Trace payloads are truncated at 8 KB** to keep SQLite fast; full
  payloads are not preserved.
- **`run_transitions` is not RL.** It's score-annotated run logs.
- **Context packer budgets** (`0.18 / 0.16 / 0.28` splits between
  developer prompt, scratchpad, and tools) are hand-tuned, not
  empirically validated via the ablation framework. If you care about
  this, it's a natural next ablation to add.

---

## Environment variables

All prefixed with `AGENTOS_`. See `.env.example` for the full list. The
most important ones:

| Variable                    | Default              | Notes                              |
|-----------------------------|----------------------|------------------------------------|
| `AGENTOS_PROFILE`           | minimal              | `minimal` (mock) or `full` (ollama + judge) |
| `AGENTOS_LLM_BACKEND`       | mock                 | `mock` or `ollama`                 |
| `AGENTOS_OLLAMA_MODEL`      | `gemma4:31b-cloud`   | any Ollama tag; `*-cloud` = cloud  |
| `AGENTOS_OLLAMA_API_KEY`    | empty                | only for proxy-auth'd endpoints    |
| `AGENTOS_DB_PATH`           | `./data/agentos.db`  | SQLite file                        |
| `AGENTOS_PROMPT_VERSION`    | `react-context-v1`   | prompt/schema version              |
| `AGENTOS_MAX_STEPS`         | 4                    | max planner/executor iterations    |
| `AGENTOS_EVAL_PASS_THRESHOLD` | 0.6                | score threshold for completion     |
| `AGENTOS_CONTEXT_CHAR_BUDGET` | 8000               | total context packer budget        |
| `AGENTOS_MEMORY_SEARCH_K`   | 8                    | retrieved memories per query       |
| `AGENTOS_MEMORY_MIN_SALIENCE` | 0.15               | drop weak memories before packing  |
| `AGENTOS_WORKING_MEMORY_TTL_SECONDS` | 3600        | short-lived scratch memory         |
| `AGENTOS_EPISODIC_MEMORY_TTL_SECONDS` | 1209600    | durable run memory                 |
| `AGENTOS_ENABLE_MEMORY`     | true                 |                                    |
| `AGENTOS_ENABLE_PLANNER`    | true                 |                                    |
| `AGENTOS_ENABLE_TOOLS`      | true                 |                                    |
| `AGENTOS_ENABLE_REFLECTION` | true                 |                                    |
| `AGENTOS_ENABLE_LLM_JUDGE`  | false (auto-on in full) | LLM-as-judge for live runs      |
| `AGENTOS_ENABLE_OTEL`       | false                | dual-write traces to OTel          |
| `AGENTOS_OTEL_SERVICE_NAME` | `agentos-core`       | span service name                  |
| `AGENTOS_OTEL_EXPORTER_OTLP_ENDPOINT` | empty      | optional OTLP endpoint             |

---

## License

Personal project scaffolding. No license assigned; adapt as you like.

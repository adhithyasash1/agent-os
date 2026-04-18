export const MOCK_RUNS = [
  {
    id: "run_8f7b2c9a",
    prompt: "Summarize the latest trends in synthetic data generation vs real-world validation.",
    status: "completed",
    score: 0.94,
    latency: "2.4s",
    timestamp: "2026-04-17T10:23:45Z",
    tokens: 1420
  },
  {
    id: "run_4a1f9e2d",
    prompt: "Scan standard output for memory leak anomalies.",
    status: "failed",
    score: 0.12,
    latency: "840ms",
    timestamp: "2026-04-17T11:05:12Z",
    tokens: 450,
    error: "Tool Execution Timeout: diagnostic.py exceeded bounds."
  },
  {
    id: "run_9c3d4f1a",
    prompt: "Update my memory to track my preference for raw JSON payload outputs.",
    status: "running",
    score: null,
    latency: null,
    timestamp: new Date().toISOString(),
    tokens: 120
  }
];

export const MOCK_TRACE = {
  run_id: "run_8f7b2c9a",
  events: [
    { type: "plan", name: "Planner", summary: "Identify core task directives", input: "Summarize...", output: "Decided to retrieve semantic memory on synthetic data before searching.", latency: 120 },
    { type: "memory", name: "MemoryStore", summary: "Retrieving semantic baseline", input: "synthetic data generation validation", output: "Found 3 references with semantic similarity > 0.85.", latency: 45 },
    { type: "tool", name: "tavily_search", summary: "External Validation Query", input: "site:arxiv.org synthetic vs real data 2026", output: "Fetched 4 top abstracts.", latency: 1200 },
    { type: "reflection", name: "LLMJudge", summary: "Critique Output", input: "Analyze summary vs original prompt constraints.", output: "Summary covers generation but misses validation tradeoffs. Retrying.", latency: 340 },
    { type: "plan", name: "Planner", summary: "Refine summary", input: "Add validation tradeoffs", output: "Generated final payload.", latency: 210 }
  ]
};

export const MOCK_MEMORY = [
  { id: "mem_semantic_1", type: "semantic", content: "Agent prefers output formats in flat JSON array matrices rather than nested hierarchies.", score: 0.94, origin: "run_2a1b9e", date: "2026-04-10" },
  { id: "mem_failure_1", type: "failure", content: "Attempted to parse entire DOM of wikipedia. Hit token limit. Must strictly use summarize endpoint.", score: 0.82, origin: "run_1f8c2e", date: "2026-04-12" },
  { id: "mem_experience_1", type: "experience", content: "Successfully recovered from a missing API key error by defaulting to the cache block.", score: 0.99, origin: "run_7c9e1a", date: "2026-04-15" }
];

export const MOCK_EVAL = {
  improvements: [
    { label: "Memory Retrieval Delta", value: "+31%", type: "positive" },
    { label: "Semantic Reranking", value: "Neutral", type: "neutral" },
    { label: "Failure Recovery", value: "-12%", type: "negative" }
  ],
  chartData: [
    { name: "Pure FTS", score: 0.61 },
    { name: "Semantics Only", score: 0.74 },
    { name: "Hybrid (No Rerank)", score: 0.68 },
    { name: "Full Pipeline", score: 0.85 }
  ]
};

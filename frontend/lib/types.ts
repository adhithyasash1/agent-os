export type AgentConfig = {
  profile: string;
  llm_backend: string;
  prompt_version: string;
  force_local_only: boolean;
  debug_verbose: boolean;
  context_char_budget: number;
  max_steps: number;
  flags: {
    enable_memory: boolean;
    enable_planner: boolean;
    enable_tools: boolean;
    enable_reflection: boolean;
    enable_llm_judge: boolean;
    enable_otel: boolean;
  };
};

export type HealthResponse = {
  status: "ok" | "degraded";
  dependencies: {
    memory: string;
    traces: string;
    ollama?: string;
    otel: string;
  };
  config: AgentConfig;
};

export type MemoryStats = {
  count: number;
  by_kind: {
    working: number;
    episodic: number;
    semantic: number;
    experience: number;
    style: number;
    failure: number;
  };
};

export type ToolInfo = {
  name: string;
  description: string;
  args: Record<string, any>;
};

export type RunSummary = {
  run_id: string;
  user_input: string;
  final_output?: string;
  score: number;
  profile: string;
  flags: string;
  prompt_version: string;
  started_at: string;
  finished_at?: string;
  total_latency_ms: number;
  total_tokens: number;
  status: "running" | "ok" | "timeout_synthesis" | "error";
  reflection_count: number;
  user_feedback?: {
    rating?: number;
    notes?: string;
  };
};

export type TraceEvent = {
  id?: number;
  run_id: string;
  step: number;
  kind: "understand" | "retrieve" | "plan" | "tool_call" | "verify" | "reflect" | "final" | "error";
  name?: string;
  input?: any;
  output?: any;
  latency_ms?: number;
  error?: string | null;
  attributes?: Record<string, any>;
  ts?: string;
};

export type RunTransition = {
  id: number;
  run_id: string;
  step: number;
  stage: string;
  state: any;
  action: any;
  observation: any;
  score?: number | null;
  done?: boolean;
  status?: string | null;
  attributes?: Record<string, any>;
  ts?: string;
};

export type RunDetail = RunSummary & {
  events: TraceEvent[];
  transitions: RunTransition[];
};

export type CreateRunResponse = RunSummary & {
  answer: string;
  steps: number;
  tool_calls: any[];
  memory_hits: any[];
  context_ids: string[];
  verification: {
    score: number;
    judge_correct?: number;
    judge_grounded?: number;
    judge_reason?: string;
    verifier_miscalibration?: boolean;
    grounding_overlap?: number;
  };
};

export type AsyncRunResponse = {
  run_id: string;
  status: "running";
};

export type MemorySearchResult = {
  id: number;
  kind: string;
  text: string;
  salience: number;
  utility_score: number;
  source_run_id?: string;
  meta?: any;
};

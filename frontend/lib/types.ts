export type AgentConfig = {
  profile: string;
  llm_backend: string;
  prompt_version: string;
  force_local_only: boolean;
  debug_verbose: boolean;
  context_char_budget: number;
  max_steps: number;
  flags: Record<string, boolean>;
};

export type HealthResponse = {
  status: string;
  dependencies: Record<string, string>;
  config: AgentConfig;
};

export type MemoryStats = {
  count: number;
  by_kind: Record<string, number>;
};

export type ToolInfo = {
  name: string;
  description: string;
  args: Record<string, string>;
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
  status: string;
  user_feedback?: {
    rating?: number;
    notes?: string;
  };
};

export type TraceEvent = {
  id?: number;
  run_id: string;
  step: number;
  kind: string;
  name?: string;
  input?: unknown;
  output?: unknown;
  latency_ms?: number;
  error?: string | null;
  attributes?: Record<string, unknown>;
  ts?: string;
};

export interface RunTransition {
  id: number;
  run_id: string;
  step: number;
  stage: string;
  state: any;
  action: any;
  observation: any;
  score?: number | null;
  done?: number | boolean;
  status?: string | null;
  attributes?: Record<string, unknown>;
  ts?: string;
}

export type RunDetail = RunSummary & {
  events: TraceEvent[];
  transitions: RunTransition[];
};

export type CreateRunResponse = {
  run_id: string;
  answer: string;
  score: number;
  steps: number;
  status: string;
  tool_calls: Array<Record<string, unknown>>;
  latency_ms: number;
  error?: string | null;
  memory_hits: Array<Record<string, unknown>>;
  context_ids: string[];
  retrieval_candidates: string[];
  reflection_count: number;
  reflection_roi: number;
  rl_transition_count: number;
  prompt_version: string;
  verification: Record<string, unknown>;
  initial_score: number;
};

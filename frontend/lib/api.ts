import type {
  CreateRunResponse,
  HealthResponse,
  MemoryStats,
  RunDetail,
  RunSummary,
  ToolInfo,
  AgentConfig,
  MemorySearchResult
} from "@/lib/types";

const API_BASE =
  process.env.NEXT_PUBLIC_AGENTOS_API_BASE ?? "http://127.0.0.1:8000/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getHealth: () => apiFetch<HealthResponse>("/health"),
  getMemoryStats: () => apiFetch<MemoryStats>("/memory/stats"),
  getTools: () => apiFetch<ToolInfo[]>("/tools"),
  listRuns: (limit = 50) => apiFetch<RunSummary[]>(`/runs?limit=${limit}`),
  getRun: (runId: string) => apiFetch<RunDetail>(`/runs/${runId}`),
  createRun: (input: string) =>
    apiFetch<CreateRunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify({ input })
    }),
  createRunAsync: (input: string) =>
    apiFetch<{ run_id: string; status: "running" }>("/runs/async", {
      method: "POST",
      body: JSON.stringify({ input })
    }),
  leaveFeedback: (runId: string, payload: { rating?: number; notes?: string }) =>
    apiFetch<{ run_id: string; feedback: { rating?: number; notes?: string } }>(
      `/runs/${runId}/feedback`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  getConfig: () => apiFetch<AgentConfig>("/config"),
  patchConfig: (payload: Partial<AgentConfig["flags"] | { context_char_budget: number, profile: string }>) =>
    apiFetch<{ updated: Record<string, any>; current: AgentConfig }>("/config", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  searchMemory: (payload: { query: string; k?: number; kinds?: string[]; min_salience?: number }) =>
    apiFetch<{ results: MemorySearchResult[] }>("/memory/search", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  purgeSystem: (kind: "working" | "episodic" | "semantic" | "all") =>
    apiFetch<{ status: string; purged: string }>("/system/purge", {
      method: "POST",
      body: JSON.stringify({ kind })
    }),
};

import type {
  AsyncRunResponse,
  ConfigPatch,
  ConfigPatchResponse,
  ConfigResponse,
  EvalImprovement,
  EvalResults,
  FeedbackRequest,
  HealthResponse,
  MemoryHit,
  MemorySearchRequest,
  MemoryStats,
  RunDetail,
  RunResult,
  RunSummary,
  Tool,
} from "@/lib/types";

const ENV_BASE = process.env.NEXT_PUBLIC_AGENTOS_API_BASE;
if (!ENV_BASE && typeof window !== "undefined") {
  console.error(
    "[agentos] NEXT_PUBLIC_AGENTOS_API_BASE is not set. " +
      "Copy frontend/.env.local.example to frontend/.env.local and set the URL."
  );
}

const BASE = (ENV_BASE ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

async function parseError(response: Response): Promise<Error> {
  const detail = await response
    .json()
    .then((body) => body?.detail || body?.error || response.statusText)
    .catch(() => response.statusText);
  return new Error(detail || `${response.status} ${response.statusText}`);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return response.json() as Promise<T>;
}

async function apiText(path: string, init?: RequestInit): Promise<string> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return response.text();
}

function mean(values: number[]): number {
  if (!values.length) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function deltaType(delta: number, invert = false): EvalImprovement["type"] {
  if (Math.abs(delta) < 0.0001) {
    return "neutral";
  }
  const positive = invert ? delta < 0 : delta > 0;
  return positive ? "positive" : "negative";
}

export const api = {
  createRun(input: string): Promise<RunResult> {
    return apiFetch<RunResult>("/runs", {
      method: "POST",
      body: JSON.stringify({ input }),
    });
  },

  createRunAsync(input: string): Promise<AsyncRunResponse> {
    return apiFetch<AsyncRunResponse>("/runs/async", {
      method: "POST",
      body: JSON.stringify({ input }),
    });
  },

  getRun(run_id: string): Promise<RunDetail> {
    return apiFetch<RunDetail>(`/runs/${run_id}`);
  },

  listRuns(limit = 50): Promise<RunSummary[]> {
    return apiFetch<RunSummary[]>(`/runs?limit=${limit}`);
  },

  getMemoryStats(): Promise<MemoryStats> {
    return apiFetch<MemoryStats>("/memory/stats");
  },

  searchMemory(req: MemorySearchRequest): Promise<{ results: MemoryHit[] }> {
    return apiFetch<{ results: MemoryHit[] }>("/memory/search", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  getTools(): Promise<Tool[]> {
    return apiFetch<Tool[]>("/tools");
  },

  getHealth(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/health");
  },

  getConfig(): Promise<ConfigResponse> {
    return apiFetch<ConfigResponse>("/config");
  },

  patchConfig(patch: ConfigPatch): Promise<ConfigPatchResponse> {
    return apiFetch<ConfigPatchResponse>("/config", {
      method: "POST",
      body: JSON.stringify(patch),
    });
  },

  purgeSystem(kind: string): Promise<{ status: string; purged?: string }> {
    return apiFetch<{ status: string; purged?: string }>("/system/purge", {
      method: "POST",
      body: JSON.stringify({ kind }),
    });
  },

  dumpContext(runId?: string): Promise<{ status: string; target: string }> {
    const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return apiFetch<{ status: string; target: string }>(`/debug/dump-context${suffix}`, {
      method: "POST",
    });
  },

  async leaveFeedback(run_id: string, feedback: FeedbackRequest): Promise<void> {
    await apiFetch<{ run_id: string; feedback: FeedbackRequest }>(`/runs/${run_id}/feedback`, {
      method: "POST",
      body: JSON.stringify(feedback),
    });
  },

  exportRLHF(format = "jsonl"): Promise<string> {
    return apiText(`/runs/export?format=${encodeURIComponent(format)}`);
  },

  async getEvalResults(): Promise<EvalResults> {
    const runs = await apiFetch<RunSummary[]>("/runs?limit=200");
    const latestRuns = runs.slice(0, 20).reverse();
    const lastFive = runs.slice(0, 5);
    const previousFive = runs.slice(5, 10);

    const overall_score = mean(runs.map((run) => run.score || 0));
    const success_rate = runs.length
      ? runs.filter((run) => run.status === "ok").length / runs.length
      : 0;
    const mean_latency_ms = mean(runs.map((run) => run.total_latency_ms || 0));

    const toolCalls = runs.reduce((sum, run) => sum + (run.tool_call_count || 0), 0);
    const toolCallSuccesses = runs.reduce(
      (sum, run) => sum + (run.tool_call_success_count || 0),
      0,
    );
    const tool_call_success_rate = toolCalls ? toolCallSuccesses / toolCalls : 0;

    const reflectionRuns = runs.filter((run) => (run.reflection_count || 0) > 0);
    const reflection_roi = reflectionRuns.length
      ? mean(reflectionRuns.map((run) => run.reflection_roi || 0))
      : 0;

    const recentScore = mean(lastFive.map((run) => run.score || 0));
    const previousScore = mean(previousFive.map((run) => run.score || 0));
    const recentSuccess = lastFive.length
      ? lastFive.filter((run) => run.status === "ok").length / lastFive.length
      : 0;
    const previousSuccess = previousFive.length
      ? previousFive.filter((run) => run.status === "ok").length / previousFive.length
      : 0;
    const recentLatency = mean(lastFive.map((run) => run.total_latency_ms || 0));
    const previousLatency = mean(previousFive.map((run) => run.total_latency_ms || 0));

    return {
      runCount: runs.length,
      overall_score,
      success_rate,
      mean_latency_ms,
      tool_call_success_rate,
      reflection_roi,
      chartData: latestRuns.map((run) => ({
        started_at: run.started_at,
        label: new Date(run.started_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        }),
        score: run.score || 0,
      })),
      improvements: [
        {
          label: "Score Delta",
          value: `${(recentScore - previousScore >= 0 ? "+" : "")}${(recentScore - previousScore).toFixed(2)}`,
          type: deltaType(recentScore - previousScore),
        },
        {
          label: "Success Delta",
          value: `${(recentSuccess - previousSuccess >= 0 ? "+" : "")}${((recentSuccess - previousSuccess) * 100).toFixed(1)}%`,
          type: deltaType(recentSuccess - previousSuccess),
        },
        {
          label: "Latency Delta",
          value: `${Math.round(recentLatency - previousLatency)} ms`,
          type: deltaType(recentLatency - previousLatency, true),
        },
      ],
      runs,
    };
  },
};

export { BASE };

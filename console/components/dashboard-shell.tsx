"use client";

import { useEffect, useState, startTransition, useDeferredValue } from "react";
import type { ComponentType } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Activity, BrainCircuit, Database, Radar } from "lucide-react";

import { RunComposer } from "@/components/run-composer";
import { RunDetail } from "@/components/run-detail";
import { RunList } from "@/components/run-list";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatPercent, formatScore, scoreTone } from "@/lib/utils";

export function DashboardShell() {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const deferredSearch = useDeferredValue(search);

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 15000
  });
  const memoryQuery = useQuery({
    queryKey: ["memory-stats"],
    queryFn: api.getMemoryStats,
    refetchInterval: 15000
  });
  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: api.getTools
  });
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(40),
    refetchInterval: 15000
  });
  const runDetailQuery = useQuery({
    queryKey: ["run", selectedRunId],
    queryFn: () => api.getRun(selectedRunId as string),
    enabled: Boolean(selectedRunId),
    refetchInterval: 15000
  });

  useEffect(() => {
    const firstRun = runsQuery.data?.[0];
    if (!firstRun) {
      setSelectedRunId(null);
      return;
    }
    if (!selectedRunId || !runsQuery.data?.some((run) => run.run_id === selectedRunId)) {
      setSelectedRunId(firstRun.run_id);
    }
  }, [runsQuery.data, selectedRunId]);

  const createRun = useMutation({
    mutationFn: api.createRun,
    onSuccess: async (result) => {
      setPrompt("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["runs"] }),
        queryClient.invalidateQueries({ queryKey: ["memory-stats"] })
      ]);
      const detail = await api.getRun(result.run_id);
      queryClient.setQueryData(["run", result.run_id], detail);
      startTransition(() => setSelectedRunId(result.run_id));
    }
  });

  const feedbackMutation = useMutation({
    mutationFn: (payload: { rating?: number; notes?: string }) =>
      api.leaveFeedback(selectedRunId as string, payload),
    onSuccess: async () => {
      if (selectedRunId) {
        const detail = await api.getRun(selectedRunId);
        queryClient.setQueryData(["run", selectedRunId], detail);
        queryClient.invalidateQueries({ queryKey: ["runs"] });
      }
    }
  });

  const runs = (runsQuery.data ?? []).filter((run) => {
    const matchesStatus = statusFilter === "all" || run.status === statusFilter;
    const matchesSearch =
      !deferredSearch.trim() ||
      run.user_input.toLowerCase().includes(deferredSearch.trim().toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const visibleRuns = runsQuery.data ?? [];
  const successRate =
    visibleRuns.length > 0
      ? visibleRuns.filter((run) => run.score >= 0.6).length / visibleRuns.length
      : 0;
  const averageScore =
    visibleRuns.length > 0
      ? visibleRuns.reduce((sum, run) => sum + (run.score ?? 0), 0) / visibleRuns.length
      : 0;

  return (
    <main className="min-h-screen bg-shell-glow px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1600px] space-y-5">
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]"
        >
          <Card className="p-7">
            <CardHeader>
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-accent">Agentos Console</p>
                <CardTitle className="mt-3 text-4xl">Observe memory, planning, verification, and reward traces in one place.</CardTitle>
                <CardDescription className="mt-3 max-w-2xl text-base">
                  This frontend sits on the richer runtime contracts now available in the backend: tiered memory,
                  context packet metadata, ReAct planner outputs, OpenTelemetry-ready trace tags, and RL transitions.
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge>{healthQuery.data?.status ?? "connecting"}</Badge>
                <Badge>{healthQuery.data?.config.profile ?? "profile"}</Badge>
                <Badge>{healthQuery.data?.config.llm_backend ?? "llm"}</Badge>
                <Badge>{healthQuery.data?.config.prompt_version ?? "prompt"}</Badge>
              </div>
            </CardHeader>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            <MetricCard
              icon={Activity}
              label="Recent Runs"
              value={String(visibleRuns.length)}
              detail="Live run window"
            />
            <MetricCard
              icon={BrainCircuit}
              label="Success Rate"
              value={formatPercent(successRate)}
              detail="score ≥ 0.60"
            />
            <MetricCard
              icon={Radar}
              label="Avg Score"
              value={formatScore(averageScore)}
              detail="visible run average"
              tone={scoreTone(averageScore)}
            />
            <MetricCard
              icon={Database}
              label="Memory Rows"
              value={String(memoryQuery.data?.count ?? 0)}
              detail={`working ${memoryQuery.data?.by_kind.working ?? 0} • episodic ${memoryQuery.data?.by_kind.episodic ?? 0} • semantic ${memoryQuery.data?.by_kind.semantic ?? 0}`}
            />
          </div>
        </motion.section>

        <section className="grid gap-5 xl:grid-cols-[0.92fr_0.88fr_1.2fr]">
          <div className="space-y-5">
            <RunComposer
              value={prompt}
              onChange={setPrompt}
              onSubmit={() => createRun.mutate(prompt)}
              isPending={createRun.isPending}
              statusText={
                createRun.isSuccess
                  ? `Latest score ${formatScore(createRun.data?.score)} • ${createRun.data?.latency_ms ?? 0} ms`
                  : createRun.isError
                    ? (createRun.error as Error).message
                    : "Send a prompt to create a fresh run."
              }
            />
            <Card className="p-6">
              <CardHeader>
                <div>
                  <CardTitle>Runtime Status</CardTitle>
                  <CardDescription>Health checks, feature flags, and tool registry.</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {Object.entries(healthQuery.data?.dependencies ?? {}).map(([key, value]) => (
                    <Badge key={key}>
                      {key}: {value}
                    </Badge>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(healthQuery.data?.config.flags ?? {}).map(([key, value]) => (
                    <Badge key={key}>{key}: {value ? "on" : "off"}</Badge>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {(toolsQuery.data ?? []).map((tool) => (
                    <Badge key={tool.name}>{tool.name}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <RunList
            runs={runs}
            selectedRunId={selectedRunId}
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            onSelect={(runId) => startTransition(() => setSelectedRunId(runId))}
          />

          <RunDetail
            run={runDetailQuery.data}
            isPending={runDetailQuery.isPending}
            feedbackPending={feedbackMutation.isPending}
            onSubmitFeedback={(payload) => feedbackMutation.mutate(payload)}
          />
        </section>
      </div>
    </main>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted">{label}</p>
            <p className={`mt-3 font-serif text-4xl tracking-[-0.04em] ${tone ?? "text-white"}`}>{value}</p>
            <p className="mt-2 text-sm text-muted">{detail}</p>
          </div>
          <div className="rounded-full border border-white/10 bg-white/5 p-3 text-accent">
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = "http://localhost:8000/api/v1";

interface HealthData {
  status: string;
  dependencies: Record<string, string>;
}

interface MemoryStats {
  vector_count: number;
  episodic_count: number;
  graph_nodes: number;
  graph_edges: number;
}

export default function Home() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [healthStatus, setHealthStatus] = useState<"loading" | "ok" | "degraded" | "error">("loading");
  const [stats, setStats] = useState<MemoryStats>({
    vector_count: 0,
    episodic_count: 0,
    graph_nodes: 0,
    graph_edges: 0,
  });
  const [runCount, setRunCount] = useState(0);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/health`).then((r) => r.json()),
      fetch(`${API}/memory/stats`)
        .then((r) => r.json())
        .catch(() => null),
      fetch(`${API}/runs/`)
        .then((r) => r.json())
        .catch(() => []),
    ])
      .then(([h, m, r]) => {
        setHealth(h);
        setHealthStatus(h?.status === "ok" ? "ok" : h?.status === "degraded" ? "degraded" : "error");
        if (m) setStats(m);
        if (Array.isArray(r)) setRunCount(r.length);
      })
      .catch(() => setHealthStatus("error"));
  }, []);

  const statusColor =
    healthStatus === "ok"
      ? "bg-emerald-400"
      : healthStatus === "degraded"
      ? "bg-amber-400"
      : healthStatus === "error"
      ? "bg-red-400"
      : "bg-amber-400 animate-pulse";

  const statusText =
    healthStatus === "ok"
      ? "All systems operational"
      : healthStatus === "degraded"
      ? "Running with degraded services"
      : healthStatus === "error"
      ? "Backend offline"
      : "Connecting...";

  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <div className="max-w-2xl w-full space-y-10">
        {/* Hero */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/60 border border-slate-700/50 text-xs text-slate-400 mb-4">
            <div className={`w-1.5 h-1.5 rounded-full ${statusColor}`} />
            {statusText}
          </div>
          <h1 className="text-4xl font-bold tracking-tight">
            Welcome to{" "}
            <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              AgentOS
            </span>
          </h1>
          <p className="text-slate-400 text-lg max-w-md mx-auto">
            A self-reflective, memory-augmented AI agent platform running
            locally on your machine.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total Runs" value={runCount} color="blue" />
          <StatCard label="Vectors" value={stats.vector_count} color="purple" />
          <StatCard label="Graph Nodes" value={stats.graph_nodes} color="emerald" />
          <StatCard label="Graph Edges" value={stats.graph_edges} color="amber" />
        </div>

        {/* Dependency Health */}
        {health?.dependencies && (
          <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-400 tracking-wide uppercase">
              Dependencies
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {Object.entries(health.dependencies).map(([name, status]) => (
                <div
                  key={name}
                  className="flex items-center gap-2 px-3 py-2 bg-slate-800/40 rounded-lg"
                >
                  <div
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      status === "ok" || status === "configured"
                        ? "bg-emerald-400"
                        : status === "disabled"
                        ? "bg-slate-500"
                        : "bg-red-400"
                    }`}
                  />
                  <span className="text-xs text-slate-300 capitalize truncate">
                    {name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick actions */}
        <div className="flex gap-3 justify-center">
          <Link
            href="/chat"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold text-sm transition-colors"
          >
            Start chatting
          </Link>
          <Link
            href="/runs"
            className="px-6 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl font-semibold text-sm transition-colors"
          >
            View runs
          </Link>
        </div>

        {/* Architecture */}
        <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-400 tracking-wide uppercase">
            Architecture
          </h3>
          <div className="flex items-center justify-between gap-2 text-sm overflow-x-auto">
            {["Executor", "Planner", "Evaluator", "Memory"].map((step, i) => (
              <div key={step} className="flex items-center gap-2 shrink-0">
                <div className="px-4 py-2 bg-slate-800 rounded-lg border border-slate-700/50 font-medium text-slate-300">
                  {step}
                </div>
                {i < 3 && (
                  <svg
                    className="w-4 h-4 text-slate-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                )}
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500">
            Loops back to Executor if evaluation score is below 0.7. Memory
            manager decides what to promote, summarize, or forget.
          </p>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "text-blue-400",
    purple: "text-purple-400",
    emerald: "text-emerald-400",
    amber: "text-amber-400",
  };
  return (
    <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-3xl font-mono font-bold ${colorMap[color]}`}>
        {value}
      </p>
    </div>
  );
}

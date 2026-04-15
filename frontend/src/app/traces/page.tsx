"use client";

import { useState, useEffect } from "react";

const API = "http://localhost:8000/api/v1";

interface Run {
  run_id: string;
  task_id: string;
  score: number;
  timestamp: string;
  trajectory: any[];
  final_answer?: string;
  critique?: string;
  human_feedback?: { score: number; comment: string } | null;
  context_used?: { vector?: string; episodic?: string; graph?: string };
}

export default function TracesPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"trajectory" | "answer" | "critique" | "context">("trajectory");

  useEffect(() => {
    fetch(`${API}/runs/`)
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data.reverse() : [];
        setRuns(list);
        if (list.length > 0) setSelected(list[0]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex h-full">
      {/* Trace list */}
      <div className="w-72 border-r border-slate-800/60 overflow-y-auto shrink-0">
        <div className="p-4 border-b border-slate-800/60">
          <h2 className="text-lg font-bold tracking-tight">Traces</h2>
          <p className="text-xs text-slate-500 mt-1">{runs.length} recorded</p>
        </div>
        {loading ? (
          <div className="p-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 bg-slate-900/50 rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {runs.map((run) => (
              <button
                key={run.run_id}
                onClick={() => {
                  setSelected(run);
                  setTab("trajectory");
                }}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                  selected?.run_id === run.run_id
                    ? "bg-blue-600/15 text-blue-400"
                    : "hover:bg-slate-800/50 text-slate-400"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs">{run.run_id}</span>
                  <div className="flex items-center gap-1.5">
                    {run.human_feedback && (
                      <span className="text-[10px]">
                        {run.human_feedback.score > 0 ? "\u{1F44D}" : "\u{1F44E}"}
                      </span>
                    )}
                    <span
                      className={`text-xs font-bold ${
                        run.score >= 0.7
                          ? "text-emerald-400"
                          : "text-amber-400"
                      }`}
                    >
                      {run.score.toFixed(2)}
                    </span>
                  </div>
                </div>
                <p className="text-[10px] text-slate-600 mt-0.5 truncate">
                  {run.task_id}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Trace detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {selected ? (
          <div className="max-w-3xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold">Run {selected.run_id}</h3>
                <p className="text-xs text-slate-500 mt-1 font-mono">
                  {selected.task_id}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {selected.human_feedback && (
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold ${
                      selected.human_feedback.score > 0
                        ? "bg-emerald-500/15 text-emerald-400"
                        : "bg-rose-500/15 text-rose-400"
                    }`}
                  >
                    {selected.human_feedback.score > 0
                      ? "Positive"
                      : "Negative"}
                  </span>
                )}
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold ${
                    selected.score >= 0.7
                      ? "bg-emerald-500/15 text-emerald-400"
                      : "bg-amber-500/15 text-amber-400"
                  }`}
                >
                  Score: {selected.score.toFixed(2)}
                </span>
              </div>
            </div>

            <div className="text-xs text-slate-500">
              {new Date(selected.timestamp).toLocaleString()}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 bg-slate-900/50 rounded-lg p-1">
              {(
                [
                  { key: "trajectory", label: "Trajectory" },
                  { key: "answer", label: "Answer" },
                  { key: "critique", label: "Critique" },
                  { key: "context", label: "Context" },
                ] as const
              ).map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex-1 text-xs font-medium py-2 rounded-md transition-colors ${
                    tab === key
                      ? "bg-slate-800 text-white"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            {tab === "trajectory" && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                  Tool Trajectory
                </h4>
                {selected.trajectory && selected.trajectory.length > 0 ? (
                  selected.trajectory.map((step, i) => (
                    <div
                      key={i}
                      className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-4 space-y-2"
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                          {i + 1}
                        </span>
                        <span className="text-sm font-medium text-slate-300">
                          {step.tool || "Step"}
                        </span>
                        <span
                          className={`text-xs ml-auto ${
                            step.status === "success"
                              ? "text-emerald-400"
                              : "text-red-400"
                          }`}
                        >
                          {step.status}
                        </span>
                      </div>
                      {(step.info || step.error || step.content) && (
                        <pre className="text-xs text-slate-500 bg-slate-950/50 rounded-lg p-3 overflow-x-auto">
                          {step.info ||
                            step.error ||
                            step.content?.slice(0, 500)}
                        </pre>
                      )}
                    </div>
                  ))
                ) : (
                  <pre className="text-xs text-slate-400 bg-slate-900 rounded-lg p-4 overflow-x-auto">
                    {JSON.stringify(selected.trajectory, null, 2)}
                  </pre>
                )}
              </div>
            )}

            {tab === "answer" && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">
                  Final Answer
                </h4>
                {selected.final_answer ? (
                  <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                    {selected.final_answer}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 italic">
                    No final answer recorded for this run.
                  </p>
                )}
              </div>
            )}

            {tab === "critique" && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-amber-400 uppercase tracking-wider">
                  Evaluator Critique
                </h4>
                {selected.critique ? (
                  <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5 text-sm text-slate-400 whitespace-pre-wrap leading-relaxed">
                    {selected.critique}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 italic">
                    No critique recorded for this run.
                  </p>
                )}
              </div>
            )}

            {tab === "context" && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">
                  Memory Context Retrieved
                </h4>
                {selected.context_used ? (
                  <div className="space-y-3">
                    {(["vector", "episodic", "graph"] as const).map((tier) => {
                      const content = selected.context_used?.[tier];
                      return (
                        <div
                          key={tier}
                          className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-4"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-400 uppercase">
                              {tier}
                            </span>
                            <span className="text-[10px] text-slate-600 font-mono">
                              {content ? `${content.length} chars` : "empty"}
                            </span>
                          </div>
                          {content ? (
                            <pre className="text-xs text-slate-500 bg-slate-950/50 rounded-lg p-3 overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">
                              {content}
                            </pre>
                          ) : (
                            <p className="text-xs text-slate-600 italic">
                              No {tier} context was retrieved
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 italic">
                    No context data recorded for this run.
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500">
            <p>Select a trace to view details</p>
          </div>
        )}
      </div>
    </div>
  );
}

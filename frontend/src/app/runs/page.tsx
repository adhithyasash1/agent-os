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

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchRuns = () => {
    setLoading(true);
    fetch(`${API}/runs/`)
      .then((r) => r.json())
      .then((data) => setRuns(Array.isArray(data) ? data.reverse() : []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const submitFeedback = async (taskId: string, score: number) => {
    try {
      await fetch(`${API}/runs/${taskId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score, comment: "" }),
      });
      // Refresh to show updated feedback
      fetchRuns();
    } catch (err) {
      console.error("Feedback failed:", err);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Execution History</h2>
        <button
          onClick={fetchRuns}
          className="text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 bg-slate-900/50 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-12 text-center">
          <p className="text-slate-500">
            No runs recorded yet. Start a chat to create your first run.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <div
              key={run.run_id}
              className="bg-slate-900/50 border border-slate-800/60 rounded-xl overflow-hidden"
            >
              {/* Run header */}
              <button
                onClick={() =>
                  setExpanded(expanded === run.run_id ? null : run.run_id)
                }
                className="w-full flex items-center gap-4 px-5 py-4 hover:bg-slate-800/30 transition-colors text-left"
              >
                <span className="font-mono text-xs text-slate-500 w-28 shrink-0">
                  {run.run_id}
                </span>
                <span className="text-sm text-slate-300 truncate flex-1">
                  {run.task_id}
                </span>

                {/* Feedback indicator */}
                {run.human_feedback && (
                  <span
                    className={`text-xs ${
                      run.human_feedback.score > 0
                        ? "text-emerald-400"
                        : "text-rose-400"
                    }`}
                  >
                    {run.human_feedback.score > 0 ? "\u{1F44D}" : "\u{1F44E}"}
                  </span>
                )}

                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    run.score >= 0.7
                      ? "bg-emerald-500/15 text-emerald-400"
                      : "bg-amber-500/15 text-amber-400"
                  }`}
                >
                  {run.score.toFixed(2)}
                </span>
                <span className="text-xs text-slate-600 w-36 shrink-0 text-right">
                  {new Date(run.timestamp).toLocaleString()}
                </span>
                <svg
                  className={`w-4 h-4 text-slate-500 transition-transform ${
                    expanded === run.run_id ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {/* Expanded detail */}
              {expanded === run.run_id && (
                <div className="border-t border-slate-800/60 px-5 py-4 bg-slate-950/50 space-y-4">
                  {/* Final Answer */}
                  {run.final_answer && (
                    <div>
                      <p className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2">
                        Final Answer
                      </p>
                      <div className="text-sm text-slate-300 bg-slate-900 rounded-lg p-4 max-h-40 overflow-y-auto whitespace-pre-wrap">
                        {run.final_answer}
                      </div>
                    </div>
                  )}

                  {/* Critique */}
                  {run.critique && (
                    <div>
                      <p className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2">
                        Evaluator Critique
                      </p>
                      <div className="text-xs text-slate-400 bg-slate-900 rounded-lg p-4 whitespace-pre-wrap">
                        {run.critique}
                      </div>
                    </div>
                  )}

                  {/* Trajectory */}
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                      Tool Trajectory
                    </p>
                    {run.trajectory && run.trajectory.length > 0 ? (
                      <div className="space-y-1.5">
                        {run.trajectory.map((step: any, i: number) => (
                          <div
                            key={i}
                            className="flex items-center gap-3 text-xs bg-slate-900 rounded-lg px-3 py-2"
                          >
                            <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-400 shrink-0">
                              {i + 1}
                            </span>
                            <span className="font-mono text-slate-300">
                              {step.tool || "unknown"}
                            </span>
                            <span
                              className={`ml-auto text-[10px] px-2 py-0.5 rounded-full ${
                                step.status === "success"
                                  ? "bg-emerald-500/10 text-emerald-400"
                                  : "bg-red-500/10 text-red-400"
                              }`}
                            >
                              {step.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <pre className="text-xs text-slate-400 bg-slate-900 rounded-lg p-4 overflow-x-auto">
                        {JSON.stringify(run.trajectory, null, 2)}
                      </pre>
                    )}
                  </div>

                  {/* Context Used */}
                  {run.context_used &&
                    Object.values(run.context_used).some((v) => v) && (
                      <div>
                        <p className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2">
                          Memory Context Used
                        </p>
                        <div className="grid grid-cols-3 gap-2">
                          {(["vector", "episodic", "graph"] as const).map(
                            (tier) => (
                              <div
                                key={tier}
                                className="bg-slate-900 rounded-lg p-3"
                              >
                                <p className="text-[10px] font-bold text-slate-500 uppercase mb-1">
                                  {tier}
                                </p>
                                <p className="text-[10px] text-slate-400 truncate">
                                  {run.context_used?.[tier]
                                    ? `${run.context_used[tier]!.length} chars`
                                    : "empty"}
                                </p>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}

                  {/* Feedback */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/40">
                    <p className="text-xs text-slate-500">
                      {run.human_feedback
                        ? `Feedback: ${
                            run.human_feedback.score > 0 ? "Positive" : "Negative"
                          }`
                        : "No feedback yet"}
                    </p>
                    {!run.human_feedback && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => submitFeedback(run.task_id, 1)}
                          className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                        >
                          Good
                        </button>
                        <button
                          onClick={() => submitFeedback(run.task_id, -1)}
                          className="text-xs px-3 py-1.5 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-colors"
                        >
                          Bad
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

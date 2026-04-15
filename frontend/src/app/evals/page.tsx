"use client";

import { useState, useEffect } from "react";

const API = "http://localhost:8000/api/v1";

interface Run {
  run_id: string;
  task_id: string;
  score: number;
  timestamp: string;
}

export default function EvalsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/runs/`)
      .then((r) => r.json())
      .then((data) => setRuns(Array.isArray(data) ? data : []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  const avgScore = runs.length > 0 ? runs.reduce((s, r) => s + r.score, 0) / runs.length : 0;
  const passCount = runs.filter((r) => r.score >= 0.7).length;
  const failCount = runs.length - passCount;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <h2 className="text-2xl font-bold tracking-tight">Evaluations</h2>

      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-slate-900/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5">
              <p className="text-xs text-slate-500 mb-1">Average Score</p>
              <p className={`text-3xl font-mono font-bold ${avgScore >= 0.7 ? "text-emerald-400" : "text-amber-400"}`}>
                {avgScore.toFixed(2)}
              </p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5">
              <p className="text-xs text-slate-500 mb-1">Passed ({">="}0.7)</p>
              <p className="text-3xl font-mono font-bold text-emerald-400">{passCount}</p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5">
              <p className="text-xs text-slate-500 mb-1">Below Threshold</p>
              <p className="text-3xl font-mono font-bold text-amber-400">{failCount}</p>
            </div>
          </div>

          {/* Score distribution */}
          {runs.length > 0 && (
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 space-y-4">
              <h3 className="text-lg font-semibold">Score History</h3>
              <div className="flex items-end gap-1 h-32">
                {runs.map((run, i) => {
                  const height = Math.max(run.score * 100, 4);
                  return (
                    <div
                      key={i}
                      className="group relative flex-1 flex flex-col justify-end"
                    >
                      <div
                        className={`rounded-t transition-all ${
                          run.score >= 0.7 ? "bg-emerald-500/60" : "bg-amber-500/60"
                        } group-hover:opacity-100 opacity-80`}
                        style={{ height: `${height}%` }}
                      />
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-800 text-xs px-2 py-1 rounded hidden group-hover:block whitespace-nowrap z-10">
                        {run.score.toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between text-xs text-slate-600">
                <span>Oldest</span>
                <span className="border-t border-dashed border-slate-700 flex-1 mx-4 self-center" />
                <span>Latest</span>
              </div>
            </div>
          )}

          {runs.length === 0 && (
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-12 text-center">
              <p className="text-slate-500">No evaluations recorded yet.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

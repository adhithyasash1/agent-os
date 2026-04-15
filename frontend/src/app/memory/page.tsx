"use client";

import { useState, useEffect } from "react";

const API = "http://localhost:8000/api/v1";

interface MemoryStats {
  vector_count: number;
  episodic_count: number;
  graph_nodes: number;
  graph_edges: number;
}

interface SearchResults {
  vector: Array<{ content: string; metadata: Record<string, any> }>;
  episodic: Array<{ content: string; score: number }>;
  graph: Array<{
    type: string;
    entity?: string;
    compiled_truth?: string;
    related_task?: string;
    score?: number;
    tools_used?: string[];
    related_entities?: string[];
    intent?: string;
  }>;
}

interface ConsolidationReport {
  started_at: string;
  completed_at?: string;
  duplicates_merged: number;
  contradictions_resolved: number;
  low_value_pruned: number;
  episodes_compressed: number;
  truths_compiled?: number;
  errors: string[];
}

export default function MemoryPage() {
  const [stats, setStats] = useState<MemoryStats>({
    vector_count: 0,
    episodic_count: 0,
    graph_nodes: 0,
    graph_edges: 0,
  });
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [consolidationReport, setConsolidationReport] =
    useState<ConsolidationReport | null>(null);

  const fetchStats = () => {
    fetch(`${API}/memory/stats`)
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const res = await fetch(
        `${API}/memory/search?query=${encodeURIComponent(query)}`
      );
      const data = await res.json();
      setResults(data);
    } catch {
      setResults(null);
    } finally {
      setSearching(false);
    }
  };

  const totalResults =
    (results?.vector?.length || 0) +
    (results?.episodic?.length || 0) +
    (results?.graph?.length || 0);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <h2 className="text-2xl font-bold tracking-tight">Memory System</h2>
      <p className="text-sm text-slate-500 -mt-4">
        3-tier hybrid memory: Vector (Chroma) + Episodic (Mem0) + Graph (Neo4j)
      </p>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          {
            label: "Vector Embeddings",
            value: stats.vector_count,
            color: "text-blue-400",
            icon: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7",
          },
          {
            label: "Episodic Memories",
            value: stats.episodic_count,
            color: "text-purple-400",
            icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
          },
          {
            label: "Graph Nodes",
            value: stats.graph_nodes,
            color: "text-emerald-400",
            icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
          },
          {
            label: "Graph Edges",
            value: stats.graph_edges,
            color: "text-amber-400",
            icon: "M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01",
          },
        ].map(({ label, value, color, icon }) => (
          <div
            key={label}
            className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5 flex items-center gap-4"
          >
            <div className="p-2.5 rounded-lg bg-slate-800/50">
              <svg
                className={`w-5 h-5 ${color}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d={icon}
                />
              </svg>
            </div>
            <div>
              <p className="text-xs text-slate-500">{label}</p>
              <p className={`text-2xl font-mono font-bold ${color}`}>{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Consolidation */}
      <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-300">
              Memory Consolidation
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Deduplicate vectors, resolve contradictions, prune low-value
              nodes, compress memories, compile entity truths.
            </p>
          </div>
          <button
            onClick={async () => {
              setConsolidating(true);
              setConsolidationReport(null);
              try {
                const res = await fetch(`${API}/memory/consolidate`, {
                  method: "POST",
                });
                const report = await res.json();
                setConsolidationReport(report);
                fetchStats();
              } catch {
                setConsolidationReport({
                  started_at: new Date().toISOString(),
                  duplicates_merged: 0,
                  contradictions_resolved: 0,
                  low_value_pruned: 0,
                  episodes_compressed: 0,
                  errors: ["Failed to connect to backend"],
                });
              } finally {
                setConsolidating(false);
              }
            }}
            disabled={consolidating}
            className="px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-400 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            {consolidating ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin" />
                Consolidating...
              </span>
            ) : (
              "Run Consolidation"
            )}
          </button>
        </div>

        {consolidationReport && (
          <div className="bg-slate-950/60 border border-slate-800/40 rounded-xl p-4 space-y-2">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {[
                {
                  label: "Duplicates Merged",
                  value: consolidationReport.duplicates_merged,
                  color: "text-blue-400",
                },
                {
                  label: "Contradictions Resolved",
                  value: consolidationReport.contradictions_resolved,
                  color: "text-amber-400",
                },
                {
                  label: "Low-Value Pruned",
                  value: consolidationReport.low_value_pruned,
                  color: "text-rose-400",
                },
                {
                  label: "Episodes Compressed",
                  value: consolidationReport.episodes_compressed,
                  color: "text-emerald-400",
                },
                {
                  label: "Truths Compiled",
                  value: consolidationReport.truths_compiled ?? 0,
                  color: "text-cyan-400",
                },
              ].map(({ label, value, color }) => (
                <div key={label} className="text-center">
                  <p className={`text-xl font-mono font-bold ${color}`}>
                    {value}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
            {consolidationReport.errors.length > 0 && (
              <div className="text-xs text-rose-400 bg-rose-500/10 rounded-lg p-2 mt-2">
                {consolidationReport.errors.join(", ")}
              </div>
            )}
            {consolidationReport.completed_at && (
              <p className="text-[10px] text-slate-600 text-right">
                Completed{" "}
                {new Date(consolidationReport.completed_at).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Search */}
      <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-semibold">Unified Memory Search</h3>
        <p className="text-xs text-slate-500">
          Searches across all 3 tiers simultaneously: vector similarity, episodic
          recall, and graph traversal.
        </p>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="Search through long-term memory..."
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50 placeholder-slate-600"
          />
          <button
            onClick={search}
            disabled={searching || !query.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 px-5 rounded-xl text-sm font-semibold transition-colors"
          >
            {searching ? "..." : "Search"}
          </button>
        </div>

        {/* Results */}
        {searched && (
          <div className="space-y-4 pt-2">
            {searching ? (
              <p className="text-sm text-slate-500 italic py-4 text-center">
                Searching across all memory tiers...
              </p>
            ) : totalResults === 0 ? (
              <p className="text-sm text-slate-500 italic py-4 text-center">
                No matches found in any memory tier.
              </p>
            ) : (
              <>
                {/* Vector Results */}
                {results?.vector && results.vector.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-blue-400 uppercase tracking-wider flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-blue-400" />
                      Vector Memory ({results.vector.length})
                    </p>
                    {results.vector.map((r, i) => (
                      <div
                        key={`v-${i}`}
                        className="bg-slate-950/80 border border-blue-900/20 rounded-lg px-4 py-3 flex items-start justify-between gap-4"
                      >
                        <p className="text-sm text-slate-300">{r.content}</p>
                        {r.metadata?.score != null && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-900/30 text-blue-400 shrink-0">
                            {Number(r.metadata.score).toFixed(2)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Episodic Results */}
                {results?.episodic && results.episodic.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-purple-400" />
                      Episodic Memory ({results.episodic.length})
                    </p>
                    {results.episodic.map((r, i) => (
                      <div
                        key={`e-${i}`}
                        className="bg-slate-950/80 border border-purple-900/20 rounded-lg px-4 py-3"
                      >
                        <p className="text-sm text-slate-300">{r.content}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Graph Results */}
                {results?.graph && results.graph.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      Graph Memory ({results.graph.length})
                    </p>
                    {results.graph.map((r, i) => (
                      <div
                        key={`g-${i}`}
                        className="bg-slate-950/80 border border-emerald-900/20 rounded-lg px-4 py-3 space-y-1"
                      >
                        {r.entity && (
                          <p className="text-sm font-medium text-emerald-300">
                            {r.entity}
                          </p>
                        )}
                        {r.compiled_truth && (
                          <p className="text-xs text-emerald-400/80 italic border-l-2 border-emerald-500/30 pl-2">
                            {r.compiled_truth}
                          </p>
                        )}
                        {r.related_task && (
                          <p className="text-xs text-slate-400">
                            Related task: {r.related_task}
                          </p>
                        )}
                        {r.intent && (
                          <p className="text-xs text-slate-400">
                            Past task: {r.intent}
                          </p>
                        )}
                        <div className="flex gap-2 flex-wrap">
                          {r.tools_used?.map((tool) => (
                            <span
                              key={tool}
                              className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-900/30 text-emerald-400"
                            >
                              {tool}
                            </span>
                          ))}
                          {r.related_entities?.map((ent) => (
                            <span
                              key={ent}
                              className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400"
                            >
                              {ent}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

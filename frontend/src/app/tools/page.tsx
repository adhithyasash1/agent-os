"use client";

import { useState, useEffect } from "react";

const API = "http://localhost:8000/api/v1";

interface MCPServer {
  name: string;
  description: string;
  keywords: string[];
  available: boolean;
  requires: string | null;
}

interface MCPTool {
  name: string;
  description: string;
}

const SERVER_ICONS: Record<string, string> = {
  excel: "M3 3h18v18H3V3zm3 4v10h12V7H6zm2 2h3v2H8V9zm4 0h4v2h-4V9zm-4 3h3v2H8v-2zm4 0h4v2h-4v-2z",
  markdownify: "M3 5h18v14H3V5zm2 2v10h14V7H5zm3 2v6l2-3 2 3V9h2v6h-2l-2-3-2 3H6V9h2z",
  github: "M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.009-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z",
  huggingface: "M12 2a10 10 0 100 20 10 10 0 000-20zm-2.5 7a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm5 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zM8 14s1.5 2 4 2 4-2 4-2",
  tradingview: "M3 17l6-6 4 4 8-8M17 7h4v4",
};

export default function ToolsPage() {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [serverTools, setServerTools] = useState<Record<string, MCPTool[]>>({});
  const [toolsLoading, setToolsLoading] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/tools/`)
      .then((r) => r.json())
      .then((data) => setServers(Array.isArray(data) ? data : []))
      .catch(() => setServers([]))
      .finally(() => setLoading(false));
  }, []);

  const loadTools = async (serverName: string) => {
    if (expanded === serverName) {
      setExpanded(null);
      return;
    }
    setExpanded(serverName);
    if (serverTools[serverName]) return;

    setToolsLoading(serverName);
    try {
      const res = await fetch(`${API}/tools/${serverName}/tools`);
      const data = await res.json();
      if (data.tools) {
        setServerTools((prev) => ({ ...prev, [serverName]: data.tools }));
      }
    } catch {
      setServerTools((prev) => ({ ...prev, [serverName]: [] }));
    } finally {
      setToolsLoading(null);
    }
  };

  const available = servers.filter((s) => s.available);
  const unavailable = servers.filter((s) => !s.available);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">MCP Tools</h2>
          <p className="text-sm text-slate-500 mt-1">
            Model Context Protocol servers connected to AgentOS
          </p>
        </div>
        <div className="flex gap-3">
          <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl px-4 py-2 text-center">
            <p className="text-xs text-slate-500">Connected</p>
            <p className="text-xl font-mono font-bold text-emerald-400">
              {available.length}
            </p>
          </div>
          <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl px-4 py-2 text-center">
            <p className="text-xs text-slate-500">Total</p>
            <p className="text-xl font-mono font-bold text-slate-300">
              {servers.length}
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="h-24 bg-slate-900/50 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {servers.map((server) => (
            <div
              key={server.name}
              className="bg-slate-900/50 border border-slate-800/60 rounded-2xl overflow-hidden transition-all"
            >
              <button
                onClick={() => server.available && loadTools(server.name)}
                className={`w-full text-left p-5 flex items-start gap-4 transition-colors ${
                  server.available
                    ? "hover:bg-slate-800/30 cursor-pointer"
                    : "opacity-50 cursor-not-allowed"
                }`}
              >
                {/* Icon */}
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    server.available
                      ? "bg-blue-600/15 text-blue-400"
                      : "bg-slate-800/50 text-slate-600"
                  }`}
                >
                  <svg
                    className="w-5 h-5"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      d={
                        SERVER_ICONS[server.name] ||
                        "M13 10V3L4 14h7v7l9-11h-7z"
                      }
                    />
                  </svg>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold capitalize">
                      {server.name}
                    </h3>
                    {server.available ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400">
                        Connected
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-400">
                        Needs {server.requires}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    {server.description}
                  </p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {server.keywords.map((kw) => (
                      <span
                        key={kw}
                        className="px-2 py-0.5 rounded-md text-[10px] bg-slate-800/80 text-slate-400"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Expand chevron */}
                {server.available && (
                  <svg
                    className={`w-4 h-4 text-slate-600 shrink-0 mt-1 transition-transform ${
                      expanded === server.name ? "rotate-180" : ""
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
                )}
              </button>

              {/* Expanded tools list */}
              {expanded === server.name && (
                <div className="border-t border-slate-800/60 p-5 bg-slate-950/30">
                  {toolsLoading === server.name ? (
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <div className="w-3 h-3 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                      Connecting to {server.name} server...
                    </div>
                  ) : serverTools[server.name]?.length ? (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                        Available Tools ({serverTools[server.name].length})
                      </p>
                      {serverTools[server.name].map((tool) => (
                        <div
                          key={tool.name}
                          className="flex items-start gap-3 p-3 rounded-lg bg-slate-900/50 border border-slate-800/40"
                        >
                          <div className="w-6 h-6 rounded-md bg-slate-800 flex items-center justify-center shrink-0 mt-0.5">
                            <svg
                              className="w-3 h-3 text-slate-400"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                              />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-mono text-slate-200">
                              {tool.name}
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {tool.description || "No description"}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">
                      Could not load tools. The server may not be installed or
                      accessible.
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* How it works */}
      <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-semibold">How MCP Tools Work</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600/15 flex items-center justify-center">
              <span className="text-blue-400 font-bold text-sm">1</span>
            </div>
            <p className="text-sm font-medium text-slate-300">
              Auto-Detection
            </p>
            <p className="text-xs text-slate-500">
              AgentOS scans your message for keywords and automatically matches
              relevant MCP servers.
            </p>
          </div>
          <div className="space-y-2">
            <div className="w-8 h-8 rounded-lg bg-purple-600/15 flex items-center justify-center">
              <span className="text-purple-400 font-bold text-sm">2</span>
            </div>
            <p className="text-sm font-medium text-slate-300">
              Tool Selection
            </p>
            <p className="text-xs text-slate-500">
              The executor picks the best tool from the matched server based on
              description overlap with your query.
            </p>
          </div>
          <div className="space-y-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-600/15 flex items-center justify-center">
              <span className="text-emerald-400 font-bold text-sm">3</span>
            </div>
            <p className="text-sm font-medium text-slate-300">
              Result Integration
            </p>
            <p className="text-xs text-slate-500">
              Tool outputs feed back into the planner, which synthesizes a final
              response grounded in real data.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

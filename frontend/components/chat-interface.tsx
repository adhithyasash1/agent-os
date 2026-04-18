"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { ArrowUp, Terminal, Workflow, Zap, Activity, Bug, Settings, Eraser } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { useAppStore } from "@/lib/store";
import { SettingsDialog } from "./settings-dialog";

import { api } from "@/lib/api";
import { formatScore, scoreTone } from "@/lib/utils";
import type { RunSummary, RunDetail } from "@/lib/types";

function RunDetailsAccordion({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  
  const detailQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    enabled: open, 
  });

  return (
    <div className="mt-3 overflow-hidden rounded-[16px] border border-white/5 bg-black/20 backdrop-blur-md">
      <button 
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-muted transition hover:bg-white/5"
      >
        <span className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5" />
          View Agent Thoughts & Tool Calls
        </span>
      </button>
      
      <AnimatePresence>
        {open && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-white/5"
          >
            <div className="p-4 space-y-4">
              {detailQuery.isPending && <div className="text-xs text-muted">Loading trace...</div>}
              {detailQuery.data && (
                <>
                  {detailQuery.data.events.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wider text-accent/70 flex items-center gap-1.5"><Activity className="h-3 w-3"/> Events</div>
                      <div className="space-y-1.5">
                        {detailQuery.data.events.map((e, idx) => (
                           <div key={idx} className="bg-black/40 rounded-md p-2 text-[11px] font-mono whitespace-pre-wrap text-[#A0B3C6]">
                             <span className="text-emerald-400">{e.step}. {e.kind}</span> - {e.name}
                             {e.input && <div className="mt-1 opacity-60">in: {JSON.stringify(e.input).slice(0, 80)}...</div>}
                             {e.output && <div className="opacity-60">out: {JSON.stringify(e.output).slice(0, 80)}...</div>}
                           </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {detailQuery.data.transitions.length > 0 && (
                    <div className="space-y-2 mt-4">
                      <div className="text-xs font-semibold uppercase tracking-wider text-gold/70 flex items-center gap-1.5"><Workflow className="h-3 w-3"/> Transitions</div>
                       <div className="space-y-1.5">
                        {detailQuery.data.transitions.map((t, idx) => (
                           <div key={idx} className="bg-black/40 rounded-md p-2 text-[11px] font-mono whitespace-pre-wrap text-[#A0B3C6]">
                             <span className="text-amber-400">{t.step}. {t.stage}</span> - score: {t.score ?? 'n/a'}
                             <div className="mt-1 opacity-60">{JSON.stringify(t.action)}</div>
                           </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ChatInterface() {
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const { fetchConfig } = useAppStore();

  useEffect(() => {
    fetchConfig();
  }, []);

  // Poll for completed/historical runs
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(50),
    refetchInterval: 5000,
  });

  const createRun = useMutation({
    mutationFn: api.createRun,
    onSuccess: () => {
      setInput("");
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (error) => {
      console.error("Agent Run Error:", error);
      setInput(""); 
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    }
  });

  const runs = useMemo(() => {
    // Reverse so chronologically ordered (oldest top, newest bottom)
    return [...(runsQuery.data || [])].reverse();
  }, [runsQuery.data]);

  // Auto scroll to bottom
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [runs, createRun.isPending]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || createRun.isPending) return;
    createRun.mutate(input);
  };

  return (
    <div className="flex h-full w-full flex-col bg-[#0b0f19] text-white relative">
      <SettingsDialog isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />

      {/* Header Controls */}
      <div className="flex items-center justify-end gap-3 px-6 py-4 border-b border-white/5 bg-white/2 backdrop-blur-xl sticky top-0 z-40">
        <button 
          onClick={() => setIsSettingsOpen(true)}
          className="p-2 hover:bg-white/10 rounded-full text-muted hover:text-white transition-all flex items-center gap-2 text-xs font-medium"
        >
          <Settings className="h-4 w-4" /> Config
        </button>
      </div>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl space-y-8 pb-32">
          {runs.length === 0 && !createRun.isPending && (
            <div className="text-center mt-20">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent/10">
                <Zap className="h-8 w-8 text-accent" />
              </div>
              <h2 className="text-xl font-medium tracking-tight">How can I help you today?</h2>
              <p className="mt-2 text-sm text-muted">Ask anything, I'll leverage tools and memory to answer.</p>
            </div>
          )}

          {runs.map((run) => (
             <div key={run.run_id} className="space-y-6">
                {/* User Message */}
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex justify-end"
                >
                  <div className="max-w-[85%] rounded-[24px] bg-accent/20 px-6 py-4 text-[15px] leading-relaxed text-[#f3f4f6]">
                    {run.user_input}
                  </div>
                </motion.div>

                {/* Agent Message */}
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[100%] rounded-[24px] border border-white/5 bg-[#121826] px-6 py-5 text-[15px] leading-relaxed shadow-lg backdrop-blur-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-accent/20">
                        <Zap className="h-3 w-3 text-accent" />
                      </div>
                      <span className="text-xs font-medium uppercase tracking-wider text-muted">Agent</span>
                      {run.status === "timeout_synthesis" && (
                        <span className="text-[10px] ml-auto font-medium px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-500 border border-amber-400/20">
                          Step Limit Reached (Partial)
                        </span>
                      )}
                      {run.status === "ok" && run.score !== undefined && run.score !== null && (
                        <span className={`text-[10px] ml-auto font-mono px-2 py-0.5 rounded-full ${run.score >= 0.6 ? 'bg-emerald-400/10 text-emerald-400' : 'bg-red-400/10 text-red-500'}`}>
                          ver {formatScore(run.score)}
                        </span>
                      )}
                    </div>
                    {run.status === "running" ? (
                      <div className="flex items-center gap-3 py-2">
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                        <span className="text-sm text-muted animate-pulse">Running agent loops...</span>
                      </div>
                    ) : run.status === "error" ? (
                      <div className="text-red-400 flex items-center gap-2"><Bug className="h-4 w-4"/> {run.error}</div>
                    ) : (
                      <div className="text-gray-200">
                        <ReactMarkdown 
                          components={{
                            h1: ({node, ...props}) => <h1 className="text-lg font-bold mb-2 mt-4 text-white" {...props} />,
                            h2: ({node, ...props}) => <h2 className="text-md font-bold mb-2 mt-3 text-white border-b border-white/10 pb-1" {...props} />,
                            h3: ({node, ...props}) => <h3 className="text-sm font-bold mb-1 mt-2 text-white" {...props} />,
                            p: ({node, ...props}) => <p className="mb-3 last:mb-0 leading-relaxed" {...props} />,
                            ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-3 space-y-1" {...props} />,
                            ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-3 space-y-1" {...props} />,
                            li: ({node, ...props}) => <li className="mb-0.5" {...props} />,
                            code: ({node, inline, ...props}) => 
                              inline 
                                ? <code className="bg-white/10 rounded px-1 py-0.5 text-xs font-mono" {...props} />
                                : <code className="block bg-black/40 rounded p-3 text-xs font-mono my-2 overflow-x-auto" {...props} />,
                            strong: ({node, ...props}) => <strong className="font-bold text-accent" {...props} />,
                          }}
                        >
                          {run.final_output || "No output provided."}
                        </ReactMarkdown>
                      </div>
                    )}
                    
                    {/* Collapsible Run Debugger */}
                    <RunDetailsAccordion runId={run.run_id} />
                  </div>
                </motion.div>
             </div>
          ))}

          {/* Optimistic Pending Message */}
          {createRun.isPending && !runs.some(r => r.user_input === createRun.variables && r.status === "running") && (
             <div className="space-y-6">
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex justify-end"
                >
                  <div className="max-w-[85%] rounded-[24px] bg-accent/20 px-6 py-4 text-[15px] leading-relaxed text-[#f3f4f6]">
                    {input || createRun.variables}
                  </div>
                </motion.div>
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex justify-start"
                >
                  <div className="max-w-[100%] rounded-[24px] border border-white/5 bg-[#121826] px-6 py-5 text-[15px] leading-relaxed shadow-lg">
                    <div className="flex items-center gap-3">
                       <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                       <span className="text-sm text-muted animate-pulse">Thinking recursively...</span>
                    </div>
                  </div>
                </motion.div>
             </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <div className="w-full bg-gradient-to-t from-[#0b0f19] via-[#0b0f19] to-transparent pt-6 pb-6 px-4 shrink-0">
        <div className="mx-auto max-w-3xl relative">
          <form 
            onSubmit={handleSubmit}
            className="flex w-full items-center gap-2 overflow-hidden rounded-[28px] border border-white/10 bg-[#161d2d] p-2 shadow-2xl focus-within:border-accent/50 focus-within:ring-2 focus-within:ring-accent/20 transition-all"
          >
            <input
              type="text"
              name="prompt"
              placeholder="Message AgentOS..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={createRun.isPending}
              autoComplete="off"
              className="flex-1 bg-transparent px-4 py-3 text-[15px] text-white placeholder-muted focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || createRun.isPending}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent text-white transition hover:bg-accent/90 disabled:opacity-50 disabled:hover:bg-accent"
            >
              <ArrowUp className="h-5 w-5" />
            </button>
          </form>
          <div className="mt-3 text-center text-[11px] text-muted font-medium">
             AgentOS can make mistakes. Consider verifying critical information.
          </div>
        </div>
      </div>
    </div>
  );
}

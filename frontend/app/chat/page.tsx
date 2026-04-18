"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { 
  Send, 
  Bot, 
  User, 
  Terminal, 
  ExternalLink, 
  Sparkles,
  Zap,
  Cpu,
  Brain,
  History,
  AlertTriangle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import ReactMarkdown from "react-markdown";

export default function ChatPage() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: tools } = useQuery({
    queryKey: ["tools"],
    queryFn: () => api.getTools(),
  });

  const { data: activeRun } = useQuery({
    queryKey: ["active-run", currentRunId],
    queryFn: () => api.getRun(currentRunId!),
    enabled: !!currentRunId,
    refetchInterval: (query) => {
      // @ts-ignore
      return query.state.data?.status === "running" ? 500 : false;
    },
  });

  const dispatchMutation = useMutation({
    mutationFn: (text: string) => api.createRunAsync(text),
    onSuccess: (res) => {
      setCurrentRunId(res.run_id);
    },
  });

  useEffect(() => {
    if (activeRun && activeRun.status !== "running") {
      setMessages(prev => [
        ...prev.filter(m => m.run_id !== activeRun.run_id),
        activeRun
      ]);
      setCurrentRunId(null);
    }
  }, [activeRun]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, activeRun]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !!currentRunId) return;
    
    const userMsg = { role: "user", user_input: input, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    dispatchMutation.mutate(input);
    setInput("");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] relative animate-fade-in font-sans">
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto pr-4 space-y-8 scroll-smooth scrollbar-hide"
      >
        {messages.length === 0 && !currentRunId && (
          <EmptyState tools={tools} />
        )}

        {messages.map((msg) => (
          <div key={msg.run_id || msg.id}>
            {msg.role === "user" ? (
              <UserMessage text={msg.user_input} />
            ) : (
              <AgentMessage run={msg} />
            )}
          </div>
        ))}

        {currentRunId && activeRun && (
          <ThinkingIndicator run={activeRun} />
        )}
      </div>

      <div className="mt-8 relative">
        <div className="absolute inset-x-0 -top-12 h-12 bg-gradient-to-t from-background to-transparent pointer-events-none" />
        <form 
          onSubmit={handleSubmit}
          className="bg-glass rounded-2xl border border-white/10 p-2 flex items-end gap-2 shadow-2xl focus-within:ring-1 focus-within:ring-accent/50 transition-all"
        >
          <textarea 
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder="Ask anything... (⌘+Enter to launch)"
            className="flex-1 bg-transparent border-none outline-none p-3 text-sm resize-none scrollbar-hide min-h-[44px]"
            disabled={!!currentRunId}
          />
          <button 
            type="submit"
            disabled={!input.trim() || !!currentRunId}
            className="p-3 bg-accent text-accent-foreground rounded-xl disabled:opacity-20 transition-all active:scale-95"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
        <div className="flex justify-between px-2 mt-2">
          <span className="text-[10px] text-muted font-bold uppercase tracking-widest">Local Intel: Ready</span>
          <span className="text-[10px] text-muted font-bold uppercase tracking-widest">{input.length} Chars</span>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ tools }: { tools: any }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center max-w-lg mx-auto space-y-6 pt-12">
      <div className="w-16 h-16 bg-accent/10 rounded-full flex items-center justify-center animate-pulse">
        <Bot className="w-8 h-8 text-accent" />
      </div>
      <div>
        <h2 className="text-xl font-bold">AgentOS Conversation</h2>
        <p className="text-sm text-muted leading-relaxed mt-2">
          Start a conversational research task. The agent will retrieve relevant history, search tools, and verify its logic before responding.
        </p>
      </div>

      {tools && (
        <div className="w-full space-y-3">
          <span className="text-[10px] uppercase font-bold text-muted tracking-widest">Active Toolset</span>
          <div className="flex flex-wrap justify-center gap-2">
            {tools.map((t: any) => (
              <div key={t.name} className="px-3 py-1 bg-white/5 border border-border rounded-full text-[10px] font-bold text-accent uppercase">
                {t.name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function UserMessage({ text }: { text: string }) {
  return (
    <motion.div 
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex justify-end pr-4"
    >
      <div className="max-w-[80%] bg-accent/10 border border-accent/20 rounded-2xl px-5 py-3 text-sm text-foreground">
        {text}
      </div>
    </motion.div>
  );
}

function AgentMessage({ run }: { run: any }) {
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex gap-4"
    >
      <div className="w-8 h-8 bg-blue-400/10 rounded-lg flex items-center justify-center flex-shrink-0 mt-1">
        <Bot className="w-5 h-5 text-blue-400" />
      </div>
      <div className="flex-1 space-y-4">
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{run.final_output || run.answer}</ReactMarkdown>
        </div>

        <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest text-muted">
          <div className="flex items-center gap-1.5 px-2 py-0.5 bg-success/10 text-success rounded border border-success/30">
            <Zap className="w-3 h-3" /> Score {(run.score || 0).toFixed(2)}
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 bg-white/5 rounded border border-border">
            <History className="w-3 h-3" /> {run.steps || run.total_steps || 0} Steps
          </div>
          <a 
            href={`/runs/${run.run_id}`}
            className="flex items-center gap-1.5 px-2 py-0.5 bg-accent/10 text-accent rounded border border-accent/30 hover:bg-accent/20 transition-all ml-auto outline-none"
          >
            Trace Inspector <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {run.status === "timeout_synthesis" && (
          <div className="flex items-center gap-2 text-[10px] text-gold font-bold uppercase bg-gold/10 border border-gold/20 px-2 py-1 rounded w-fit">
            <AlertTriangle className="w-3 h-3" /> Partial Synthesis
          </div>
        )}
      </div>
    </motion.div>
  );
}

function ThinkingIndicator({ run }: { run: any }) {
  const lastTransition = run.transitions?.[run.transitions.length - 1];
  const stage = lastTransition?.stage || "starting";
  const action = lastTransition?.action || {};
  
  // Extract specific details for better "streaming" feel
  const currentGoal = action.goal || "Initializing research context...";
  const toolName = action.tool;
  const isTool = stage === "tool_result" || (stage === "plan" && action.type === "call_tool");

  const phases = [
    { label: "Understand", match: "understand" },
    { label: "Retrieve", match: "memory" },
    { label: "Plan", match: "plan" },
    { label: "Act", match: "tool" },
    { label: "Verify", match: "verify" },
    { label: "Final", match: "final" },
  ];

  return (
    <div className="flex gap-4">
      <div className="w-8 h-8 bg-accent/10 rounded-lg flex items-center justify-center flex-shrink-0">
        <Cpu className="w-5 h-5 text-accent animate-pulse" />
      </div>
      <div className="space-y-4 flex-1">
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-accent tracking-tighter animate-pulse uppercase">
              {stage.replace("_", " ")}
            </span>
            {isTool && toolName && (
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded border border-emerald-400/20">
                TOOL: {toolName}
              </span>
            )}
          </div>
          <p className="text-xs text-muted leading-relaxed italic border-l-2 border-accent/20 pl-4 py-1">
            {currentGoal}
          </p>
        </div>
        
        <div className="flex gap-1">
          {phases.map((p) => {
            const isActive = stage.includes(p.match);
            return (
              <div 
                key={p.label} 
                className={cn(
                  "h-1 flex-1 rounded-full bg-white/5 transition-all duration-500",
                  isActive ? "bg-accent shadow-[0_0_8px_rgba(125,211,252,0.5)]" : ""
                )} 
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

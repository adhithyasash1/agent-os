"use client";

import { useState, useRef, useEffect } from "react";

const API = "http://localhost:8000/api/v1";

interface Message {
  role: "user" | "assistant";
  content: string;
  score?: number;
  taskId?: string;
  feedbackState?: number; // 1 for up, -1 for down
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response, score: data.score, taskId: data.task_id },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message || "Could not reach backend"}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgIndex: number, taskId: string, feedbackScore: number) => {
    // Optimistic UI update
    setMessages((prev) => {
      const updated = [...prev];
      updated[msgIndex] = { ...updated[msgIndex], feedbackState: feedbackScore };
      return updated;
    });

    try {
      const res = await fetch(`${API}/runs/${taskId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score: feedbackScore, comment: "" }),
      });

      if (!res.ok) {
        console.error("Failed to submit feedback");
        // Revert on error
        setMessages((prev) => {
          const updated = [...prev];
          updated[msgIndex] = { ...updated[msgIndex], feedbackState: undefined };
          return updated;
        });
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-40 select-none">
            <p className="text-3xl mb-2">&#x1f916;</p>
            <h2 className="text-xl font-semibold mb-1">AgentOS Chat</h2>
            <p className="text-sm text-slate-400">
              Your local reasoning agent is ready.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                m.role === "user"
                  ? "bg-blue-600 text-white rounded-br-md"
                  : "bg-slate-800/70 border border-slate-700/40 rounded-bl-md"
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</p>
              {m.role === "assistant" && m.taskId && (
                <div className="mt-2 pt-2 border-t border-slate-700/30 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center gap-3">
                    <span>
                      Score:{" "}
                      <span
                        className={`font-mono font-bold ${
                          m.score && m.score > 0.8 ? "text-emerald-400" : "text-amber-400"
                        }`}
                      >
                        {m.score?.toFixed(2)}
                      </span>
                    </span>
                    <span className="font-mono text-slate-500 truncate max-w-[150px]" title={m.taskId}>
                      {m.taskId.slice(0, 8)}
                    </span>
                  </div>
                  
                  {/* Feedback Widget */}
                  <div className="flex gap-2 items-center">
                    <button 
                      onClick={() => handleFeedback(i, m.taskId!, 1)}
                      className={`hover:text-emerald-400 transition-colors ${m.feedbackState === 1 ? 'text-emerald-400' : 'text-slate-500'}`}
                      title="Good response"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                    </button>
                    <button 
                      onClick={() => handleFeedback(i, m.taskId!, -1)}
                      className={`hover:text-rose-400 transition-colors ${m.feedbackState === -1 ? 'text-rose-400' : 'text-slate-500'}`}
                      title="Bad response"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-800/70 border border-blue-500/20 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
                <span className="text-xs">Reasoning...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 px-6 pb-6">
        <div className="flex gap-2 bg-slate-900/80 border border-slate-800 rounded-2xl p-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask AgentOS anything..."
            className="flex-1 bg-transparent px-4 py-2.5 text-sm focus:outline-none placeholder-slate-500"
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

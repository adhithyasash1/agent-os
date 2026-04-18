"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronRight, BrainCircuit, Wrench, Search, Zap, Code2, Copy, Check } from "lucide-react";

interface TraceNodeProps {
  event: {
    type: string;
    name: string;
    summary: string;
    input: string | object | null;
    output: string | object | null;
    latency?: number;
  };
  index: number;
}

export function TraceNode({ event, index }: TraceNodeProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  // Icon mapping
  const Icon = {
    plan: BrainCircuit,
    tool: Wrench,
    memory: Search,
    reflection: Zap
  }[event.type as keyof typeof Icon] || Code2;
  
  // Color mapping
  const colorClass = {
    plan: "text-amber-500",
    tool: "text-emerald-500",
    memory: "text-indigo-400",
    reflection: "text-rose-400"
  }[event.type] || "text-gray-400";

  const bgClass = {
    plan: "bg-amber-500/10",
    tool: "bg-emerald-500/10",
    memory: "bg-indigo-500/10",
    reflection: "bg-rose-500/10"
  }[event.type] || "bg-gray-500/10";

  const handleCopy = (e: React.MouseEvent, text: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatPayload = (payload: any) => {
    if (!payload) return "null";
    if (typeof payload === 'object') return JSON.stringify(payload, null, 2);
    return payload;
  };

  return (
    <div className="relative group">
       {/* Connection Line */}
       {index !== 0 && (
         <div className="absolute -top-6 left-3.5 w-px h-6 bg-[#2A2A2E] z-0" />
       )}

       <div 
         onClick={() => setExpanded(!expanded)}
         className="relative z-10 flex flex-col rounded-lg border border-[#222224] bg-[#111113] overflow-hidden cursor-pointer hover:border-[#3A3A40] transition-colors"
       >
          {/* Node Summary Header */}
          <div className="flex items-center gap-3 p-3">
             <div className="shrink-0 flex items-center justify-center h-6 w-6">
                <motion.div animate={{ rotate: expanded ? 90 : 0 }}>
                   <ChevronRight className="h-4 w-4 text-[#5A5A5F]" />
                </motion.div>
             </div>
             
             <div className={`flex items-center gap-2 shrink-0 pr-3 border-r border-[#222224]`}>
                <div className={`p-1.5 rounded-md ${bgClass} ${colorClass}`}>
                  <Icon className="h-3 w-3" />
                </div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#E4E4E5]">
                  {event.type}
                </span>
             </div>

             <div className="truncate text-[13px] font-medium text-[#D1D1D4] pr-4">
               {event.summary}
             </div>

             {event.latency && (
               <div className="ml-auto shrink-0 text-[11px] font-mono text-[#8F8F94]">
                 {event.latency}ms
               </div>
             )}
          </div>

          {/* Expanded Payload Section */}
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-t border-[#222224] bg-[#0A0A0C]"
              >
                 <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Input Payload */}
                    {event.input && (
                      <div className="space-y-2">
                         <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-[#8F8F94]">Input</span>
                         </div>
                         <div className="relative group/copy rounded-md border border-[#222224] bg-[#141416] p-3 text-[12px] font-mono whitespace-pre-wrap text-[#D1D1D4] overflow-x-auto max-h-[300px]">
                            {formatPayload(event.input)}
                         </div>
                      </div>
                    )}

                    {/* Output Payload */}
                    {event.output && (
                      <div className="space-y-2">
                         <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-[#8F8F94]">Output</span>
                         </div>
                         <div className="relative group/copy rounded-md border border-[#222224] bg-[#141416] p-3 text-[12px] font-mono whitespace-pre-wrap text-[#D1D1D4] overflow-x-auto max-h-[300px]">
                            {formatPayload(event.output)}
                         </div>
                      </div>
                    )}
                 </div>
              </motion.div>
            )}
          </AnimatePresence>
       </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { MOCK_RUNS } from "@/lib/mock-data";
import { Clock, Play, BrainCircuit, ShieldAlert, ArrowRight, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { motion } from "motion/react";

export default function DashboardPage() {
  const toggleCommandMenu = useAppStore(state => state.toggleCommandMenu);
  
  const executingRun = MOCK_RUNS.find(r => r.status === "running");
  const lastFailure = MOCK_RUNS.find(r => r.status === "failed");
  const recentRuns = MOCK_RUNS.filter(r => r.status !== "running");

  return (
    <div className="flex-1 overflow-auto bg-[#0A0A0C]">
      <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b border-[#222224] bg-[#0A0A0C]/80 px-6 backdrop-blur-md">
        <h1 className="text-[14px] font-semibold text-[#E4E4E5]">Operational Dashboard</h1>
      </header>

      <main className="p-6 max-w-6xl mx-auto space-y-6">

        {/* Global Dispatcher */}
        <div 
          onClick={toggleCommandMenu}
          className="group cursor-pointer rounded-xl border border-[#222224] bg-[#111113] p-4 transition-all hover:bg-[#141417] hover:border-indigo-500/30"
        >
           <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500/10 text-indigo-400">
                <Play className="h-4 w-4" />
              </div>
              <div>
                <div className="text-[13px] font-medium text-[#E4E4E5]">Dispatch Agent Task...</div>
                <div className="text-[11px] text-[#8F8F94]">Press <kbd className="font-mono bg-[#2A2A2E] px-1 rounded mx-0.5">⌘K</kbd> to execute a new workflow.</div>
              </div>
           </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* Active Execution Panel */}
          <div className="rounded-xl border border-[#222224] bg-[#0F0F12] overflow-hidden flex flex-col">
             <div className="border-b border-[#222224] bg-[#141416] px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                   <div className="relative flex h-2 w-2">
                     <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                     <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                   </div>
                   <h2 className="text-[12px] font-medium tracking-wide uppercase text-[#8F8F94]">Active State</h2>
                </div>
                <span className="text-[11px] font-mono text-[#8F8F94]">0ms</span>
             </div>
             
             <div className="p-5 flex-1">
               {executingRun ? (
                 <div className="space-y-4">
                   <div className="text-[15px] font-medium leading-snug text-[#E4E4E5]">
                     "{executingRun.prompt}"
                   </div>
                   <div className="flex items-center gap-4 text-[12px]">
                      <div className="flex items-center gap-1.5 text-indigo-400 bg-indigo-400/10 px-2 py-1 rounded">
                         <BrainCircuit className="h-3.5 w-3.5 animate-pulse" />
                         Resolving context graph
                      </div>
                   </div>
                 </div>
               ) : (
                 <div className="h-full flex items-center justify-center text-[13px] text-[#5A5A5F]">
                   No active agent loops.
                 </div>
               )}
             </div>
          </div>

          {/* Last Failure Prominence */}
          <div className="rounded-xl border border-red-500/20 bg-[#160B0B] overflow-hidden flex flex-col">
             <div className="border-b border-red-500/20 bg-[#1D0C0C] px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                   <ShieldAlert className="h-4 w-4 text-red-500" />
                   <h2 className="text-[12px] font-medium tracking-wide uppercase text-red-400">Last Incident</h2>
                </div>
                <span className="text-[11px] font-mono text-red-400/70">{lastFailure?.id}</span>
             </div>
             
             <div className="p-5 flex-1 flex flex-col">
               {lastFailure ? (
                 <>
                   <div className="text-[14px] text-[#E4E4E5] mb-2 font-medium">"{lastFailure.prompt}"</div>
                   <div className="text-[12px] font-mono text-red-400 bg-red-950/50 p-2 rounded border border-red-900/50 mb-4 inline-block">
                     {lastFailure.error}
                   </div>
                   <Link 
                     href={`/runs/${lastFailure.id}`} 
                     className="mt-auto inline-flex items-center gap-1.5 text-[12px] font-medium text-red-400 hover:text-red-300 transition-colors w-fit"
                   >
                     Inspect trace breakdown <ArrowRight className="h-3 w-3" />
                   </Link>
                 </>
               ) : (
                 <div className="h-full flex items-center justify-center text-[13px] text-emerald-500/50">
                   No recent failures.
                 </div>
               )}
             </div>
          </div>

        </div>

        {/* Stable Execution Log */}
        <div className="rounded-xl border border-[#222224] bg-[#0F0F12] overflow-hidden">
          <div className="border-b border-[#222224] bg-[#141416] px-4 py-3">
             <h2 className="text-[12px] font-medium tracking-wide uppercase text-[#8F8F94]">Recent Runs</h2>
          </div>
          <div className="divide-y divide-[#222224]">
            {recentRuns.map((r, i) => (
              <motion.div 
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                key={r.id}
                className="group flex flex-col sm:flex-row sm:items-center gap-3 px-5 py-3 hover:bg-[#141417] transition-colors"
              >
                 <div className="flex items-center gap-3 w-full sm:w-[200px] shrink-0">
                    {r.status === 'completed' ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <ShieldAlert className="h-4 w-4 text-red-500" />
                    )}
                    <span className="text-[12px] font-mono text-[#8F8F94]">{r.id}</span>
                 </div>
                 
                 <div className="flex-1 truncate text-[13px] text-[#E4E4E5]">
                   {r.prompt}
                 </div>
                 
                 <div className="flex items-center gap-6 shrink-0 mt-2 sm:mt-0">
                    <div className="flex items-center gap-1.5">
                       <Clock className="h-3.5 w-3.5 text-[#5A5A5F]" />
                       <span className="text-[12px] font-mono text-[#8F8F94]">{r.latency}</span>
                    </div>
                    {r.score !== undefined && r.score !== null && (
                      <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full ${r.score >= 0.6 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                        v.{r.score.toFixed(2)}
                      </span>
                    )}
                 </div>
                 <Link 
                   href={`/runs/${r.id}`}
                   className="absolute inset-0"
                   aria-label={`View trace for ${r.id}`}
                 />
              </motion.div>
            ))}
          </div>
        </div>

      </main>
    </div>
  );
}

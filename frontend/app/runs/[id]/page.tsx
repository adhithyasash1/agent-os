"use client";

import { use } from "react";
import { MOCK_RUNS, MOCK_TRACE } from "@/lib/mock-data";
import { TraceNode } from "@/components/trace-node";
import { ArrowLeft, Clock, History, CheckCircle2, ShieldAlert } from "lucide-react";
import Link from "next/link";

export default function TraceViewerPage({ params }: { params: Promise<{ id: string }> }) {
  // Utilizing unwrapped params natively in Next 15 standard
  const { id } = use(params);

  const run = MOCK_RUNS.find(r => r.id === id) || MOCK_RUNS[0];
  const trace = MOCK_TRACE; // Mapped universally for mock visual purposes

  return (
    <div className="flex flex-col h-full bg-[#0A0A0C]">
      
      {/* Header Sticky Boundary */}
      <header className="sticky top-0 z-20 flex flex-col border-b border-[#222224] bg-[#0A0A0C]/90 backdrop-blur-md">
        <div className="flex items-center h-14 px-4 gap-3">
           <Link href="/" className="flex items-center justify-center w-8 h-8 rounded-md hover:bg-[#1A1A1E] transition-colors text-[#8F8F94] hover:text-[#D1D1D4]">
             <ArrowLeft className="h-4 w-4" />
           </Link>
           <div className="w-px h-4 bg-[#2A2A2E]" />
           <h1 className="text-[13px] font-mono text-[#E4E4E5]">{id}</h1>
           
           <div className="ml-auto flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-[12px] text-[#8F8F94] font-mono bg-[#111113] border border-[#222224] px-2 py-1 rounded">
                <Clock className="h-3.5 w-3.5" /> {run.latency}
              </div>
              <div className={`flex items-center gap-1.5 text-[12px] font-medium border px-2 py-1 rounded ${
                run.status === 'completed' 
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                  : 'bg-red-500/10 border-red-500/20 text-red-400'
              }`}>
                {run.status === 'completed' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
                {run.status.toUpperCase()}
              </div>
           </div>
        </div>
        
        {/* Run Prompt Context */}
        <div className="px-6 py-4 bg-[#0F0F12]">
           <h2 className="text-[11px] font-bold uppercase tracking-wider text-[#5A5A5F] mb-1">Execution Prompt</h2>
           <p className="text-[14px] text-[#E4E4E5] leading-relaxed">{run.prompt}</p>
        </div>
      </header>

      {/* Main Timeline View */}
      <main className="flex-1 overflow-auto p-6">
         <div className="max-w-4xl mx-auto">
            
            <div className="flex items-center gap-2 mb-6">
               <History className="h-4 w-4 text-[#8F8F94]" />
               <h3 className="text-[14px] font-medium text-[#D1D1D4]">Execution Trace Hierarchy</h3>
            </div>

            <div className="pl-3 space-y-2">
               {trace.events.map((event, idx) => (
                 <TraceNode key={idx} event={event} index={idx} />
               ))}
            </div>

         </div>
      </main>
      
    </div>
  );
}

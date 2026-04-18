"use client";

import { useState } from "react";
import { MOCK_MEMORY } from "@/lib/mock-data";
import { Database, SlidersHorizontal, Plus, Search, ChevronDown } from "lucide-react";
import { motion } from "motion/react";

export default function MemoryExplorerPage() {
  const [topK, setTopK] = useState(3);
  const [activeFilter, setActiveFilter] = useState<string>("all");
  
  const memories = MOCK_MEMORY.filter(m => activeFilter === "all" || m.type === activeFilter);

  return (
    <div className="flex flex-col h-full bg-[#0A0A0C]">
      
      {/* Header Sticky Boundary */}
      <header className="flex flex-col border-b border-[#222224] bg-[#0A0A0C]/90 backdrop-blur-md px-6 py-4 space-y-4">
        <div className="flex items-center gap-3">
           <div className="flex items-center justify-center h-8 w-8 rounded-md bg-indigo-500/10 text-indigo-400">
              <Database className="h-4 w-4" />
           </div>
           <div>
              <h1 className="text-[14px] font-semibold text-[#E4E4E5]">Memory Explorer</h1>
              <p className="text-[12px] text-[#8F8F94]">Hybrid Document & Episodic Store Tracking</p>
           </div>
        </div>

        {/* Global Controls */}
        <div className="flex flex-wrap items-center gap-4">
           {/* Filters */}
           <div className="flex items-center gap-2 p-1 rounded-md bg-[#111113] border border-[#222224]">
              {['all', 'semantic', 'experience', 'failure'].map(type => (
                 <button 
                   key={type}
                   onClick={() => setActiveFilter(type)}
                   className={`px-3 py-1 rounded text-[11px] font-medium tracking-wide uppercase transition-colors ${
                     activeFilter === type 
                        ? 'bg-[#2A2A2E] text-white' 
                        : 'text-[#5A5A5F] hover:text-[#8F8F94]'
                   }`}
                 >
                   {type}
                 </button>
              ))}
           </div>
           
           <div className="w-px h-6 bg-[#222224]" />

           {/* Top_K Slider control */}
           <div className="flex items-center gap-3 flex-1 min-w-[200px] max-w-sm px-4 py-2 rounded-md bg-[#111113] border border-[#222224]">
              <SlidersHorizontal className="h-3.5 w-3.5 text-[#5A5A5F]" />
              <span className="text-[11px] font-mono text-[#8F8F94] w-12">top_k:{topK}</span>
              <input 
                type="range" 
                min="1" 
                max="10" 
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full accent-indigo-500 h-1 bg-[#222224] rounded-lg appearance-none cursor-pointer"
              />
           </div>

           <div className="ml-auto relative">
              <button className="flex items-center justify-between gap-3 w-48 px-3 py-2 rounded-md bg-[#111113] border border-[#222224] text-[12px] text-[#D1D1D4] hover:border-[#3A3A40] transition-colors">
                <span className="flex items-center gap-2"><Search className="h-3.5 w-3.5 text-[#5A5A5F]" /> Semantic Search</span>
              </button>
           </div>
        </div>
      </header>

      {/* Grid Explorer */}
      <main className="flex-1 overflow-auto p-6">
         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
           {memories.slice(0, topK).map((mem, idx) => (
             <motion.div 
               initial={{ opacity: 0, scale: 0.98 }}
               animate={{ opacity: 1, scale: 1 }}
               transition={{ delay: idx * 0.05 }}
               key={mem.id} 
               className="group flex flex-col rounded-xl border border-[#222224] bg-[#0F0F12] overflow-hidden hover:border-[#3A3A40] transition-colors"
             >
                <div className="p-4 flex-1">
                   {/* Meta Headers */}
                   <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                      <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm ${
                        mem.type === 'failure' ? 'bg-red-500/10 text-red-400' :
                        mem.type === 'experience' ? 'bg-emerald-500/10 text-emerald-400' :
                        'bg-indigo-500/10 text-indigo-400'
                      }`}>
                        {mem.type} Layer
                      </span>
                      <span className="text-[11px] font-mono text-[#8F8F94]">Sim: {mem.score}</span>
                   </div>
                   
                   <div className="text-[13px] leading-relaxed text-[#D1D1D4] mb-4">
                     {mem.content}
                   </div>
                </div>

                {/* Card Footer Controls */}
                <div className="border-t border-[#222224] bg-[#141416] p-3 flex items-center justify-between">
                   <div className="flex flex-col">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A5A5F]">Origin</span>
                      <span className="text-[11px] font-mono text-[#8F8F94] hover:text-indigo-400 hover:underline cursor-pointer">{mem.origin}</span>
                   </div>
                   
                   {/* Simulated Injector */}
                   <button className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-500 hover:bg-indigo-400 transition-colors text-white text-[11px] font-medium opacity-0 group-hover:opacity-100 focus:opacity-100 duration-200">
                     <Plus className="h-3 w-3" /> Inject Prompt
                   </button>
                </div>
             </motion.div>
           ))}
         </div>
         {memories.length === 0 && (
           <div className="flex items-center justify-center p-12 text-[13px] text-[#5A5A5F]">
             No memories matched this filter configuration.
           </div>
         )}
      </main>

    </div>
  );
}

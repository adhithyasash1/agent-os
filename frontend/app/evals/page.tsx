"use client";

import { MOCK_EVAL } from "@/lib/mock-data";
import { Activity, Lightbulb, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function EvaluationsPage() {
  
  return (
    <div className="flex flex-col h-full bg-[#0A0A0C]">
      
      {/* Header Sticky Boundary */}
      <header className="flex flex-col border-b border-[#222224] bg-[#0A0A0C]/90 backdrop-blur-md px-6 py-4 space-y-4">
        <div className="flex items-center gap-3">
           <div className="flex items-center justify-center h-8 w-8 rounded-md bg-amber-500/10 text-amber-500">
              <Activity className="h-4 w-4" />
           </div>
           <div>
              <h1 className="text-[14px] font-semibold text-[#E4E4E5]">Configuration Evaluations</h1>
              <p className="text-[12px] text-[#8F8F94]">Ablation Matrices & Benchmark Deltas</p>
           </div>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-6 max-w-5xl mx-auto w-full space-y-8">
         
         {/* Natural Language Insights */}
         <section className="bg-[#111113] border border-[#222224] rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
               <Lightbulb className="h-4 w-4 text-emerald-400" />
               <h2 className="text-[13px] font-medium text-[#E4E4E5]">Core Architectural Insights</h2>
            </div>
            <ul className="space-y-3">
               <li className="flex items-start gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                  <p className="text-[13px] text-[#D1D1D4] leading-relaxed">
                    <strong className="text-white font-medium">Memory Architecture rescues pipelines.</strong> Incorporating memory improved global completion ratios by <span className="text-emerald-400 font-mono">+31%</span> natively across all deterministic workflows.
                  </p>
               </li>
               <li className="flex items-start gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                  <p className="text-[13px] text-[#D1D1D4] leading-relaxed">
                    <strong className="text-white font-medium">FlashRank handles lexical noise.</strong> Without a Reranker crossing the FTS lexicons, hybrid performance crashed by -16% strictly due to contextual overload.
                  </p>
               </li>
               <li className="flex items-start gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-red-500 mt-1.5 shrink-0" />
                  <p className="text-[13px] text-[#D1D1D4] leading-relaxed">
                    <strong className="text-white font-medium">Failure recovery drops off sharply.</strong> The highest failure point globally remains recursive infinite loops causing memory bounds to exhaust.
                  </p>
               </li>
            </ul>
         </section>

         {/* Visual Deltas */}
         <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {MOCK_EVAL.improvements.map((impact, idx) => (
              <div key={idx} className="bg-[#0F0F12] border border-[#222224] rounded-xl p-4 flex flex-col justify-center">
                 <div className="text-[11px] font-bold uppercase tracking-wider text-[#5A5A5F] mb-1">{impact.label}</div>
                 <div className="flex items-center gap-2">
                    {impact.type === 'positive' && <TrendingUp className="h-5 w-5 text-emerald-500" />}
                    {impact.type === 'negative' && <TrendingDown className="h-5 w-5 text-red-500" />}
                    {impact.type === 'neutral' && <Minus className="h-5 w-5 text-amber-500" />}
                    <span className={`text-[24px] font-medium tracking-tight ${
                      impact.type === 'positive' ? 'text-emerald-500' : 
                      impact.type === 'negative' ? 'text-red-500' : 'text-amber-500'
                    }`}>
                      {impact.value}
                    </span>
                 </div>
              </div>
            ))}
         </div>
         
         {/* Recharts Area */}
         <section className="bg-[#0F0F12] border border-[#222224] rounded-xl p-5 shadow-sm h-[350px] flex flex-col">
            <h2 className="text-[12px] font-medium tracking-wide uppercase text-[#8F8F94] mb-6">Ablation Benchmark Scaling Curve</h2>
            <div className="flex-1 min-h-0">
               <ResponsiveContainer width="100%" height="100%">
                 <LineChart data={MOCK_EVAL.chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                   <CartesianGrid strokeDasharray="3 3" stroke="#222224" vertical={false} />
                   <XAxis 
                     dataKey="name" 
                     stroke="#5A5A5F" 
                     fontSize={11} 
                     tickLine={false} 
                     axisLine={false}
                     dy={10}
                   />
                   <YAxis 
                     stroke="#5A5A5F" 
                     fontSize={11} 
                     tickLine={false} 
                     axisLine={false}
                     domain={[0.5, 1]}
                     tickFormatter={(val) => val.toFixed(2)}
                   />
                   <Tooltip 
                     contentStyle={{ backgroundColor: '#111113', border: '1px solid #2A2A2E', borderRadius: '8px', fontSize: '12px', color: '#fff' }}
                     itemStyle={{ color: '#6366f1' }}
                   />
                   <Line 
                     type="monotone" 
                     dataKey="score" 
                     stroke="#6366f1" 
                     strokeWidth={2} 
                     dot={{ fill: '#6366f1', strokeWidth: 2, r: 4 }} 
                     activeDot={{ r: 6, fill: '#6366f1', stroke: '#0F0F12', strokeWidth: 2 }}
                   />
                 </LineChart>
               </ResponsiveContainer>
            </div>
         </section>

      </main>

    </div>
  );
}

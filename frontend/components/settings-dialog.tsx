"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { 
  X, Settings, Shield, Zap, Terminal, 
  Trash2, Database, Bug, RefreshCw, BarChart 
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";

export function SettingsDialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { config, updateConfig, fetchConfig } = useAppStore();
  const [activeTab, setActiveTab] = useState<"general" | "maintenance">("general");
  const [localBudget, setLocalBudget] = useState(config?.context_char_budget || 150000);

  useEffect(() => {
    if (isOpen) fetchConfig();
  }, [isOpen]);

  useEffect(() => {
    if (config?.context_char_budget) setLocalBudget(config.context_char_budget);
  }, [config?.context_char_budget]);

  const handlePurge = async (kind: "working" | "episodic" | "semantic" | "all") => {
    if (confirm(`Are you sure you want to purge ${kind} memory? This cannot be undone.`)) {
      await api.purgeSystem(kind);
      alert(`${kind} memory purged successfully.`);
    }
  };

  const handleDumpContext = async () => {
    await api.dumpContext();
    alert("Context dump triggered. Check the backend terminal STDOUT.");
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-2xl bg-[#0F1117] border border-white/10 rounded-[24px] shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/2">
            <div className="flex items-center gap-2">
              <Settings className="h-4 w-4 text-accent" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-white">Agent Configuration</h2>
            </div>
            <button onClick={onClose} className="p-1.5 hover:bg-white/5 rounded-full transition-colors">
              <X className="h-4 w-4 text-muted" />
            </button>
          </div>

          <div className="flex h-[400px]">
            {/* Sidebar Tabs */}
            <div className="w-48 border-r border-white/5 bg-black/20 p-2 space-y-1">
              <button 
                onClick={() => setActiveTab("general")}
                className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-[13px] transition-all ${activeTab === "general" ? "bg-accent/10 text-accent font-medium" : "text-muted hover:bg-white/5"}`}
              >
                <Shield className="h-3.5 w-3.5" /> General
              </button>
              <button 
                onClick={() => setActiveTab("maintenance")}
                className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-[13px] transition-all ${activeTab === "maintenance" ? "bg-amber-400/10 text-amber-400 font-medium" : "text-muted hover:bg-white/5"}`}
              >
                <Bug className="h-3.5 w-3.5" /> Maintenance
              </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6">
              {activeTab === "general" && config && (
                <div className="space-y-6">
                  {/* Air Gap Toggle */}
                  <div className="flex items-center justify-between group">
                    <div>
                      <div className="text-[13px] font-medium text-white flex items-center gap-2">
                        Air-Gap Mode (Local Only)
                        <span className="text-[10px] bg-emerald-500/10 text-emerald-500 px-1.5 py-0.5 rounded border border-emerald-500/20">Recommended</span>
                      </div>
                      <div className="text-[11px] text-muted mt-0.5">Disables external APIs (HN, Search, Fetch) for 100% local, private research.</div>
                    </div>
                    <button 
                      onClick={() => updateConfig({ force_local_only: !(config?.force_local_only ?? false) })}
                      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${(config?.force_local_only ?? false) ? 'bg-accent' : 'bg-white/10'}`}
                    >
                      <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${(config?.force_local_only ?? false) ? 'translate-x-4' : 'translate-x-0'}`} />
                    </button>
                  </div>

                  {/* Context Slider */}
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-[13px] font-medium text-white">Context IQ ceiling</div>
                        <div className="text-[11px] text-muted mt-0.5">Max memory/tool data per turn. Higher = deeper but slower.</div>
                      </div>
                      <div className="text-[11px] font-mono text-accent">{(localBudget/1000).toFixed(0)}k characters</div>
                    </div>
                    <input 
                      type="range" min="8000" max="300000" step="4000"
                      value={localBudget}
                      onChange={(e) => setLocalBudget(parseInt(e.target.value))}
                      onMouseUp={() => updateConfig({ context_char_budget: localBudget })}
                      className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-accent"
                    />
                  </div>

                  {/* VRAM Profile Selector */}
                  <div className="space-y-3 pt-2">
                    <div className="text-[13px] font-medium text-white">VRAM Profile</div>
                    <div className="flex gap-2">
                      <button 
                        onClick={() => updateConfig({ vram_profile: "low" })}
                        className={`flex-1 py-1.5 px-3 rounded-lg text-[11px] font-medium border transition-all ${config?.vram_profile === "low" ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/5 border-white/5 text-muted hover:border-white/10"}`}
                      >
                        Low (Safe)
                        <div className="text-[9px] opacity-70 mt-0.5">Capped at 32k ctx</div>
                      </button>
                      <button 
                        onClick={() => updateConfig({ vram_profile: "high" })}
                        className={`flex-1 py-1.5 px-3 rounded-lg text-[11px] font-medium border transition-all ${config?.vram_profile === "high" ? "bg-accent/10 border-accent/20 text-accent" : "bg-white/5 border-white/5 text-muted hover:border-white/10"}`}
                      >
                        High (Turbo)
                        <div className="text-[9px] opacity-70 mt-0.5">Up to 128k ctx</div>
                      </button>
                    </div>
                  </div>

                  {/* Feature Switches */}
                  <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/5">
                    <div className="p-3 bg-white/2 rounded-xl border border-white/5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[12px] text-white">Semantic Memory</span>
                        <Switch 
                          checked={config?.flags?.memory ?? true} 
                          onChange={(val) => updateConfig({ flags: { ...config?.flags, memory: val } })}
                        />
                      </div>
                      <div className="text-[10px] text-muted leading-tight">Persistence and fact retrieval.</div>
                    </div>
                    <div className="p-3 bg-white/2 rounded-xl border border-white/5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[12px] text-white">Tool Access</span>
                        <Switch 
                          checked={config?.flags?.tools ?? true} 
                          onChange={(val) => updateConfig({ flags: { ...config?.flags, tools: val } })}
                        />
                      </div>
                      <div className="text-[10px] text-muted leading-tight">Ability to use APIs and logic sandboxes.</div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "maintenance" && (
                <div className="space-y-6">
                  {/* Debug Toggles */}
                  <div className="space-y-4">
                     <div className="flex items-center justify-between">
                        <div>
                          <div className="text-[13px] font-medium text-white">Verbose Backend Stream</div>
                          <div className="text-[11px] text-muted">Streams raw logs and agent 'thoughts' to your terminal.</div>
                        </div>
                        <Switch 
                           checked={config?.debug_verbose || false}
                           onChange={(val) => updateConfig({ debug_verbose: val })}
                        />
                     </div>
                  </div>

                  <div className="pt-6 border-t border-white/5 space-y-5">
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-widest text-muted mb-4">Danger Zone / Demo Cleanup</div>
                      <div className="p-3 bg-red-500/5 rounded-xl border border-red-500/10 mb-4">
                        <div className="text-[12px] text-red-400 font-medium mb-1">Reset All Demo Data</div>
                        <div className="text-[11px] text-red-400/60 leading-tight mb-3">
                          Warning: This wipes all chat history, verified knowledge, and temporary caches. Use this to prepare a fresh session for new testers.
                        </div>
                        <button 
                          onClick={() => handlePurge("all")}
                          className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/20 rounded-lg text-[12px] text-red-400 transition-all font-medium"
                        >
                          <Database className="h-3.5 w-3.5" /> Wipe Everything
                        </button>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-white/2 rounded-xl border border-white/5">
                        <div className="text-[11px] text-white font-medium mb-1">Purge Session</div>
                        <div className="text-[10px] text-muted mb-2 leading-tight">Clear current run state only.</div>
                        <button 
                          onClick={() => handlePurge("working")}
                          className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-md text-[11px] transition-colors"
                        >
                          <RefreshCw className="h-3 w-3 text-blue-400" /> Clear Run
                        </button>
                      </div>
                      <div className="p-3 bg-white/2 rounded-xl border border-white/5">
                        <div className="text-[11px] text-white font-medium mb-1">Dump Artifacts</div>
                        <div className="text-[10px] text-muted mb-2 leading-tight">Export raw context to terminal.</div>
                        <button 
                          onClick={handleDumpContext}
                          className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-md text-[11px] transition-colors"
                        >
                          <Terminal className="h-3 w-3 text-accent" /> Dump context
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

function Switch({ checked, onChange }: { checked: boolean, onChange: (val: boolean) => void }) {
  return (
    <button 
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none ${checked ? 'bg-accent' : 'bg-white/10'}`}
    >
      <span className={`pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${checked ? 'translate-x-3' : 'translate-x-0'}`} />
    </button>
  );
}

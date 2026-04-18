"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Terminal, Database, Activity, LayoutDashboard, Search, TerminalSquare } from "lucide-react";
import { useAppStore } from "@/lib/store";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Agent Console", icon: TerminalSquare },
  { href: "/runs/run_8f7b2c9a", label: "Trace Viewer", icon: Terminal },
  { href: "/memory", label: "Memory Explorer", icon: Database },
  { href: "/evals", label: "Evaluations", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();
  const toggleCommandMenu = useAppStore(state => state.toggleCommandMenu);

  return (
    <aside className="w-56 shrink-0 bg-[#0A0A0C] flex flex-col py-4 px-3 relative">
      <div className="flex items-center gap-2 px-2 py-3 mb-4">
        <div className="h-5 w-5 bg-indigo-500 rounded-[4px]" />
        <span className="font-semibold tracking-tight text-white text-[14px]">AgentOS</span>
      </div>

      <button 
        onClick={toggleCommandMenu}
        className="flex items-center gap-2 w-full px-3 py-1.5 mb-6 text-sm text-[#8F8F94] bg-[#1A1A1E] rounded-md border border-[#2A2A2E] hover:bg-[#222224] transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span>Search</span>
        <div className="ml-auto flex gap-1">
          <kbd className="text-[10px] font-mono tracking-tighter bg-[#2A2A2E] px-1 rounded">⌘</kbd>
          <kbd className="text-[10px] font-mono tracking-tighter bg-[#2A2A2E] px-1 rounded">K</kbd>
        </div>
      </button>

      <nav className="space-y-0.5">
        <div className="px-2 text-[11px] font-semibold tracking-wider text-[#5A5A5F] uppercase mb-2">Platform</div>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href.split('/')[1]));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-2 py-1.5 rounded-md text-[13px] font-medium transition-colors ${
                isActive 
                  ? "bg-[#1A1A1E] text-white" 
                  : "text-[#8A8A93] hover:text-[#D1D1D4] hover:bg-[#141416]"
              }`}
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      
      <div className="mt-auto px-2 py-3">
         <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs text-[#8A8A93]">Daemon Online</span>
         </div>
      </div>
    </aside>
  );
}

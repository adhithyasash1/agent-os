"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat", icon: "M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" },
  { href: "/runs", label: "Runs", icon: "M13 10V3L4 14h7v7l9-11h-7z" },
  { href: "/memory", label: "Memory", icon: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" },
  { href: "/tools", label: "Tools", icon: "M11.42 15.17l-2.1-.63a1 1 0 01-.66-.53l-.3-.68a1 1 0 00-.94-.61H5.5a2.5 2.5 0 010-5h1.92a1 1 0 00.94-.61l.3-.68a1 1 0 01.66-.53l2.1-.63a1 1 0 01.58 0l2.1.63a1 1 0 01.66.53l.3.68a1 1 0 00.94.61H18.5a2.5 2.5 0 010 5h-1.92a1 1 0 00-.94.61l-.3.68a1 1 0 01-.66.53l-2.1.63a1 1 0 01-.58 0z" },
  { href: "/evals", label: "Evals", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
  { href: "/traces", label: "Traces", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 border-r border-slate-800/60 p-5 flex flex-col gap-1 bg-slate-950/80 shrink-0">
      <Link href="/" className="flex items-center gap-2 mb-8">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-black text-sm">
          A
        </div>
        <span className="text-lg font-bold tracking-tight">AgentOS</span>
      </Link>

      <p className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase mb-2 px-3">
        Platform
      </p>
      <nav className="flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? "bg-blue-600/15 text-blue-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
              </svg>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-4 border-t border-slate-800/60">
        <div className="flex items-center gap-2 px-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow" />
          <span className="text-xs text-slate-500">Local instance</span>
        </div>
      </div>
    </aside>
  );
}

"use client";

import { useEffect } from "react";
import { Command } from "cmdk";
import * as Dialog from "@radix-ui/react-dialog";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { Bolt, Terminal, Database, Play } from "lucide-react";

export function CommandBar() {
  const router = useRouter();
  const open = useAppStore(state => state.isCommandMenuOpen);
  const setOpen = useAppStore(state => state.setCommandMenuOpen);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [setOpen]);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 transition-all duration-200" />
        <Dialog.Content className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-2xl bg-[#141418] border border-[#2A2A2E] rounded-xl shadow-2xl z-50 overflow-hidden">
          <Dialog.Title className="sr-only">Command Menu</Dialog.Title>
          <Dialog.Description className="sr-only">Quick access actions for AgentOS</Dialog.Description>
          <Command className="w-full flex flex-col" label="Global Command Menu">
            <div className="flex items-center px-4 py-3 border-b border-[#2A2A2E]">
               <Command.Input 
                 placeholder="What should the agent do? Or type a command..." 
                 className="flex-1 bg-transparent text-[15px] font-medium text-white placeholder:text-[#5A5A5F] focus:outline-none"
               />
               <kbd className="hidden sm:inline-flex bg-[#2A2A2E] px-1.5 py-0.5 rounded text-[10px] font-mono text-[#8A8A93]">ESC</kbd>
            </div>

            <Command.List className="max-h-[300px] overflow-y-auto px-2 py-3">
              <Command.Empty className="py-6 text-center text-sm text-[#5A5A5F]">No results found.</Command.Empty>

              <Command.Group heading={<span className="text-[10px] uppercase font-semibold text-[#5A5A5F] px-2 mb-1 block">Actions</span>}>
                <Command.Item 
                  onSelect={() => {
                     setOpen(false)
                     // Navigate to terminal mode/dashboard
                     router.push('/')
                  }}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] text-[#D1D1D4] aria-selected:bg-[#1E1E24] aria-selected:text-white cursor-pointer transition-colors"
                >
                  <Play className="h-4 w-4 text-indigo-400" />
                  Trigger New Agent Run
                </Command.Item>
                <Command.Item 
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] text-[#D1D1D4] aria-selected:bg-[#1E1E24] aria-selected:text-white cursor-pointer transition-colors"
                >
                  <Bolt className="h-4 w-4 text-amber-400" />
                  Run Offline Evaluation Benchmark
                </Command.Item>
              </Command.Group>

              <div className="h-px bg-[#2A2A2E] my-2 mx-1" />

              <Command.Group heading={<span className="text-[10px] uppercase font-semibold text-[#5A5A5F] px-2 mb-1 block">Navigation</span>}>
                <Command.Item 
                  onSelect={() => { setOpen(false); router.push('/runs/run_8f7b2c9a'); }}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] text-[#D1D1D4] aria-selected:bg-[#1E1E24] aria-selected:text-white cursor-pointer transition-colors"
                >
                  <Terminal className="h-4 w-4 text-[#8A8A93]" />
                  View Top Trace
                </Command.Item>
                <Command.Item 
                  onSelect={() => { setOpen(false); router.push('/memory'); }}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] text-[#D1D1D4] aria-selected:bg-[#1E1E24] aria-selected:text-white cursor-pointer transition-colors"
                >
                  <Database className="h-4 w-4 text-[#8A8A93]" />
                  Search Memory Database
                </Command.Item>
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

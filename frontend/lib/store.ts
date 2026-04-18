import { create } from 'zustand';
import { api } from './api';
import type { AgentConfig } from './types';

interface AppState {
  isCommandMenuOpen: boolean;
  setCommandMenuOpen: (open: boolean) => void;
  toggleCommandMenu: () => void;
  
  // Settings & Config
  config: AgentConfig | null;
  fetchConfig: () => Promise<void>;
  updateConfig: (patch: Partial<AgentConfig>) => Promise<void>;

  // Simulated Agent Task State
  isAgentRunning: boolean;
  setAgentRunning: (running: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isCommandMenuOpen: false,
  setCommandMenuOpen: (open) => set({ isCommandMenuOpen: open }),
  toggleCommandMenu: () => set((state) => ({ isCommandMenuOpen: !state.isCommandMenuOpen })),
  
  config: null,
  fetchConfig: async () => {
    try {
      const config = await api.getConfig();
      set({ config });
    } catch (e) { console.error(e); }
  },
  updateConfig: async (patch) => {
    try {
      const { current } = await api.patchConfig(patch);
      set({ config: current });
    } catch (e) { console.error(e); }
  },

  isAgentRunning: false,
  setAgentRunning: (running) => set({ isAgentRunning: running })
}));

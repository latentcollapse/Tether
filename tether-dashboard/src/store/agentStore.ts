import { create } from 'zustand';
import { Agent } from '../types/agent';

interface AgentState {
  agents: Record<string, Agent>;
  upsertAgent: (agent: Agent) => void;
  removeAgent: (id: string) => void;
  setAgents: (agents: Agent[]) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: {},
  upsertAgent: (agent) =>
    set((state) => ({
      agents: { ...state.agents, [agent.id]: agent },
    })),
  removeAgent: (id) =>
    set((state) => {
      const next = { ...state.agents };
      delete next[id];
      return { agents: next };
    }),
  setAgents: (agents) => {
    const map: Record<string, Agent> = {};
    agents.forEach(a => map[a.id] = a);
    set({ agents: map });
  }
}));

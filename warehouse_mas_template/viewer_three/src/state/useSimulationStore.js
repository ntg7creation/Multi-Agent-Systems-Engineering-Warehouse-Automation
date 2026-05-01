import { create } from 'zustand'
import { simulationClient } from '../api/simulationClient'

export const useSimulationStore = create((set, get) => ({
  state: null,
  selectedAgentId: null,
  loading: false,
  error: '',

  selectedAgent: () => {
    const { state, selectedAgentId } = get()
    return state?.agents?.find((agent) => agent.agent_id === selectedAgentId) ?? null
  },

  refresh: async () => {
    set({ loading: true, error: '' })
    try {
      const state = await simulationClient.state()
      set({ state, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  tick: async (steps = 1) => {
    set({ loading: true, error: '' })
    try {
      const state = await simulationClient.tick(steps)
      set({ state, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  selectAgent: (agentId) => set({ selectedAgentId: agentId }),
}))

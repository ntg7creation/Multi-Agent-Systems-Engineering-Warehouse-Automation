import { create } from 'zustand'
import { simulationClient } from '../api/simulationClient'
import { DEFAULT_CARRY_BOX_OFFSET } from '../scene/constants'

export const useSimulationStore = create((set, get) => ({
  state: null,
  scenarios: [],
  selectedAgentId: null,
  viewMode: 'global',
  cameraFollowSelected: false,
  stateBuffer: [],
  bufferTarget: 3,
  bufferPlaybackActive: false,
  bufferDelayMs: 600,
  bufferFilling: false,
  carryBoxOffset: DEFAULT_CARRY_BOX_OFFSET,
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
      set({
        state,
        stateBuffer: [],
        bufferPlaybackActive: false,
        selectedAgentId: get().selectedAgentId ?? state.agents?.[0]?.agent_id ?? null,
        loading: false,
      })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  loadScenarios: async () => {
    try {
      const data = await simulationClient.scenarios()
      set({ scenarios: data.scenarios ?? [] })
    } catch (error) {
      set({ scenarios: [] })
    }
  },

  tick: async (steps = 1) => {
    set({ loading: true, error: '', stateBuffer: [], bufferPlaybackActive: false })
    try {
      const state = await simulationClient.tick(steps)
      set({ state, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  run: async (steps = 10) => {
    set({ loading: true, error: '', stateBuffer: [], bufferPlaybackActive: false })
    try {
      const state = await simulationClient.run(steps)
      set({ state, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  reset: async ({ scenarioId = 'default', seed, config } = {}) => {
    set({ loading: true, error: '', stateBuffer: [], bufferPlaybackActive: false })
    try {
      const state = await simulationClient.reset({ scenarioId, seed, config })
      set({ state, selectedAgentId: state.agents?.[0]?.agent_id ?? null, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  start: async ({ delayMs = 600 } = {}) => {
    set({
      error: '',
      bufferDelayMs: delayMs,
      bufferPlaybackActive: true,
    })
    try {
      await simulationClient.pause()
      await get().fillBuffer()
    } catch (error) {
      set({ error: error.message, bufferPlaybackActive: false, bufferFilling: false })
    }
  },

  pause: async () => {
    set({ loading: true, error: '', bufferPlaybackActive: false })
    try {
      await simulationClient.pause()
      set({ loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },

  fillBuffer: async () => {
    const current = get()
    if (current.bufferFilling || current.state?.is_complete) return

    set({ bufferFilling: true, error: '' })
    try {
      while (
        get().stateBuffer.length < get().bufferTarget
        && !get().state?.is_complete
      ) {
        const futureState = await simulationClient.tick(1)
        set((state) => ({
          stateBuffer: [...state.stateBuffer, futureState],
        }))
        if (futureState.is_complete) break
      }
      set({ bufferFilling: false })
    } catch (error) {
      set({
        error: error.message,
        bufferFilling: false,
        bufferPlaybackActive: false,
      })
    }
  },

  playNextBufferedFrame: async () => {
    if (!get().bufferPlaybackActive) return
    if (!get().stateBuffer.length) {
      await get().fillBuffer()
    }

    const nextFrame = get().stateBuffer[0]
    if (!nextFrame) return

    set((state) => {
      const selectedStillExists = nextFrame.agents?.some(
        (agent) => agent.agent_id === state.selectedAgentId,
      )
      return {
        state: nextFrame,
        stateBuffer: state.stateBuffer.slice(1),
        selectedAgentId: selectedStillExists
          ? state.selectedAgentId
          : nextFrame.agents?.[0]?.agent_id ?? null,
        bufferPlaybackActive: !nextFrame.is_complete,
      }
    })

    get().fillBuffer()
  },

  selectAgent: (agentId) => set({ selectedAgentId: agentId }),
  setViewMode: (viewMode) => set({ viewMode }),
  setCameraFollowSelected: (cameraFollowSelected) => set({ cameraFollowSelected }),
}))

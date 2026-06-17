import { useEffect } from 'react'
import { WarehouseScene } from './scene/WarehouseScene'
import { ControlPanel } from './ui/ControlPanel'
import { InspectorPanel } from './ui/InspectorPanel'
import { useSimulationStore } from './state/useSimulationStore'

function App() {
  const refresh = useSimulationStore((state) => state.refresh)
  const loadScenarios = useSimulationStore((state) => state.loadScenarios)
  const bufferPlaybackActive = useSimulationStore((state) => state.bufferPlaybackActive)
  const bufferDelayMs = useSimulationStore((state) => state.bufferDelayMs)
  const playNextBufferedFrame = useSimulationStore((state) => state.playNextBufferedFrame)

  useEffect(() => {
    loadScenarios()
    refresh()
  }, [loadScenarios, refresh])

  useEffect(() => {
    if (!bufferPlaybackActive) return undefined
    const id = window.setInterval(playNextBufferedFrame, Math.max(80, bufferDelayMs))
    return () => window.clearInterval(id)
  }, [bufferDelayMs, bufferPlaybackActive, playNextBufferedFrame])

  return (
    <div className="app-shell">
      <ControlPanel />
      <main className="viewer-layout">
        <WarehouseScene />
        <InspectorPanel />
      </main>
    </div>
  )
}

export default App

import { useEffect } from 'react'
import { ScenePlaceholder } from './scene/ScenePlaceholder'
import { ControlPanel } from './ui/ControlPanel'
import { InspectorPanel } from './ui/InspectorPanel'
import { useSimulationStore } from './state/useSimulationStore'

function App() {
  const refresh = useSimulationStore((state) => state.refresh)

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div className="app-shell">
      <ControlPanel />
      <main className="viewer-layout">
        <ScenePlaceholder />
        <InspectorPanel />
      </main>
    </div>
  )
}

export default App

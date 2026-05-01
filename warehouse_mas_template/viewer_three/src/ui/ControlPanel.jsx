import { useSimulationStore } from '../state/useSimulationStore'

export function ControlPanel() {
  const state = useSimulationStore((store) => store.state)
  const loading = useSimulationStore((store) => store.loading)
  const error = useSimulationStore((store) => store.error)
  const refresh = useSimulationStore((store) => store.refresh)
  const tick = useSimulationStore((store) => store.tick)

  return (
    <header className="control-panel">
      <div>
        <strong>Warehouse MAS Three Viewer</strong>
        <span>Tick {state?.tick ?? '-'}</span>
      </div>
      <nav>
        <button onClick={() => tick(1)} disabled={loading}>Tick</button>
        <button onClick={() => tick(10)} disabled={loading}>Run 10</button>
        <button onClick={refresh} disabled={loading}>Refresh</button>
      </nav>
      {error && <p className="error">{error}</p>}
    </header>
  )
}

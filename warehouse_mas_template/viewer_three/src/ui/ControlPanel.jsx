import { useEffect, useState } from 'react'
import { useSimulationStore } from '../state/useSimulationStore'

export function ControlPanel() {
  const state = useSimulationStore((store) => store.state)
  const scenarios = useSimulationStore((store) => store.scenarios)
  const loading = useSimulationStore((store) => store.loading)
  const error = useSimulationStore((store) => store.error)
  const refresh = useSimulationStore((store) => store.refresh)
  const tick = useSimulationStore((store) => store.tick)
  const run = useSimulationStore((store) => store.run)
  const reset = useSimulationStore((store) => store.reset)
  const start = useSimulationStore((store) => store.start)
  const pause = useSimulationStore((store) => store.pause)
  const viewMode = useSimulationStore((store) => store.viewMode)
  const setViewMode = useSimulationStore((store) => store.setViewMode)
  const cameraFollowSelected = useSimulationStore((store) => store.cameraFollowSelected)
  const setCameraFollowSelected = useSimulationStore((store) => store.setCameraFollowSelected)
  const stateBuffer = useSimulationStore((store) => store.stateBuffer)
  const bufferTarget = useSimulationStore((store) => store.bufferTarget)
  const bufferPlaybackActive = useSimulationStore((store) => store.bufferPlaybackActive)
  const bufferFilling = useSimulationStore((store) => store.bufferFilling)

  const [scenarioId, setScenarioId] = useState('default')
  const [seed, setSeed] = useState('42')
  const [delayMs, setDelayMs] = useState(600)

  useEffect(() => {
    if (!state) return
    setScenarioId(state.scenario?.scenario_id ?? 'default')
    setSeed(String(state.seed ?? ''))
  }, [state?.run_id])

  return (
    <header className="control-panel">
      <div className="viewer-title">
        <strong>Warehouse MAS Three Viewer</strong>
        <span>Display tick {state?.tick ?? '-'}</span>
        <span>
          Buffer {stateBuffer.length}/{bufferTarget}
          {stateBuffer.length ? ` to T${stateBuffer[stateBuffer.length - 1]?.tick}` : ''}
        </span>
        {bufferPlaybackActive && <span className="live-pill">Buffered playback</span>}
        {bufferFilling && <span>filling...</span>}
        <span>{state?.scenario?.name ?? 'No scenario loaded'}</span>
      </div>

      <div className="scenario-strip">
        <label>
          Scenario
          <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
            {scenarios.map((scenario) => (
              <option key={scenario.scenario_id} value={scenario.scenario_id}>
                {scenario.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Seed
          <input
            type="number"
            value={seed}
            onChange={(event) => setSeed(event.target.value)}
          />
        </label>
        <label>
          Speed
          <input
            type="range"
            min="80"
            max="2000"
            step="20"
            value={delayMs}
            onChange={(event) => setDelayMs(Number(event.target.value))}
          />
          <span>{delayMs} ms</span>
        </label>
      </div>

      <nav>
        <button onClick={() => start({ delayMs })} disabled={loading}>Start</button>
        <button onClick={pause} disabled={loading}>Pause</button>
        <button onClick={() => tick(1)} disabled={loading}>Step</button>
        <button onClick={() => run(10)} disabled={loading}>Run 10</button>
        <button
          onClick={() => reset({ scenarioId, seed: seed === '' ? undefined : Number(seed) })}
          disabled={loading}
        >
          Reset
        </button>
        <button className="secondary" onClick={refresh} disabled={loading}>Refresh</button>
      </nav>

      <div className="viewer-mode-strip" aria-label="3D viewer modes">
        <div className="mode-toggle">
          <button
            className={viewMode === 'global' ? 'active' : ''}
            type="button"
            onClick={() => setViewMode('global')}
          >
            Global
          </button>
          <button
            className={viewMode === 'agent' ? 'active' : ''}
            type="button"
            onClick={() => setViewMode('agent')}
          >
            Agent view
          </button>
          <button type="button" disabled title="Memory view will be added later">
            Memory
          </button>
        </div>
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={cameraFollowSelected}
            onChange={(event) => setCameraFollowSelected(event.target.checked)}
          />
          Follow selected agent
        </label>
      </div>

      {error && <p className="error">{error}</p>}
    </header>
  )
}

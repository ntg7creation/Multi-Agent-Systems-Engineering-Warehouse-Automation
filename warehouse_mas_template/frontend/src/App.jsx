import { useEffect, useMemo, useState } from 'react'
import {
  getScenarios,
  getState,
  resetSimulation,
  runSteps,
  startAutorun,
  stopAutorun,
  tick,
} from './api'

function App() {
  const [state, setState] = useState(null)
  const [scenarios, setScenarios] = useState([])
  const [scenarioId, setScenarioId] = useState('default')
  const [seed, setSeed] = useState('42')
  const [stepDelay, setStepDelay] = useState(600)
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [error, setError] = useState('')

  const selectedAgent = useMemo(
    () => state?.agents?.find((agent) => agent.agent_id === selectedAgentId) ?? state?.agents?.[0],
    [selectedAgentId, state],
  )

  const agentMap = useMemo(() => {
    const map = new Map()
    state?.agents?.forEach((agent) => {
      map.set(agent.position.join(','), agent)
    })
    return map
  }, [state])

  const itemMap = useMemo(() => {
    const map = new Map()
    state?.items?.forEach((item) => {
      const key = item.position.join(',')
      const bucket = map.get(key) ?? []
      bucket.push(item)
      map.set(key, bucket)
    })
    return map
  }, [state])

  async function refreshState() {
    try {
      const data = await getState()
      setState(data)
      setScenarioId(data.scenario?.scenario_id ?? 'default')
      setSeed(String(data.seed ?? ''))
      setError('')
    } catch (err) {
      setError('Could not reach the Flask server on port 5000.')
    }
  }

  async function refreshScenarios() {
    try {
      const data = await getScenarios()
      setScenarios(data.scenarios ?? [])
    } catch (err) {
      setScenarios([])
    }
  }

  async function perform(action) {
    try {
      const data = await action()
      if (data?.tick !== undefined) {
        setState(data)
      } else {
        await refreshState()
      }
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    refreshScenarios()
    refreshState()
  }, [])

  useEffect(() => {
    if (!state?.autorun?.active) return undefined
    const id = setInterval(refreshState, Math.max(150, stepDelay))
    return () => clearInterval(id)
  }, [state?.autorun?.active, stepDelay])

  const rows = state?.board?.rows ?? []
  const metrics = state?.metrics?.global ?? {}
  const activeTasks = state?.tasks?.filter((task) => task.status !== 'delivered') ?? []

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Warehouse MAS</h1>
          <p className="subtitle">Flask simulation server with a lightweight React board viewer</p>
        </div>
        <div className="scenario-controls">
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
          <button onClick={() => perform(() => resetSimulation({ scenarioId, seed: Number(seed) }))}>
            Reset
          </button>
        </div>
      </header>

      <section className="controls">
        <button onClick={() => perform(() => tick(1))}>Tick</button>
        <button onClick={() => perform(() => runSteps(10))}>Run 10</button>
        <button onClick={() => perform(() => runSteps(50))}>Run 50</button>
        <button
          onClick={() =>
            perform(() =>
              state?.autorun?.active
                ? stopAutorun()
                : startAutorun({ delayMs: stepDelay }),
            )
          }
        >
          {state?.autorun?.active ? 'Stop server autorun' : 'Start server autorun'}
        </button>
        <label>
          Tick ms
          <input
            type="number"
            min="50"
            step="50"
            value={stepDelay}
            onChange={(event) => setStepDelay(Number(event.target.value) || 600)}
          />
        </label>
        <button className="secondary" onClick={refreshState}>Refresh</button>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="stats">
        <span><strong>Tick:</strong> {state?.tick ?? '-'}</span>
        <span><strong>Seed:</strong> {state?.seed ?? '-'}</span>
        <span><strong>Agents:</strong> {state?.agents?.length ?? 0}</span>
        <span><strong>Active tasks:</strong> {activeTasks.length}</span>
        <span><strong>Completed:</strong> {metrics.completed_deliveries ?? 0}/{metrics.total_tasks ?? 0}</span>
        <span><strong>Throughput:</strong> {metrics.throughput ?? 0}</span>
      </section>

      <main className="content">
        <section className="board-panel">
          <div
            className="grid"
            style={{
              gridTemplateColumns: `repeat(${state?.board?.width ?? 1}, 42px)`,
            }}
          >
            {rows.flatMap((row) =>
              row.map((cell) => {
                const key = cell.position.join(',')
                const agent = agentMap.get(key)
                const items = itemMap.get(key) ?? []
                return (
                  <button
                    key={key}
                    className={`cell ${cell.cell_type}`}
                    type="button"
                    onClick={() => agent && setSelectedAgentId(agent.agent_id)}
                    title={`${cell.position[0]},${cell.position[1]} ${cell.cell_type}`}
                  >
                    <span className="cell-coord">{cell.position[0]},{cell.position[1]}</span>
                    {items.map((item) => (
                      <span key={item.item_id} className={`box ${item.state}`}>B</span>
                    ))}
                    {agent && <span className="agent">{agent.agent_id.replace('agent_', 'A')}</span>}
                  </button>
                )
              }),
            )}
          </div>
        </section>

        <aside className="side-panels">
          <section className="card">
            <h2>Agents</h2>
            <div className="list">
              {state?.agents?.map((agent) => (
                <button
                  key={agent.agent_id}
                  className={`list-row ${selectedAgent?.agent_id === agent.agent_id ? 'selected' : ''}`}
                  type="button"
                  onClick={() => setSelectedAgentId(agent.agent_id)}
                >
                  <strong>{agent.agent_id}</strong>
                  <span>{agent.state}</span>
                  <span>({agent.position[0]}, {agent.position[1]})</span>
                </button>
              ))}
            </div>
          </section>

          <section className="card">
            <h2>Selected Agent</h2>
            {selectedAgent ? (
              <div className="details">
                <span><strong>ID:</strong> {selectedAgent.agent_id}</span>
                <span><strong>Goal:</strong> {selectedAgent.goal_type ?? 'idle'}</span>
                <span><strong>Task:</strong> {selectedAgent.goal_task_id ?? '-'}</span>
                <span><strong>Carrying:</strong> {selectedAgent.carrying_item_id ?? '-'}</span>
                <span><strong>Known cells:</strong> {selectedAgent.memory?.known_cell_count ?? 0}</span>
                <span><strong>Path length:</strong> {selectedAgent.metrics?.path_length ?? 0}</span>
              </div>
            ) : (
              <p className="empty">No agent selected.</p>
            )}
          </section>

          <section className="card">
            <h2>Tasks</h2>
            <div className="list">
              {state?.tasks?.map((task) => (
                <div key={task.task_id} className="task-row">
                  <strong>{task.task_id}</strong>
                  <span>{task.status}</span>
                  <span>{task.assigned_agent_id ?? 'unassigned'}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card">
            <h2>Recent Events</h2>
            <div className="events">
              {state?.events?.length ? state.events.slice().reverse().map((event) => (
                <div key={event.event_id} className="event-row">
                  <span>T{event.tick}</span>
                  <p>{event.message}</p>
                </div>
              )) : <p className="empty">No events yet.</p>}
            </div>
          </section>
        </aside>
      </main>
    </div>
  )
}

export default App

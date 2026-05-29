import { useEffect, useMemo, useState } from 'react'
import {
  getScenarios,
  getState,
  pauseSimulation,
  resetSimulation,
  resumeSimulation,
  runSteps,
  startSimulation,
  tick,
} from './api'

function formatPosition(position) {
  return position ? `(${position[0]}, ${position[1]})` : '-'
}

function App() {
  const [state, setState] = useState(null)
  const [scenarios, setScenarios] = useState([])
  const [scenarioId, setScenarioId] = useState('default')
  const [seed, setSeed] = useState('42')
  const [stepDelay, setStepDelay] = useState(600)
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [error, setError] = useState('')

  const selectedAgent = useMemo(
    () => state?.agents?.find((agent) => agent.agent_id === selectedAgentId) ?? state?.agents?.[0],
    [selectedAgentId, state],
  )

  const selectedTask = useMemo(
    () => state?.tasks?.find((task) => task.task_id === selectedTaskId)
      ?? state?.tasks?.find((task) => task.task_id === selectedAgent?.current_task_id)
      ?? state?.tasks?.[0],
    [selectedAgent, selectedTaskId, state],
  )

  const selectedItem = useMemo(
    () => state?.items?.find((item) => item.item_id === selectedTask?.item_id),
    [selectedTask, state],
  )

  const pathCells = useMemo(() => {
    const set = new Set()
    selectedAgent?.planned_path?.forEach((position) => set.add(position.join(',')))
    return set
  }, [selectedAgent])

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
      if (!item.position) return
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
      setSelectedAgentId((current) => current || data.agents?.[0]?.agent_id || '')
      setSelectedTaskId((current) => current || data.tasks?.[0]?.task_id || '')
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
  const agentMetrics = selectedAgent ? state?.metrics?.agents?.[selectedAgent.agent_id] : null
  const activeTasks = state?.tasks?.filter((task) => task.status !== 'delivered') ?? []

  return (
    <div className="page">
      <header className="topbar">
        <div className="title-block">
          <h1>Warehouse MAS Dashboard</h1>
          <p className="subtitle">{state?.scenario?.name ?? 'Backend simulation dashboard'}</p>
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
        <button onClick={() => perform(() => startSimulation({ delayMs: stepDelay }))}>Start</button>
        <button onClick={() => perform(() => pauseSimulation())}>Pause</button>
        <button onClick={() => perform(() => resumeSimulation({ delayMs: stepDelay }))}>Resume</button>
        <button onClick={() => perform(() => tick(1))}>Step</button>
        <button onClick={() => perform(() => runSteps(10))}>Run 10</button>
        <label className="speed-control">
          Speed
          <input
            type="range"
            min="80"
            max="2000"
            step="20"
            value={stepDelay}
            onChange={(event) => setStepDelay(Number(event.target.value))}
          />
          <span>{stepDelay} ms</span>
        </label>
        <button className="secondary" onClick={refreshState}>Refresh</button>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="stats">
        <span><strong>Tick</strong>{state?.tick ?? '-'}</span>
        <span><strong>Completed</strong>{metrics.completed_deliveries ?? 0}/{metrics.total_tasks ?? 0}</span>
        <span><strong>Active</strong>{activeTasks.length}</span>
        <span><strong>Avg time</strong>{metrics.average_completion_time ?? 0}</span>
        <span><strong>Waits</strong>{metrics.wait_actions ?? 0}</span>
        <span><strong>Blocked</strong>{metrics.blocked_move_attempts ?? 0}</span>
        <span><strong>Throughput</strong>{metrics.throughput ?? 0}</span>
        <span><strong>CAS</strong>{metrics.collision_avoidance_score ?? 1}</span>
      </section>

      <main className="content">
        <section className="board-panel">
          <div className="board-header">
            <h2>Warehouse Grid</h2>
            <div className="legend">
              <span><i className="legend-road" />Free</span>
              <span><i className="legend-blocked" />Blocked</span>
              <span><i className="legend-pickup" />Pickup</span>
              <span><i className="legend-dropoff" />Delivery</span>
              <span><i className="legend-path" />Selected path</span>
            </div>
          </div>
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
                const isPath = pathCells.has(key)
                const isSelectedAgent = selectedAgent?.agent_id === agent?.agent_id
                return (
                  <button
                    key={key}
                    className={[
                      'cell',
                      cell.cell_type,
                      isPath ? 'path' : '',
                      isSelectedAgent ? 'selected-agent-cell' : '',
                    ].filter(Boolean).join(' ')}
                    type="button"
                    onClick={() => {
                      if (agent) setSelectedAgentId(agent.agent_id)
                      if (items[0]) setSelectedTaskId(items[0].task_id)
                    }}
                    title={`${cell.position[0]},${cell.position[1]} ${cell.cell_type}`}
                  >
                    <span className="cell-coord">{cell.position[0]},{cell.position[1]}</span>
                    {items.map((item) => (
                      <span key={item.item_id} className={`box ${item.state}`}>
                        {item.item_id.replace(/[^0-9a-z]/gi, '').slice(-1).toUpperCase()}
                      </span>
                    ))}
                    {agent && (
                      <span className={`agent ${agent.carrying_item_id ? 'carrying' : ''}`}>
                        {agent.agent_id.replace('agent_', 'A')}
                      </span>
                    )}
                  </button>
                )
              }),
            )}
          </div>
        </section>

        <aside className="side-panels">
          <section className="card">
            <h2>Agent Inspection</h2>
            <div className="list compact">
              {state?.agents?.map((agent) => (
                <button
                  key={agent.agent_id}
                  className={`list-row ${selectedAgent?.agent_id === agent.agent_id ? 'selected' : ''}`}
                  type="button"
                  onClick={() => setSelectedAgentId(agent.agent_id)}
                >
                  <strong>{agent.agent_id}</strong>
                  <span>{agent.mode}</span>
                  <span>{formatPosition(agent.position)}</span>
                </button>
              ))}
            </div>
            {selectedAgent && (
              <div className="details split">
                <span><strong>ID</strong>{selectedAgent.agent_id}</span>
                <span><strong>Mode</strong>{selectedAgent.mode}</span>
                <span><strong>Task</strong>{selectedAgent.current_task_id ?? '-'}</span>
                <span><strong>Carrying</strong>{selectedAgent.carrying_item_id ?? '-'}</span>
                <span><strong>Target</strong>{formatPosition(selectedAgent.current_target)}</span>
                <span><strong>Intended</strong>{selectedAgent.intended_action?.type ?? '-'}</span>
                <span><strong>Previous</strong>{selectedAgent.previous_action_result?.success === false ? selectedAgent.previous_action_result.failure_reason : selectedAgent.previous_action_result?.action?.type ?? '-'}</span>
                <span><strong>Path cells</strong>{selectedAgent.planned_path?.length ?? 0}</span>
                <span><strong>Waits</strong>{selectedAgent.waiting_counter ?? 0}</span>
                <span><strong>Failed moves</strong>{selectedAgent.failed_movement_counter ?? 0}</span>
                <span><strong>Known cells</strong>{selectedAgent.memory?.known_cell_count ?? 0}</span>
                <span><strong>Congestion cells</strong>{selectedAgent.memory?.congestion_cell_count ?? 0}</span>
                <span><strong>Completed</strong>{agentMetrics?.completed_tasks ?? 0}</span>
                <span><strong>Efficiency</strong>{agentMetrics?.efficiency ?? 0}</span>
              </div>
            )}
          </section>

          <section className="card">
            <h2>Tasks And Items</h2>
            <div className="list">
              {state?.tasks?.map((task) => (
                <button
                  key={task.task_id}
                  className={`task-row ${selectedTask?.task_id === task.task_id ? 'selected' : ''}`}
                  type="button"
                  onClick={() => setSelectedTaskId(task.task_id)}
                >
                  <strong>{task.task_id}</strong>
                  <span>{task.status}</span>
                  <span>{task.assigned_agent_id ?? 'unassigned'}</span>
                </button>
              ))}
            </div>
            {selectedTask && (
              <div className="details split">
                <span><strong>Pickup</strong>{formatPosition(selectedTask.pickup_position)}</span>
                <span><strong>Delivery</strong>{formatPosition(selectedTask.dropoff_position)}</span>
                <span><strong>Item</strong>{selectedTask.item_id}</span>
                <span><strong>Item state</strong>{selectedItem?.state ?? '-'}</span>
                <span><strong>Created</strong>{selectedTask.created_tick}</span>
                <span><strong>Assigned</strong>{selectedTask.assigned_tick ?? '-'}</span>
                <span><strong>Picked</strong>{selectedTask.picked_tick ?? '-'}</span>
                <span><strong>Delivered</strong>{selectedTask.delivered_tick ?? '-'}</span>
              </div>
            )}
          </section>

          <section className="card">
            <h2>Metrics</h2>
            <div className="details split">
              <span><strong>Moves</strong>{metrics.move_actions ?? 0}</span>
              <span><strong>Pickups</strong>{metrics.pick_actions ?? 0}</span>
              <span><strong>Places</strong>{metrics.place_actions ?? 0}</span>
              <span><strong>Replans</strong>{metrics.route_replans ?? 0}</span>
              <span><strong>Path length</strong>{metrics.path_length ?? 0}</span>
              <span><strong>Path ineff.</strong>{metrics.path_inefficiency ?? 0}</span>
              <span><strong>Comms</strong>{metrics.communication_events ?? 0}</span>
              <span><strong>Conflicts</strong>{metrics.collision_preventions ?? 0}</span>
            </div>
          </section>

          <section className="card event-card">
            <h2>Event Log</h2>
            <div className="events">
              {state?.events?.length ? state.events.slice().reverse().map((event) => (
                <div key={event.event_id} className="event-row">
                  <span>T{event.tick}</span>
                  <strong>{event.type}</strong>
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

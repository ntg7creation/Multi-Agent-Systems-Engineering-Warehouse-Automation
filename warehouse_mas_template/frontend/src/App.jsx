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

function positionKey(position) {
  return position ? position.join(',') : ''
}

function congestionLabel(value) {
  if (!value) return ''
  return Number(value).toFixed(value >= 10 ? 0 : 1)
}

function App() {
  const [state, setState] = useState(null)
  const [scenarios, setScenarios] = useState([])
  const [scenarioId, setScenarioId] = useState('default')
  const [seed, setSeed] = useState('42')
  const [stepDelay, setStepDelay] = useState(600)
  const [gridZoom, setGridZoom] = useState(100)
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [viewMode, setViewMode] = useState('global')
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

  const perceptionCells = useMemo(() => {
    const set = new Set()
    selectedAgent?.perception?.visible_cells?.forEach((cell) => set.add(positionKey(cell.position)))
    return set
  }, [selectedAgent])

  const memoryCellMap = useMemo(() => {
    const map = new Map()
    selectedAgent?.memory_map?.known_cells?.forEach((cell) => {
      map.set(positionKey(cell.position), cell)
    })
    selectedAgent?.memory_map?.known_pickups?.forEach((pickup) => {
      map.set(positionKey(pickup.position), {
        position: pickup.position,
        cell_type: 'pickup',
        walkable: false,
        last_seen_tick: pickup.last_seen_tick,
      })
    })
    selectedAgent?.memory_map?.known_deliveries?.forEach((delivery) => {
      map.set(positionKey(delivery.position), {
        position: delivery.position,
        cell_type: 'dropoff',
        walkable: false,
        last_seen_tick: delivery.last_seen_tick,
      })
    })
    return map
  }, [selectedAgent])

  const memoryItemMap = useMemo(() => {
    const map = new Map()
    selectedAgent?.memory_map?.known_items?.forEach((item) => {
      if (!item.position) return
      const key = positionKey(item.position)
      const bucket = map.get(key) ?? []
      bucket.push(item)
      map.set(key, bucket)
    })
    return map
  }, [selectedAgent])

  const memoryAgentMap = useMemo(() => {
    const map = new Map()
    selectedAgent?.memory_map?.known_agents?.forEach((agent) => {
      if (!agent.position) return
      map.set(positionKey(agent.position), agent)
    })
    return map
  }, [selectedAgent])

  const memoryCongestionMap = useMemo(() => {
    const map = new Map()
    selectedAgent?.memory_map?.congestion?.forEach((entry) => {
      map.set(positionKey(entry.position), entry.value)
    })
    return map
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
  const boardWidth = state?.board?.width ?? 1
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
        <label className="speed-control">
          Grid zoom
          <input
            type="range"
            min="45"
            max="125"
            step="5"
            value={gridZoom}
            onChange={(event) => setGridZoom(Number(event.target.value))}
          />
          <span>{gridZoom}%</span>
        </label>
        <button className="secondary" type="button" onClick={() => setGridZoom(100)}>Fit grid</button>
        <div className="mode-toggle" aria-label="Map view mode">
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
          <button
            className={viewMode === 'memory' ? 'active' : ''}
            type="button"
            onClick={() => setViewMode('memory')}
          >
            Memory map
          </button>
        </div>
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
              <span><i className="legend-perception" />Perception</span>
              <span><i className="legend-unknown" />Unknown</span>
              <span><i className="legend-congestion" />Congestion</span>
            </div>
          </div>
          {viewMode !== 'global' && selectedAgent && (
            <div className="agent-view-strip">
              <strong>{selectedAgent.agent_id}</strong>
              {viewMode === 'agent' ? (
                <>
                  <span>radius {selectedAgent.perception?.radius ?? selectedAgent.perception_radius}</span>
                  <span>seen cells {selectedAgent.perception?.visible_cells?.length ?? 0}</span>
                  <span>perception tick {selectedAgent.perception?.tick ?? '-'}</span>
                </>
              ) : (
                <>
                  <span>known cells {selectedAgent.memory?.known_cell_count ?? 0}</span>
                  <span>known items {selectedAgent.memory?.known_item_count ?? 0}</span>
                  <span>congestion cells {selectedAgent.memory?.congestion_cell_count ?? 0}</span>
                  <span>max congestion {selectedAgent.memory_map?.max_congestion ?? 0}</span>
                </>
              )}
            </div>
          )}
          <div
            className="grid"
            style={{
              '--cell-size': `${Math.round(46 * (gridZoom / 100))}px`,
              gridTemplateColumns: `repeat(${boardWidth}, var(--cell-size))`,
            }}
          >
            {rows.flatMap((row) =>
              row.map((cell) => {
                const key = positionKey(cell.position)
                const memoryCell = memoryCellMap.get(key)
                const memoryCongestion = memoryCongestionMap.get(key) ?? 0
                const maxCongestion = selectedAgent?.memory_map?.max_congestion ?? 0
                const congestionIntensity = maxCongestion > 0 ? Math.min(memoryCongestion / maxCongestion, 1) : 0
                const rememberedAgent = memoryAgentMap.get(key)
                const agent = viewMode === 'memory'
                  ? (selectedAgent?.position && key === positionKey(selectedAgent.position) ? selectedAgent : null)
                  : agentMap.get(key)
                const items = viewMode === 'memory' ? memoryItemMap.get(key) ?? [] : itemMap.get(key) ?? []
                const displayType = viewMode === 'memory'
                  ? memoryCell?.cell_type ?? 'unknown'
                  : cell.cell_type
                const isPath = pathCells.has(key)
                const isPerceived = perceptionCells.has(key)
                const dimForAgentView = viewMode === 'agent' && selectedAgent && !isPerceived
                const isSelectedAgent = selectedAgent?.agent_id === agent?.agent_id
                return (
                  <button
                    key={key}
                    className={[
                      'cell',
                      displayType,
                      isPath ? 'path' : '',
                      viewMode === 'agent' && isPerceived ? 'perceived' : '',
                      viewMode === 'memory' && memoryCongestion > 0 ? 'congested' : '',
                      dimForAgentView ? 'outside-perception' : '',
                      isSelectedAgent ? 'selected-agent-cell' : '',
                    ].filter(Boolean).join(' ')}
                    style={{ '--congestion-alpha': congestionIntensity }}
                    type="button"
                    onClick={() => {
                      if (agent) setSelectedAgentId(agent.agent_id)
                      if (items[0]) setSelectedTaskId(items[0].task_id)
                    }}
                    title={
                      viewMode === 'memory'
                        ? `${cell.position[0]},${cell.position[1]} remembered ${displayType}; congestion ${memoryCongestion}`
                        : `${cell.position[0]},${cell.position[1]} ${cell.cell_type}`
                    }
                  >
                    <span className="cell-coord">{cell.position[0]},{cell.position[1]}</span>
                    {viewMode === 'memory' && memoryCell?.last_seen_tick !== undefined && (
                      <span className="memory-tick">t{memoryCell.last_seen_tick}</span>
                    )}
                    {items.map((item) => (
                      <span key={item.item_id} className={`box ${item.state}`}>
                        {item.item_id.replace(/[^0-9a-z]/gi, '').slice(-1).toUpperCase()}
                      </span>
                    ))}
                    {viewMode === 'memory' && rememberedAgent && !agent && (
                      <span className="agent remembered">
                        {rememberedAgent.agent_id.replace('agent_', 'A')}
                      </span>
                    )}
                    {agent && (
                      <span className={`agent ${agent.carrying_item_id ? 'carrying' : ''}`}>
                        {agent.agent_id.replace('agent_', 'A')}
                      </span>
                    )}
                    {viewMode === 'memory' && memoryCongestion > 0 && (
                      <span className="congestion-label">{congestionLabel(memoryCongestion)}</span>
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
                <span><strong>Radius</strong>{selectedAgent.perception?.radius ?? selectedAgent.perception_radius}</span>
                <span><strong>Visible cells</strong>{selectedAgent.perception?.visible_cells?.length ?? 0}</span>
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

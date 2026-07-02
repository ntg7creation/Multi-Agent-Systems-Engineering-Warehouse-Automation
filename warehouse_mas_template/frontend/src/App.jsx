import { useEffect, useMemo, useState } from 'react'
import {
  analyticsDownloadUrl,
  getAnalyticsAgents,
  getAnalyticsEvents,
  getAnalyticsReplay,
  getAnalyticsSummary,
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

function formatMetric(value, digits = 3) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value : value.toFixed(digits)
  }
  return value
}

const PATH_WEIGHT_FIELDS = [
  { key: 'alpha_distance', label: 'alpha_distance', step: 0.05 },
  { key: 'beta_congestion', label: 'beta_congestion', step: 0.05 },
  { key: 'gamma_failed_route', label: 'gamma_failed_route', step: 0.05 },
  { key: 'delta_uncertainty', label: 'delta_uncertainty', step: 0.05 },
  { key: 'occupied_penalty', label: 'occupied_penalty', step: 0.05 },
  { key: 'max_candidates', label: 'max_candidates', step: 1, integer: true },
  { key: 'near_optimal_margin', label: 'near_optimal_margin', step: 0.05 },
  { key: 'max_expansion_multiplier', label: 'max_expansion_multiplier', step: 1, integer: true },
]

const CONGESTION_FIELDS = [
  { key: 'decay', label: 'decay', step: 0.05 },
  { key: 'nearby_agent_weight', label: 'nearby_agent_weight', step: 0.05 },
  { key: 'waiting_weight', label: 'waiting_weight', step: 0.05 },
  { key: 'failed_move_weight', label: 'failed_move_weight', step: 0.05 },
  { key: 'blocked_path_weight', label: 'blocked_path_weight', step: 0.05 },
  { key: 'communicated_weight', label: 'communicated_weight', step: 0.05 },
  { key: 'path_padding', label: 'path_padding', step: 1, integer: true },
]

const BASELINE_CONFIG = {
  perception_radius: 3,
  allocation_strategy: 'nearest_available',
  routing_strategy: 'local_memory_astar',
  path_weights: {
    alpha_distance: 1.0,
    beta_congestion: 0.0,
    gamma_failed_route: 0.0,
    delta_uncertainty: 0.0,
    occupied_penalty: 0.0,
    max_candidates: 1,
    near_optimal_margin: 0.0,
    max_expansion_multiplier: 10,
  },
  congestion: {
    decay: 0.0,
    nearby_agent_weight: 0.0,
    waiting_weight: 0.0,
    failed_move_weight: 0.0,
    blocked_path_weight: 0.0,
    communicated_weight: 0.0,
    path_padding: 0,
  },
}

function cloneConfig(config) {
  return config ? JSON.parse(JSON.stringify(config)) : null
}

function fieldNumber(value, integer = false) {
  if (value === '' || value === null || value === undefined) return 0
  const parsed = integer ? parseInt(value, 10) : parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function sanitizeConfig(config) {
  if (!config) return undefined
  return {
    perception_radius: fieldNumber(config.perception_radius, true),
    allocation_strategy: config.allocation_strategy || 'nearest_available',
    routing_strategy: config.routing_strategy || 'local_memory_astar',
    path_weights: Object.fromEntries(
      PATH_WEIGHT_FIELDS.map((field) => [
        field.key,
        fieldNumber(config.path_weights?.[field.key], field.integer),
      ]),
    ),
    congestion: Object.fromEntries(
      CONGESTION_FIELDS.map((field) => [
        field.key,
        fieldNumber(config.congestion?.[field.key], field.integer),
      ]),
    ),
  }
}

const AGENT_PATH_COLORS = [
  '#2563eb',
  '#dc2626',
  '#059669',
  '#d97706',
  '#7c3aed',
  '#0891b2',
  '#be123c',
  '#4d7c0f',
  '#9333ea',
  '#0f766e',
]

const PATH_OFFSETS = [
  [0, 0],
  [-4, -4],
  [4, -4],
  [-4, 4],
  [4, 4],
  [0, -6],
  [6, 0],
  [0, 6],
  [-6, 0],
  [6, 6],
]

function exportPositionText(position) {
  return position ? `${position[0]},${position[1]}` : '-'
}

function safeFileName(value) {
  return String(value || 'run').replace(/[^a-z0-9_-]+/gi, '_')
}

function fitCanvasText(ctx, value, maxWidth) {
  const text = value === null || value === undefined || value === '' ? '-' : String(value)
  if (ctx.measureText(text).width <= maxWidth) return text

  let truncated = text
  while (truncated.length > 1 && ctx.measureText(`${truncated}...`).width > maxWidth) {
    truncated = truncated.slice(0, -1)
  }
  return `${truncated}...`
}

function buildAgentPaths(state, replayFrames) {
  const paths = new Map()

  const ensurePath = (agentId) => {
    if (!agentId) return null
    if (!paths.has(agentId)) paths.set(agentId, [])
    return paths.get(agentId)
  }

  const pushPosition = (agent) => {
    const path = ensurePath(agent?.agent_id)
    if (!path || !agent?.position) return
    const position = [Number(agent.position[0]), Number(agent.position[1])]
    const last = path[path.length - 1]
    if (!last || last[0] !== position[0] || last[1] !== position[1]) {
      path.push(position)
    }
  }

  state?.agents?.forEach((agent) => ensurePath(agent.agent_id))

  const frames = Array.isArray(replayFrames) ? replayFrames : []
  frames[0]?.before?.agents?.forEach(pushPosition)
  frames.forEach((frame) => {
    frame.after?.agents?.forEach(pushPosition)
  })

  const hasRecordedPath = Array.from(paths.values()).some((path) => path.length > 0)
  if (!hasRecordedPath) {
    state?.agents?.forEach(pushPosition)
  }

  return Array.from(paths.entries()).map(([agentId, positions], index) => ({
    agentId,
    positions,
    color: AGENT_PATH_COLORS[index % AGENT_PATH_COLORS.length],
    offset: PATH_OFFSETS[index % PATH_OFFSETS.length],
  }))
}

function canvasCellCenter(position, mapX, mapY, cellSize, cellGap, offset = [0, 0]) {
  return [
    mapX + position[0] * (cellSize + cellGap) + cellSize / 2 + offset[0],
    mapY + position[1] * (cellSize + cellGap) + cellSize / 2 + offset[1],
  ]
}

function normalizePosition(position) {
  if (!Array.isArray(position) || position.length < 2) return null
  return [Number(position[0]), Number(position[1])]
}

function buildAgentMilestones(state, replayFrames, agentPaths) {
  const milestones = new Map()
  const pathInfo = new Map(agentPaths.map((path) => [path.agentId, path]))

  const addMilestone = (agentId, position, label) => {
    const normalized = normalizePosition(position)
    if (!agentId || !normalized) return
    const path = pathInfo.get(agentId)
    const bucket = milestones.get(agentId) ?? []
    bucket.push({
      agentId,
      color: path?.color ?? AGENT_PATH_COLORS[bucket.length % AGENT_PATH_COLORS.length],
      label: label ?? bucket.length,
      offset: path?.offset ?? [0, 0],
      position: normalized,
    })
    milestones.set(agentId, bucket)
  }

  agentPaths.forEach((path) => {
    if (path.positions[0]) addMilestone(path.agentId, path.positions[0], 0)
  })

  const frames = Array.isArray(replayFrames) ? replayFrames : []
  frames.forEach((frame) => {
    frame.results?.forEach((result) => {
      const actionType = result.action?.type
      if (!result.success || !['pickup', 'place'].includes(actionType)) return
      const agentId = result.agent_id
      const nextLabel = milestones.get(agentId)?.length ?? 0
      addMilestone(agentId, result.target_position ?? result.source_position, nextLabel)
    })
  })

  state?.agents?.forEach((agent) => {
    if (!milestones.has(agent.agent_id)) addMilestone(agent.agent_id, agent.position, 0)
  })

  return Array.from(milestones.values()).flat()
}

function drawMilestoneMarkers(ctx, milestones, mapX, mapY, cellSize, cellGap) {
  const markerCounts = new Map()
  const stackOffsets = [
    [0, 0],
    [-8, -8],
    [8, -8],
    [-8, 8],
    [8, 8],
    [0, -11],
    [11, 0],
    [0, 11],
    [-11, 0],
  ]

  ctx.save()
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  milestones.forEach((milestone) => {
    const label = String(milestone.label)
    const radius = label.length > 1 ? 10 : 8
    const markerKey = `${milestone.agentId}-${milestone.position.join(',')}`
    const stackIndex = markerCounts.get(markerKey) ?? 0
    markerCounts.set(markerKey, stackIndex + 1)
    const stackOffset = stackOffsets[stackIndex % stackOffsets.length]
    const markerOffset = [
      milestone.offset[0] + stackOffset[0],
      milestone.offset[1] + stackOffset[1],
    ]
    const [x, y] = canvasCellCenter(milestone.position, mapX, mapY, cellSize, cellGap, markerOffset)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.94)'
    ctx.strokeStyle = milestone.color
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    ctx.fillStyle = milestone.color
    ctx.font = '700 10px Inter, Arial, sans-serif'
    ctx.fillText(label, x, y + 0.5)
  })
  ctx.restore()
}

function drawFinalMapImage(state, replayFrames) {
  const rows = state?.board?.rows ?? []
  const boardWidth = state?.board?.width ?? rows[0]?.length ?? 1
  const boardHeight = state?.board?.height ?? rows.length ?? 1
  const cellSize = 42
  const cellGap = 3
  const padding = 32
  const mapWidth = boardWidth * cellSize + Math.max(0, boardWidth - 1) * cellGap
  const mapHeight = boardHeight * cellSize + Math.max(0, boardHeight - 1) * cellGap
  const contentWidth = Math.max(mapWidth, 960)
  const agentPaths = buildAgentPaths(state, replayFrames)
  const agentMilestones = buildAgentMilestones(state, replayFrames, agentPaths)
  const legendColumns = Math.min(4, Math.max(1, agentPaths.length))
  const legendRows = Math.ceil(Math.max(1, agentPaths.length) / legendColumns)
  const legendHeight = agentPaths.length ? legendRows * 24 + 18 : 0
  const taskRows = state?.tasks ?? []
  const tableTitleHeight = 34
  const tableHeaderHeight = 32
  const tableRowHeight = 30
  const tableHeight = tableTitleHeight + tableHeaderHeight + Math.max(1, taskRows.length) * tableRowHeight
  const headerHeight = 68
  const mapToTableGap = 24
  const canvasWidth = contentWidth + padding * 2
  const canvasHeight = padding * 2 + headerHeight + mapHeight + legendHeight + mapToTableGap + tableHeight
  const pixelRatio = 2
  const canvas = document.createElement('canvas')
  canvas.width = canvasWidth * pixelRatio
  canvas.height = canvasHeight * pixelRatio
  const ctx = canvas.getContext('2d')
  ctx.scale(pixelRatio, pixelRatio)

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)
  ctx.fillStyle = '#172033'
  ctx.font = '700 24px Inter, Arial, sans-serif'
  ctx.fillText('Warehouse MAS Final Map', padding, padding + 24)
  ctx.fillStyle = '#607089'
  ctx.font = '14px Inter, Arial, sans-serif'
  ctx.fillText(`Run ${state?.run_id ?? '-'} - tick ${state?.tick ?? '-'}`, padding, padding + 48)

  const mapX = padding + (contentWidth - mapWidth) / 2
  const mapY = padding + headerHeight
  const cellColors = {
    road: '#f8fafc',
    blocked: '#58677a',
    pickup: '#a7f3d0',
    dropoff: '#fed7aa',
    unknown: '#e2e8f0',
  }

  rows.forEach((row) => {
    row.forEach((cell) => {
      const [x, y] = cell.position
      const left = mapX + x * (cellSize + cellGap)
      const top = mapY + y * (cellSize + cellGap)
      ctx.fillStyle = cellColors[cell.cell_type] ?? cellColors.road
      ctx.fillRect(left, top, cellSize, cellSize)
      ctx.strokeStyle = 'rgba(18, 30, 48, 0.16)'
      ctx.lineWidth = 1
      ctx.strokeRect(left + 0.5, top + 0.5, cellSize - 1, cellSize - 1)
    })
  })

  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.lineWidth = 5
  ctx.globalAlpha = 0.88
  agentPaths.forEach((path) => {
    if (!path.positions.length) return
    ctx.strokeStyle = path.color
    ctx.fillStyle = path.color
    if (path.positions.length === 1) {
      const [x, y] = canvasCellCenter(path.positions[0], mapX, mapY, cellSize, cellGap, path.offset)
      ctx.beginPath()
      ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fill()
      return
    }
    ctx.beginPath()
    path.positions.forEach((position, index) => {
      const [x, y] = canvasCellCenter(position, mapX, mapY, cellSize, cellGap, path.offset)
      if (index === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })
    ctx.stroke()
  })
  ctx.restore()

  rows.forEach((row) => {
    row.forEach((cell) => {
      if (!['pickup', 'dropoff'].includes(cell.cell_type)) return
      const [x, y] = cell.position
      const left = mapX + x * (cellSize + cellGap)
      const top = mapY + y * (cellSize + cellGap)
      ctx.fillStyle = cell.cell_type === 'pickup' ? '#065f46' : '#9a3412'
      ctx.font = '700 12px Inter, Arial, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(cell.cell_type === 'pickup' ? 'P' : 'D', left + cellSize / 2, top + cellSize / 2 + 4)
      ctx.textAlign = 'left'
    })
  })

  const itemByPosition = new Map()
  state?.items?.forEach((item) => {
    if (!item.position) return
    const key = positionKey(item.position)
    const bucket = itemByPosition.get(key) ?? []
    bucket.push(item)
    itemByPosition.set(key, bucket)
  })

  itemByPosition.forEach((items, key) => {
    const [x, y] = key.split(',').map(Number)
    const left = mapX + x * (cellSize + cellGap) + 4
    const top = mapY + y * (cellSize + cellGap) + cellSize - 18
    items.slice(0, 2).forEach((item, index) => {
      ctx.fillStyle = item.state === 'delivered' ? '#22c55e' : '#eab308'
      ctx.fillRect(left + index * 15, top, 14, 14)
      ctx.fillStyle = item.state === 'delivered' ? '#ffffff' : '#1f2937'
      ctx.font = '700 9px Inter, Arial, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(item.item_id.replace(/[^0-9a-z]/gi, '').slice(-1).toUpperCase(), left + index * 15 + 7, top + 10)
      ctx.textAlign = 'left'
    })
  })

  const colorByAgent = new Map(agentPaths.map((path) => [path.agentId, path.color]))
  state?.agents?.forEach((agent, index) => {
    if (!agent.position) return
    const color = colorByAgent.get(agent.agent_id) ?? AGENT_PATH_COLORS[index % AGENT_PATH_COLORS.length]
    const [x, y] = canvasCellCenter(agent.position, mapX, mapY, cellSize, cellGap)
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(x, y, 13, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#ffffff'
    ctx.font = '700 10px Inter, Arial, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(agent.agent_id.replace('agent_', 'A'), x, y + 4)
    ctx.textAlign = 'left'
  })

  drawMilestoneMarkers(ctx, agentMilestones, mapX, mapY, cellSize, cellGap)

  const legendY = mapY + mapHeight + 18
  if (agentPaths.length) {
    const legendColumnWidth = contentWidth / legendColumns
    ctx.font = '700 13px Inter, Arial, sans-serif'
    agentPaths.forEach((path, index) => {
      const x = padding + (index % legendColumns) * legendColumnWidth
      const y = legendY + Math.floor(index / legendColumns) * 24
      ctx.strokeStyle = path.color
      ctx.lineWidth = 5
      ctx.beginPath()
      ctx.moveTo(x, y + 8)
      ctx.lineTo(x + 26, y + 8)
      ctx.stroke()
      ctx.fillStyle = '#26364f'
      ctx.fillText(path.agentId, x + 36, y + 12)
    })
  }

  const tableY = legendY + legendHeight + mapToTableGap
  ctx.fillStyle = '#172033'
  ctx.font = '700 18px Inter, Arial, sans-serif'
  ctx.fillText('Task List', padding, tableY + 22)

  const columns = [
    { label: 'Task', width: 125, value: (task) => task.task_id },
    { label: 'Status', width: 95, value: (task) => task.status },
    { label: 'Agent', width: 120, value: (task) => task.assigned_agent_id ?? '-' },
    { label: 'Item', width: 95, value: (task) => task.item_id },
    { label: 'Pickup', width: 105, value: (task) => exportPositionText(task.pickup_position) },
    { label: 'Delivery', width: 105, value: (task) => exportPositionText(task.dropoff_position) },
    { label: 'Created', width: 85, value: (task) => task.created_tick },
    { label: 'Assigned', width: 85, value: (task) => task.assigned_tick ?? '-' },
    { label: 'Picked', width: 75, value: (task) => task.picked_tick ?? '-' },
    { label: 'Delivered', width: 90, value: (task) => task.delivered_tick ?? '-' },
  ]
  const baseWidth = columns.reduce((sum, column) => sum + column.width, 0)
  const tableScale = contentWidth / baseWidth
  let x = padding
  const headerY = tableY + tableTitleHeight
  ctx.fillStyle = '#f8fafc'
  ctx.fillRect(padding, headerY, contentWidth, tableHeaderHeight)
  ctx.strokeStyle = '#d8dee8'
  ctx.strokeRect(padding, headerY, contentWidth, tableHeaderHeight)
  ctx.font = '700 11px Inter, Arial, sans-serif'
  ctx.fillStyle = '#64748b'
  columns.forEach((column) => {
    const width = column.width * tableScale
    ctx.fillText(column.label.toUpperCase(), x + 8, headerY + 21)
    x += width
  })

  const rowsToDraw = taskRows.length ? taskRows : [{ task_id: 'No tasks', status: '-', item_id: '-' }]
  rowsToDraw.forEach((task, rowIndex) => {
    const y = headerY + tableHeaderHeight + rowIndex * tableRowHeight
    ctx.fillStyle = rowIndex % 2 === 0 ? '#ffffff' : '#f8fafc'
    ctx.fillRect(padding, y, contentWidth, tableRowHeight)
    ctx.strokeStyle = '#e1e7ef'
    ctx.beginPath()
    ctx.moveTo(padding, y + tableRowHeight)
    ctx.lineTo(padding + contentWidth, y + tableRowHeight)
    ctx.stroke()
    ctx.font = '13px Inter, Arial, sans-serif'
    ctx.fillStyle = '#243246'
    x = padding
    columns.forEach((column) => {
      const width = column.width * tableScale
      const text = fitCanvasText(ctx, column.value(task), width - 12)
      ctx.fillText(text, x + 8, y + 20)
      x += width
    })
  })

  return canvas
}

function downloadCanvas(canvas, filename) {
  const link = document.createElement('a')
  link.href = canvas.toDataURL('image/png')
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
}

function MetricCard({ label, value }) {
  return (
    <span>
      <strong>{label}</strong>
      {formatMetric(value)}
    </span>
  )
}

function BarChart({ rows, labelKey, valueKey }) {
  const max = Math.max(1, ...rows.map((row) => Number(row[valueKey]) || 0))
  return (
    <div className="bar-chart">
      {rows.length ? rows.map((row) => {
        const value = Number(row[valueKey]) || 0
        return (
          <div key={`${row[labelKey]}-${valueKey}`} className="bar-row">
            <span>{row[labelKey]}</span>
            <div className="bar-track">
              <i style={{ width: `${Math.max(3, (value / max) * 100)}%` }} />
            </div>
            <strong>{formatMetric(value)}</strong>
          </div>
        )
      }) : <p className="empty">No chart data yet.</p>}
    </div>
  )
}

function AnalyticsView({ analytics, refreshAnalytics }) {
  const summary = analytics.summary
  const system = summary?.system ?? {}
  const agents = Object.values(analytics.agents?.agents ?? summary?.agents ?? {})
  const events = analytics.events?.events ?? []
  const timeline = summary?.timeline ?? []
  const latestFrame = analytics.replay?.frames?.slice(-1)?.[0]
  const utilityRows = agents.map((agent) => ({
    agent_id: agent.agent_id,
    utility_score: agent.utility_score ?? 0,
  }))
  const countDelta = (rows, key) => rows.map((row, index) => ({
    tick: `T${row.tick ?? index}`,
    value: Math.max(0, Number(row[key] ?? 0) - Number(rows[index - 1]?.[key] ?? 0)),
  }))

  return (
    <main className="analytics-layout">
      <section className="analytics-header">
        <div>
          <h2>Analytics</h2>
          <p className="subtitle">
            {summary?.run_id ? `Run ${summary.run_id}` : 'Start or step the simulation to collect analytics.'}
          </p>
        </div>
        <div className="analytics-actions">
          <button className="secondary" type="button" onClick={refreshAnalytics}>Refresh analytics</button>
          <a className="download-button" href={analyticsDownloadUrl('json')}>Download JSON</a>
          <a className="download-button" href={analyticsDownloadUrl('csv')}>Download CSV</a>
        </div>
      </section>

      <section className="stats analytics-stats">
        <MetricCard label="Tick" value={system.current_tick ?? system.total_steps} />
        <MetricCard label="Completed" value={system.completed_deliveries} />
        <MetricCard label="Completion rate" value={system.task_completion_rate} />
        <MetricCard label="Throughput" value={system.throughput} />
        <MetricCard label="Avg task time" value={system.average_completion_time} />
        <MetricCard label="Total waits" value={system.total_waiting_actions ?? system.wait_actions} />
        <MetricCard label="Blocked moves" value={system.total_blocked_movements ?? system.blocked_move_attempts} />
        <MetricCard label="Replans" value={system.route_replans} />
        <MetricCard label="CAS" value={system.collision_avoidance_score} />
        <MetricCard label="Social welfare" value={system.social_welfare} />
      </section>

      <section className="analytics-grid">
        <section className="card analytics-table-card">
          <h2>Per-Agent Metrics</h2>
          {agents.length ? (
            <div className="table-scroll">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Tasks</th>
                    <th>Actions</th>
                    <th>Useful</th>
                    <th>Efficiency</th>
                    <th>Waits</th>
                    <th>Failed moves</th>
                    <th>Replans</th>
                    <th>Utility</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((agent) => (
                    <tr key={agent.agent_id}>
                      <td>{agent.agent_id}</td>
                      <td>{agent.tasks_completed ?? agent.completed_tasks ?? 0}</td>
                      <td>{agent.total_actions ?? 0}</td>
                      <td>{agent.useful_actions ?? 0}</td>
                      <td>{formatMetric(agent.efficiency)}</td>
                      <td>{agent.wait_count ?? agent.wait_actions ?? 0}</td>
                      <td>{agent.failed_movement_count ?? agent.blocked_move_attempts ?? 0}</td>
                      <td>{agent.replanning_count ?? agent.route_replans ?? 0}</td>
                      <td>{formatMetric(agent.utility_score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="empty">No agent metrics are available yet.</p>}
        </section>

        <section className="card">
          <h2>Utility Per Agent</h2>
          <BarChart rows={utilityRows} labelKey="agent_id" valueKey="utility_score" />
        </section>

        <section className="card">
          <h2>Completed Deliveries Over Time</h2>
          <BarChart
            rows={timeline.map((row) => ({ tick: `T${row.tick}`, completed_deliveries: row.completed_deliveries }))}
            labelKey="tick"
            valueKey="completed_deliveries"
          />
        </section>

        <section className="card">
          <h2>Wait / Block / Replan Events</h2>
          <div className="mini-chart-stack">
            <span>Waits</span>
            <BarChart rows={countDelta(timeline, 'wait_actions')} labelKey="tick" valueKey="value" />
            <span>Blocked</span>
            <BarChart rows={countDelta(timeline, 'blocked_move_attempts')} labelKey="tick" valueKey="value" />
            <span>Replans</span>
            <BarChart rows={countDelta(timeline, 'route_replans')} labelKey="tick" valueKey="value" />
          </div>
        </section>

        <section className="card analytics-table-card event-log-wide">
          <h2>Event Log Viewer</h2>
          {events.length ? (
            <div className="table-scroll event-table-scroll">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th>Tick</th>
                    <th>Event</th>
                    <th>Agent</th>
                    <th>Task</th>
                    <th>Result</th>
                    <th>Reason / Details</th>
                  </tr>
                </thead>
                <tbody>
                  {events.slice().reverse().map((event) => (
                    <tr key={event.event_id}>
                      <td>{event.tick}</td>
                      <td>{event.type}</td>
                      <td>{event.agent_id ?? '-'}</td>
                      <td>{event.task_id ?? '-'}</td>
                      <td>{event.result ?? '-'}</td>
                      <td>{event.rejection_reason || event.message || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="empty">No analytics events yet.</p>}
        </section>

        <section className="card">
          <h2>Replay Snapshot</h2>
          {latestFrame ? (
            <div className="details split">
              <span><strong>Latest tick</strong>{latestFrame.tick}</span>
              <span><strong>Frames</strong>{analytics.replay?.frames?.length ?? 0}</span>
              <span><strong>Actions</strong>{latestFrame.intended_actions?.length ?? 0}</span>
              <span><strong>Results</strong>{latestFrame.results?.length ?? 0}</span>
            </div>
          ) : <p className="empty">No replay frames yet.</p>}
        </section>
      </section>
    </main>
  )
}

function App() {
  const [state, setState] = useState(null)
  const [analytics, setAnalytics] = useState({
    summary: null,
    events: { events: [] },
    agents: { agents: {}, decision_log: [] },
    replay: { frames: [] },
  })
  const [scenarios, setScenarios] = useState([])
  const [scenarioId, setScenarioId] = useState('default')
  const [seed, setSeed] = useState('42')
  const [configDraft, setConfigDraft] = useState(null)
  const [configDirty, setConfigDirty] = useState(false)
  const [stepDelay, setStepDelay] = useState(600)
  const [gridZoom, setGridZoom] = useState(100)
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [viewMode, setViewMode] = useState('global')
  const [activeTab, setActiveTab] = useState('simulation')
  const [error, setError] = useState('')
  const [exportStatus, setExportStatus] = useState('')

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

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.scenario_id === scenarioId),
    [scenarioId, scenarios],
  )

  const visibleConfig = configDraft
    ?? state?.scenario?.config
    ?? selectedScenario?.config
    ?? BASELINE_CONFIG

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

  async function refreshState({ forceConfig = false } = {}) {
    try {
      const data = await getState()
      setState(data)
      setScenarioId(data.scenario?.scenario_id ?? 'default')
      setSeed(String(data.seed ?? ''))
      if (forceConfig || !configDirty) {
        setConfigDraft(cloneConfig(data.scenario?.config))
        setConfigDirty(false)
      }
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
      if (!configDraft && !configDirty) {
        const activeScenario = data.scenarios?.find((scenario) => scenario.scenario_id === scenarioId)
        if (activeScenario?.config) setConfigDraft(cloneConfig(activeScenario.config))
      }
    } catch (err) {
      setScenarios([])
    }
  }

  async function refreshAnalytics() {
    try {
      const [summary, events, agentsData, replay] = await Promise.all([
        getAnalyticsSummary(),
        getAnalyticsEvents(250),
        getAnalyticsAgents(),
        getAnalyticsReplay(250),
      ])
      setAnalytics({ summary, events, agents: agentsData, replay })
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  async function perform(action, { syncConfig = false } = {}) {
    try {
      const data = await action()
      if (data?.tick !== undefined) {
        setState(data)
        if (syncConfig || !configDirty) {
          setConfigDraft(cloneConfig(data.scenario?.config))
          setConfigDirty(false)
        }
      } else {
        await refreshState({ forceConfig: syncConfig })
      }
      await refreshAnalytics()
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  async function downloadFinalMap() {
    if (!state?.is_complete) return
    try {
      setExportStatus('Preparing image...')
      const replay = await getAnalyticsReplay(null)
      const canvas = drawFinalMapImage(state, replay.frames ?? [])
      const scenarioName = state.scenario?.name ?? state.scenario?.scenario_id ?? 'scenario'
      downloadCanvas(canvas, `warehouse-final-map-${safeFileName(scenarioName)}-${safeFileName(state.run_id)}.png`)
      setExportStatus('Downloaded final map.')
      window.setTimeout(() => setExportStatus(''), 2500)
      setError('')
    } catch (err) {
      setExportStatus('')
      setError(err.message)
    }
  }

  function handleScenarioChange(nextScenarioId) {
    setScenarioId(nextScenarioId)
    const nextScenario = scenarios.find((scenario) => scenario.scenario_id === nextScenarioId)
    if (nextScenario?.config) {
      setConfigDraft(cloneConfig(nextScenario.config))
      setConfigDirty(false)
    }
  }

  function updateConfigField(section, key, value) {
    setConfigDirty(true)
    setConfigDraft((current) => {
      const base = cloneConfig(current ?? visibleConfig)
      if (section === 'root') {
        base[key] = value
      } else {
        base[section] = { ...(base[section] ?? {}), [key]: value }
      }
      return base
    })
  }

  function applyScenarioConfig() {
    const source = selectedScenario?.config ?? state?.scenario?.config
    setConfigDraft(cloneConfig(source))
    setConfigDirty(false)
  }

  function applyBaselineConfig() {
    setConfigDraft(cloneConfig(BASELINE_CONFIG))
    setConfigDirty(true)
  }

  useEffect(() => {
    refreshScenarios()
    refreshState()
    refreshAnalytics()
  }, [])

  useEffect(() => {
    if (!state?.autorun?.active) return undefined
    const id = setInterval(refreshState, Math.max(150, stepDelay))
    return () => clearInterval(id)
  }, [state?.autorun?.active, stepDelay, configDirty])

  useEffect(() => {
    if (!state?.autorun?.active) return undefined
    const id = setInterval(refreshAnalytics, Math.max(250, stepDelay))
    return () => clearInterval(id)
  }, [state?.autorun?.active, stepDelay])

  const rows = state?.board?.rows ?? []
  const boardWidth = state?.board?.width ?? 1
  const metrics = state?.metrics?.global ?? {}
  const agentMetrics = selectedAgent ? state?.metrics?.agents?.[selectedAgent.agent_id] : null
  const activeTasks = state?.tasks?.filter((task) => task.status !== 'delivered') ?? []
  const isSimulationComplete = Boolean(state?.is_complete)

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
            <select value={scenarioId} onChange={(event) => handleScenarioChange(event.target.value)}>
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
          <button onClick={() => perform(() => resetSimulation({
            scenarioId,
            seed: seed === '' ? undefined : Number(seed),
            config: sanitizeConfig(visibleConfig),
          }), { syncConfig: true })}>
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

      <section className="config-panel">
        <div className="config-header">
          <h2>Strategy Config</h2>
          <div className="config-actions">
            <button className="secondary" type="button" onClick={applyScenarioConfig}>Scenario</button>
            <button className="secondary" type="button" onClick={applyBaselineConfig}>Baseline</button>
          </div>
        </div>

        <div className="config-grid root-config">
          <label>
            perception_radius
            <input
              type="number"
              min="0"
              step="1"
              value={visibleConfig?.perception_radius ?? ''}
              onChange={(event) => updateConfigField('root', 'perception_radius', event.target.value)}
            />
          </label>
          <label>
            allocation_strategy
            <select
              value={visibleConfig?.allocation_strategy ?? 'nearest_available'}
              onChange={(event) => updateConfigField('root', 'allocation_strategy', event.target.value)}
            >
              <option value="nearest_available">nearest_available</option>
            </select>
          </label>
          <label>
            routing_strategy
            <select
              value={visibleConfig?.routing_strategy ?? 'local_memory_astar'}
              onChange={(event) => updateConfigField('root', 'routing_strategy', event.target.value)}
            >
              <option value="local_memory_astar">local_memory_astar</option>
            </select>
          </label>
        </div>

        <div className="config-columns">
          <div className="config-group">
            <h3>path_weights</h3>
            <div className="config-grid">
              {PATH_WEIGHT_FIELDS.map((field) => (
                <label key={field.key}>
                  {field.label}
                  <input
                    type="number"
                    step={field.step}
                    min={field.integer ? 0 : undefined}
                    value={visibleConfig?.path_weights?.[field.key] ?? ''}
                    onChange={(event) => updateConfigField('path_weights', field.key, event.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="config-group">
            <h3>congestion</h3>
            <div className="config-grid">
              {CONGESTION_FIELDS.map((field) => (
                <label key={field.key}>
                  {field.label}
                  <input
                    type="number"
                    step={field.step}
                    min={field.integer ? 0 : undefined}
                    value={visibleConfig?.congestion?.[field.key] ?? ''}
                    onChange={(event) => updateConfigField('congestion', field.key, event.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      <nav className="tabbar" aria-label="Dashboard sections">
        <button
          className={activeTab === 'simulation' ? 'active' : ''}
          type="button"
          onClick={() => setActiveTab('simulation')}
        >
          Simulation
        </button>
        <button
          className={activeTab === 'analytics' ? 'active' : ''}
          type="button"
          onClick={() => {
            setActiveTab('analytics')
            refreshAnalytics()
          }}
        >
          Analytics
        </button>
      </nav>

      {activeTab === 'analytics' ? (
        <AnalyticsView analytics={analytics} refreshAnalytics={refreshAnalytics} />
      ) : (
        <>

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

      {isSimulationComplete && (
        <section className="completion-actions">
          <div className="completion-copy">
            <strong>Simulation complete</strong>
            <span>All tasks delivered at tick {state?.tick ?? '-'}.</span>
          </div>
          <button
            className="download-button"
            disabled={exportStatus === 'Preparing image...'}
            type="button"
            onClick={downloadFinalMap}
          >
            Download final map
          </button>
          {exportStatus && <span className="export-status">{exportStatus}</span>}
        </section>
      )}

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
        </>
      )}
    </div>
  )
}

export default App

#!/usr/bin/env node

import fs from 'node:fs/promises'
import path from 'node:path'
import { createCanvas } from '@napi-rs/canvas'

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

function parseArgs(argv) {
  const args = {}
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i]
    if (!key.startsWith('--')) continue
    const value = argv[i + 1]
    args[key.slice(2)] = value
    i += 1
  }
  if (!args.state || !args.replay || !args.out) {
    throw new Error('Usage: node render_final_map_cli.mjs --state <final_state.json> --replay <replay.json> --out <output.png>')
  }
  return args
}

function positionKey(position) {
  return position ? position.join(',') : ''
}

function exportPositionText(position) {
  return position ? `${position[0]},${position[1]}` : '-'
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

  const hasRecordedPath = Array.from(paths.values()).some((line) => line.length > 0)
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
  const pathInfo = new Map(agentPaths.map((line) => [line.agentId, line]))

  const addMilestone = (agentId, position, label) => {
    const normalized = normalizePosition(position)
    if (!agentId || !normalized) return
    const line = pathInfo.get(agentId)
    const bucket = milestones.get(agentId) ?? []
    bucket.push({
      agentId,
      color: line?.color ?? AGENT_PATH_COLORS[bucket.length % AGENT_PATH_COLORS.length],
      label: label ?? bucket.length,
      offset: line?.offset ?? [0, 0],
      position: normalized,
    })
    milestones.set(agentId, bucket)
  }

  agentPaths.forEach((line) => {
    if (line.positions[0]) addMilestone(line.agentId, line.positions[0], 0)
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

  const canvas = createCanvas(canvasWidth, canvasHeight)
  const ctx = canvas.getContext('2d')

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
  agentPaths.forEach((line) => {
    if (!line.positions.length) return
    ctx.strokeStyle = line.color
    ctx.fillStyle = line.color
    if (line.positions.length === 1) {
      const [x, y] = canvasCellCenter(line.positions[0], mapX, mapY, cellSize, cellGap, line.offset)
      ctx.beginPath()
      ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fill()
      return
    }
    ctx.beginPath()
    line.positions.forEach((position, index) => {
      const [x, y] = canvasCellCenter(position, mapX, mapY, cellSize, cellGap, line.offset)
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

  const colorByAgent = new Map(agentPaths.map((line) => [line.agentId, line.color]))
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
    agentPaths.forEach((line, index) => {
      const x = padding + (index % legendColumns) * legendColumnWidth
      const y = legendY + Math.floor(index / legendColumns) * 24
      ctx.strokeStyle = line.color
      ctx.lineWidth = 5
      ctx.beginPath()
      ctx.moveTo(x, y + 8)
      ctx.lineTo(x + 26, y + 8)
      ctx.stroke()
      ctx.fillStyle = '#26364f'
      ctx.fillText(line.agentId, x + 36, y + 12)
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

async function readJson(filePath) {
  const text = await fs.readFile(filePath, 'utf-8')
  return JSON.parse(text)
}

async function main() {
  const args = parseArgs(process.argv)
  const state = await readJson(args.state)
  const replayJson = await readJson(args.replay)
  const replayFrames = Array.isArray(replayJson) ? replayJson : (replayJson.frames ?? [])

  const canvas = drawFinalMapImage(state, replayFrames)
  const buffer = canvas.toBuffer('image/png')

  await fs.mkdir(path.dirname(args.out), { recursive: true })
  await fs.writeFile(args.out, buffer)
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error))
  process.exit(1)
})

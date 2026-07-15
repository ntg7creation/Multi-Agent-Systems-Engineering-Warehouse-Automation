import { getSimulationAdapter } from '../simulation/PyodideSimulationAdapter.js'

const adapter = getSimulationAdapter()

export function getState() {
  return adapter.getState()
}

export function getScenarios() {
  return adapter.listScenarios()
}

export function getAnalyticsSummary() {
  return adapter.getAnalyticsSummary()
}

export function getAnalyticsEvents(limit = 200) {
  return adapter.getAnalyticsEvents(limit)
}

export function getAnalyticsAgents() {
  return adapter.getAnalyticsAgents()
}

export function getAnalyticsReplay(limit = 200) {
  return adapter.getAnalyticsReplay(limit)
}

export function tick(steps = 1) {
  return adapter.step(steps)
}

export function runSteps(steps = 10) {
  return adapter.run(steps)
}

export function resetSimulation({ scenarioId = 'default', seed, config } = {}) {
  return adapter.reset({ scenarioId, seed, config })
}

export function loadScenario({ scenarioId = 'default', seed, config } = {}) {
  return adapter.loadScenario({ scenarioId, seed, config })
}

export function startSimulation({ delayMs = 600, maxTicks = null } = {}) {
  return adapter.start({ delayMs, maxTicks })
}

export function pauseSimulation() {
  return adapter.pause()
}

export function resumeSimulation({ delayMs = 600, maxTicks = null } = {}) {
  return adapter.resume({ delayMs, maxTicks })
}

export function startAutorun({ delayMs = 600, maxTicks = null } = {}) {
  return adapter.start({ delayMs, maxTicks })
}

export function stopAutorun() {
  return adapter.pause()
}

export async function downloadAnalytics(format) {
  const data = await adapter.exportAnalytics(format)
  const isCsv = format === 'csv'
  const blob = new Blob(
    [isCsv ? String(data) : JSON.stringify(data, null, 2)],
    { type: isCsv ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8' },
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `warehouse_analytics.${isCsv ? 'csv' : 'json'}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

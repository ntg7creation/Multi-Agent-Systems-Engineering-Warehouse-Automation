const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:5000/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error ?? `Request failed: ${response.status}`)
  }
  return data
}

export function getState() {
  return request('/state')
}

export function getScenarios() {
  return request('/scenarios')
}

export function tick(steps = 1) {
  return request('/tick', {
    method: 'POST',
    body: JSON.stringify({ steps }),
  })
}

export function runSteps(steps = 10) {
  return request('/run', {
    method: 'POST',
    body: JSON.stringify({ steps }),
  })
}

export function resetSimulation({ scenarioId = 'default', seed } = {}) {
  return request('/reset', {
    method: 'POST',
    body: JSON.stringify({ scenario_id: scenarioId, seed }),
  })
}

export function startAutorun({ delayMs = 600, maxTicks = null } = {}) {
  return request('/autorun/start', {
    method: 'POST',
    body: JSON.stringify({ delay_ms: delayMs, max_ticks: maxTicks }),
  })
}

export function stopAutorun() {
  return request('/autorun/stop', { method: 'POST' })
}

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

export const simulationClient = {
  state: () => request('/state'),
  board: () => request('/board'),
  tick: (steps = 1) =>
    request('/tick', {
      method: 'POST',
      body: JSON.stringify({ steps }),
    }),
  run: (steps = 10) =>
    request('/run', {
      method: 'POST',
      body: JSON.stringify({ steps }),
    }),
  reset: ({ scenarioId = 'default', seed } = {}) =>
    request('/reset', {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId, seed }),
    }),
}

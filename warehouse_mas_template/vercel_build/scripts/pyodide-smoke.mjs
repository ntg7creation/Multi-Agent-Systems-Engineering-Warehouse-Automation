import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { loadPyodide } from 'pyodide'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const pythonRoot = join(root, 'public', 'python', 'warehouse_simulation')
const manifest = JSON.parse(
  await readFile(join(pythonRoot, 'python-manifest.json'), 'utf-8'),
)
const require = createRequire(import.meta.url)
const pyodidePackage = dirname(require.resolve('pyodide/package.json'))

const pyodide = await loadPyodide({
  indexURL: `${pyodidePackage.replaceAll('\\', '/')}/`,
})

pyodide.FS.mkdirTree('/warehouse_simulation')
for (const filePath of manifest.files) {
  const target = `/warehouse_simulation/${filePath}`
  ensureDirectory(dirnamePosix(target))
  pyodide.FS.writeFile(target, await readFile(join(pythonRoot, ...filePath.split('/')), 'utf-8'))
}

pyodide.FS.chdir('/warehouse_simulation')
await pyodide.runPythonAsync(`
import sys
if "/warehouse_simulation" not in sys.path:
    sys.path.insert(0, "/warehouse_simulation")
import pyodide_bridge
`)

async function command(type, payload = {}) {
  pyodide.globals.set('__warehouse_command_json', JSON.stringify({ type, payload }))
  const resultJson = await pyodide.runPythonAsync(`
import json
import pyodide_bridge
json.dumps(pyodide_bridge.handle(json.loads(__warehouse_command_json)))
`)
  return JSON.parse(resultJson)
}

const scenarios = await command('LIST_SCENARIOS')
assert.ok(scenarios.scenarios.length >= 20, 'Expected copied scenarios to be listed')

let state = await command('RESET', { scenario_id: 'simple_one_agent_delivery', seed: 42 })
assert.equal(state.tick, 0)
assert.equal(state.scenario.scenario_id, 'simple_one_agent_delivery')
const startPosition = state.agents[0].position.join(',')

state = await command('STEP', { steps: 1 })
assert.equal(state.tick, 1)
assert.ok(Array.isArray(state.actions), 'Expected action log after one step')

state = await command('RUN', { steps: 8 })
assert.ok(state.tick >= 2, 'Expected run command to advance ticks')
const latestPosition = state.agents[0].position.join(',')
assert.notEqual(latestPosition, startPosition, 'Expected simple scenario agent to move')

const summary = await command('GET_ANALYTICS_SUMMARY')
assert.equal(summary.scenario.scenario_id, 'simple_one_agent_delivery')
assert.ok(summary.event_count > 0, 'Expected analytics events')

const csv = await command('EXPORT_ANALYTICS_CSV')
assert.ok(csv.includes('# events'), 'Expected CSV export content')

const exported = await command('EXPORT_ANALYTICS_JSON')
assert.ok(Array.isArray(exported.events), 'Expected JSON analytics export events')

state = await command('RESET', { scenario_id: 'ten_agents_twenty_tasks_stress', seed: 77 })
assert.equal(state.agents.length, 10)
state = await command('RUN', { steps: 5 })
assert.equal(state.tick, 5)
assert.ok(state.metrics.global.total_steps >= 5)

console.log(JSON.stringify({
  scenarios: scenarios.scenarios.length,
  simpleTick: summary.system.current_tick,
  stressTick: state.tick,
  stressAgents: state.agents.length,
  csvBytes: csv.length,
}))

function ensureDirectory(path) {
  if (!path || path === '/' || path === '.') return
  const parts = path.split('/').filter(Boolean)
  let current = ''
  for (const part of parts) {
    current += `/${part}`
    try {
      pyodide.FS.mkdir(current)
    } catch (error) {
      if (error?.errno !== 20 && !String(error).includes('File exists')) throw error
    }
  }
}

function dirnamePosix(path) {
  const index = path.lastIndexOf('/')
  return index <= 0 ? '/' : path.slice(0, index)
}

import { getSimulationAdapter } from '../../simulation/PyodideSimulationAdapter.js'

const adapter = getSimulationAdapter()

export const simulationClient = {
  state: () => adapter.getState(),
  board: () => adapter.getBoard(),
  scenarios: () => adapter.listScenarios(),
  tick: (steps = 1) => adapter.step(steps),
  run: (steps = 10) => adapter.run(steps),
  reset: ({ scenarioId = 'default', seed, config } = {}) =>
    adapter.reset({ scenarioId, seed, config }),
  start: ({ delayMs = 600, maxTicks = null } = {}) =>
    adapter.start({ delayMs, maxTicks }),
  pause: () => adapter.pause(),
  resume: ({ delayMs = 600, maxTicks = null } = {}) =>
    adapter.resume({ delayMs, maxTicks }),
}

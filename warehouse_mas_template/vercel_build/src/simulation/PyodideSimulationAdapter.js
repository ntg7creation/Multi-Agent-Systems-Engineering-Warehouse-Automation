import { COMMANDS } from './messages.js'
import { SimulationAdapter } from './SimulationAdapter.js'

const DEFAULT_STATUS = {
  phase: 'idle',
  message: 'Python runtime idle',
}

class PyodideSimulationAdapter extends SimulationAdapter {
  constructor() {
    super()
    this.worker = null
    this.pending = new Map()
    this.requestCounter = 0
    this.initialized = false
    this.initializing = null
    this.queue = Promise.resolve()
    this.status = DEFAULT_STATUS
    this.statusListeners = new Set()
    this.autorun = {
      active: false,
      delay_ms: 600,
      max_ticks: null,
      ticks_run: 0,
    }
    this.autorunTimer = null
    this.autorunStepInFlight = false
  }

  getStatus() {
    return this.status
  }

  subscribeStatus(listener) {
    this.statusListeners.add(listener)
    listener(this.status)
    return () => this.statusListeners.delete(listener)
  }

  setStatus(nextStatus) {
    this.status = {
      ...this.status,
      ...nextStatus,
    }
    this.statusListeners.forEach((listener) => listener(this.status))
  }

  async initialize() {
    if (this.initialized) return { ok: true }
    if (!this.initializing) {
      this.setStatus({ phase: 'loading', message: 'Downloading Python runtime' })
      this.initializing = this.enqueue({ type: COMMANDS.INITIALIZE })
        .then((result) => {
          this.initialized = true
          this.setStatus({ phase: 'ready', message: 'Python simulation ready' })
          return result
        })
        .catch((error) => {
          this.initializing = null
          this.setStatus({ phase: 'error', message: error.message })
          throw error
        })
    }
    return this.initializing
  }

  async listScenarios() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.LIST_SCENARIOS })
  }

  async loadScenario({ scenarioId = 'default', seed, config } = {}) {
    await this.initialize()
    this.pause()
    const state = await this.enqueue({
      type: COMMANDS.LOAD_SCENARIO,
      payload: { scenario_id: scenarioId, seed, config },
    })
    return this.withAutorun(state)
  }

  async getState() {
    await this.initialize()
    const state = await this.enqueue({ type: COMMANDS.GET_STATE })
    return this.withAutorun(state)
  }

  async getBoard() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_BOARD })
  }

  async getAgents() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_AGENTS })
  }

  async getTasks() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_TASKS })
  }

  async getItems() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_ITEMS })
  }

  async getMetrics() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_METRICS })
  }

  async getEvents(limit = null) {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_EVENTS, payload: { limit } })
  }

  async getReplay(limit = null) {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_REPLAY, payload: { limit } })
  }

  async step(steps = 1) {
    await this.initialize()
    const state = await this.enqueue({ type: COMMANDS.STEP, payload: { steps } })
    if (state?.is_complete) this.pause()
    return this.withAutorun(state)
  }

  async run(steps = 10) {
    await this.initialize()
    const state = await this.enqueue({ type: COMMANDS.RUN, payload: { steps } })
    if (state?.is_complete) this.pause()
    return this.withAutorun(state)
  }

  start({ delayMs = 600, maxTicks = null } = {}) {
    const delay = Math.max(50, Math.min(Number(delayMs) || 600, 10000))
    this.autorun = {
      active: true,
      delay_ms: delay,
      max_ticks: maxTicks,
      ticks_run: 0,
    }
    this.startAutorunTimer()
    return Promise.resolve(this.autorunStatus())
  }

  resume(options = {}) {
    return this.start(options)
  }

  pause() {
    this.autorun.active = false
    if (this.autorunTimer) {
      window.clearInterval(this.autorunTimer)
      this.autorunTimer = null
    }
    return Promise.resolve(this.autorunStatus())
  }

  async reset({ scenarioId = 'default', seed, config } = {}) {
    await this.initialize()
    this.pause()
    const state = await this.enqueue({
      type: COMMANDS.RESET,
      payload: { scenario_id: scenarioId, seed, config },
    })
    return this.withAutorun(state)
  }

  async setSpeed(delayMs = 600) {
    this.autorun.delay_ms = Math.max(50, Math.min(Number(delayMs) || 600, 10000))
    if (this.autorun.active) this.startAutorunTimer()
    return this.autorunStatus()
  }

  async setStrategy(strategy, options = {}) {
    await this.initialize()
    this.pause()
    const state = await this.enqueue({
      type: COMMANDS.SET_STRATEGY,
      payload: { strategy, ...options },
    })
    return this.withAutorun(state)
  }

  async getAnalytics() {
    const [summary, events, agents, replay] = await Promise.all([
      this.getAnalyticsSummary(),
      this.getAnalyticsEvents(250),
      this.getAnalyticsAgents(),
      this.getAnalyticsReplay(250),
    ])
    return { summary, events, agents, replay }
  }

  async getAnalyticsSummary() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_ANALYTICS_SUMMARY })
  }

  async getAnalyticsEvents(limit = 200) {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_ANALYTICS_EVENTS, payload: { limit } })
  }

  async getAnalyticsAgents() {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_ANALYTICS_AGENTS })
  }

  async getAnalyticsReplay(limit = 200) {
    await this.initialize()
    return this.enqueue({ type: COMMANDS.GET_ANALYTICS_REPLAY, payload: { limit } })
  }

  async exportAnalytics(format = 'json') {
    await this.initialize()
    if (format === 'csv') {
      return this.enqueue({ type: COMMANDS.EXPORT_ANALYTICS_CSV })
    }
    return this.enqueue({ type: COMMANDS.EXPORT_ANALYTICS_JSON })
  }

  dispose() {
    this.pause()
    this.pending.forEach(({ reject }) => reject(new Error('Simulation worker disposed.')))
    this.pending.clear()
    this.worker?.terminate()
    this.worker = null
    this.initialized = false
    this.initializing = null
    this.setStatus(DEFAULT_STATUS)
  }

  startAutorunTimer() {
    if (this.autorunTimer) window.clearInterval(this.autorunTimer)
    this.autorunTimer = window.setInterval(() => {
      this.runAutorunStep()
    }, this.autorun.delay_ms)
    this.runAutorunStep()
  }

  async runAutorunStep() {
    if (!this.autorun.active || this.autorunStepInFlight) return
    if (
      this.autorun.max_ticks !== null
      && this.autorun.max_ticks !== undefined
      && this.autorun.ticks_run >= Number(this.autorun.max_ticks)
    ) {
      this.pause()
      return
    }

    this.autorunStepInFlight = true
    try {
      const state = await this.step(1)
      this.autorun.ticks_run += 1
      if (state?.is_complete) this.pause()
    } catch (error) {
      this.pause()
      this.setStatus({ phase: 'error', message: error.message })
    } finally {
      this.autorunStepInFlight = false
    }
  }

  autorunStatus() {
    return {
      active: this.autorun.active,
      delay_ms: this.autorun.delay_ms,
      max_ticks: this.autorun.max_ticks,
    }
  }

  withAutorun(state) {
    if (!state || typeof state !== 'object' || state.tick === undefined) return state
    return {
      ...state,
      autorun: this.autorunStatus(),
    }
  }

  enqueue(command) {
    const request = this.queue.catch(() => {}).then(() => this.send(command))
    this.queue = request.catch(() => {})
    return request
  }

  ensureWorker() {
    if (this.worker) return
    this.worker = new Worker(new URL('./simulationWorker.js', import.meta.url))
    this.worker.onmessage = (event) => this.handleWorkerMessage(event.data)
    this.worker.onerror = (event) => {
      const error = new Error(event.message || 'Simulation worker failed.')
      this.pending.forEach(({ reject }) => reject(error))
      this.pending.clear()
      this.setStatus({ phase: 'error', message: error.message })
    }
  }

  send(command) {
    this.ensureWorker()
    const requestId = `sim-${Date.now()}-${this.requestCounter += 1}`
    return new Promise((resolve, reject) => {
      this.pending.set(requestId, { resolve, reject })
      this.worker.postMessage({ requestId, command })
    })
  }

  handleWorkerMessage(message) {
    if (message?.type === 'STATUS') {
      this.setStatus(message.status)
      return
    }
    const pending = this.pending.get(message?.requestId)
    if (!pending) return
    this.pending.delete(message.requestId)
    if (message.success) {
      pending.resolve(message.data)
    } else {
      const error = new Error(message.error?.message || 'Simulation command failed.')
      error.details = message.error
      pending.reject(error)
    }
  }
}

const adapter = new PyodideSimulationAdapter()

export function getSimulationAdapter() {
  return adapter
}

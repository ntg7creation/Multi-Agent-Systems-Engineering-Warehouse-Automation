const port = process.argv[2] || '9224'
const route = process.argv[3] || '/2d'

const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
const page = pages.find((entry) => entry.type === 'page' && entry.url.includes(route))
if (!page) {
  throw new Error(`No Chrome page found for ${route}`)
}

const ws = new WebSocket(page.webSocketDebuggerUrl)
const pending = new Map()
let id = 0

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message)
    pending.delete(message.id)
  }
}

await new Promise((resolve, reject) => {
  ws.onopen = resolve
  ws.onerror = reject
})

function send(method, params = {}) {
  return new Promise((resolve) => {
    const message = { id: ++id, method, params }
    pending.set(message.id, resolve)
    ws.send(JSON.stringify(message))
  })
}

await send('Runtime.enable')

const expression = `(() => {
  const text = document.body.innerText || '';
  return {
    status: document.querySelector('.runtime-pill')?.textContent || '',
    error: document.querySelector('.error')?.textContent || '',
    scenarioOptions: document.querySelectorAll('select option').length,
    boardCells: document.querySelectorAll('.cell').length,
    agentsVisible: text.includes('agent_'),
    tickText: text.match(/Tick\\s+[-0-9]+/)?.[0] || '',
    body: text.slice(0, 1500),
  };
})()`

let latest = null
for (let attempt = 0; attempt < 90; attempt += 1) {
  const result = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  latest = result.result.result.value
  if (
    latest.status === 'Python simulation ready'
    && latest.scenarioOptions > 0
    && latest.boardCells > 0
    && latest.agentsVisible
  ) {
    console.log(JSON.stringify({ attempt, ok: true, ...latest }, null, 2))
    ws.close()
    process.exit(0)
  }
  if (latest.error) break
  await new Promise((resolve) => setTimeout(resolve, 1000))
}

console.log(JSON.stringify({ ok: false, ...latest }, null, 2))
ws.close()
process.exit(1)

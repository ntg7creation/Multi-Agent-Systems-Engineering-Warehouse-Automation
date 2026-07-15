const PYTHON_ROOT = '/python/warehouse_simulation'
const PYTHON_FS_ROOT = '/warehouse_simulation'

let pyodide = null
let pyodideReady = null

self.onmessage = async (event) => {
  const { requestId, command } = event.data
  try {
    const data = await execute(command)
    self.postMessage({ requestId, success: true, data })
  } catch (error) {
    self.postMessage({
      requestId,
      success: false,
      error: {
        message: error?.message || String(error),
        type: error?.name,
        traceback: error?.stack,
      },
    })
  }
}

async function execute(command) {
  await ensurePyodide()
  pyodide.globals.set('__warehouse_command_json', JSON.stringify(command ?? {}))
  const resultJson = await pyodide.runPythonAsync(`
import json
import pyodide_bridge
json.dumps(pyodide_bridge.handle(json.loads(__warehouse_command_json)))
`)
  return JSON.parse(resultJson)
}

async function ensurePyodide() {
  if (!pyodideReady) {
    pyodideReady = initializePyodide()
  }
  return pyodideReady
}

async function initializePyodide() {
  postStatus('loading', 'Downloading Python runtime')
  self.importScripts('/pyodide/pyodide.js')
  pyodide = await self.loadPyodide({ indexURL: '/pyodide/' })

  postStatus('loading', 'Loading simulation modules')
  await writePythonFiles()
  pyodide.FS.chdir(PYTHON_FS_ROOT)
  await pyodide.runPythonAsync(`
import sys
if "${PYTHON_FS_ROOT}" not in sys.path:
    sys.path.insert(0, "${PYTHON_FS_ROOT}")
import pyodide_bridge
`)

  postStatus('ready', 'Python simulation ready')
}

async function writePythonFiles() {
  const manifestResponse = await fetch(`${PYTHON_ROOT}/python-manifest.json`)
  if (!manifestResponse.ok) {
    throw new Error(`Could not load Python manifest: ${manifestResponse.status}`)
  }
  const manifest = await manifestResponse.json()
  pyodide.FS.mkdirTree(PYTHON_FS_ROOT)

  for (const filePath of manifest.files) {
    const response = await fetch(`${PYTHON_ROOT}/${encodePath(filePath)}`)
    if (!response.ok) {
      throw new Error(`Could not load Python file ${filePath}: ${response.status}`)
    }
    const content = await response.text()
    const targetPath = `${PYTHON_FS_ROOT}/${filePath}`
    ensureDirectory(dirname(targetPath))
    pyodide.FS.writeFile(targetPath, content)
  }
}

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

function dirname(path) {
  const index = path.lastIndexOf('/')
  return index <= 0 ? '/' : path.slice(0, index)
}

function encodePath(path) {
  return path.split('/').map(encodeURIComponent).join('/')
}

function postStatus(phase, message) {
  self.postMessage({
    type: 'STATUS',
    status: { phase, message },
  })
}

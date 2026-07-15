import { readdir } from 'node:fs/promises'
import { extname, join } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../src/', import.meta.url))
const extensions = new Set(['.js', '.mjs'])

async function* walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      yield* walk(path)
    } else if (extensions.has(extname(entry.name))) {
      yield path
    }
  }
}

function check(path) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['--check', path], { stdio: 'inherit' })
    child.on('exit', (code) => {
      if (code === 0) resolve()
      else reject(new Error(`Syntax check failed for ${path}`))
    })
  })
}

for await (const file of walk(root)) {
  await check(file)
}

console.log('JavaScript syntax check passed.')

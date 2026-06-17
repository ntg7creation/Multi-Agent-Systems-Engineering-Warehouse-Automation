import { CELL_SIZE } from './constants'

// Converts backend grid coordinates into centered Three.js world coordinates.
// Backend cells use (x, y); Three.js uses (x, y-up, z), so grid y maps to z.
export function gridToWorld(position, board, cellSize = CELL_SIZE, y = 0) {
  if (!position || !board) return [0, y, 0]
  const [gridX, gridY] = position
  const width = board.width ?? 1
  const height = board.height ?? 1
  const worldX = (gridX - (width - 1) / 2) * cellSize
  const worldZ = (gridY - (height - 1) / 2) * cellSize
  return [worldX, y, worldZ]
}

export function gridDirectionToYaw(direction) {
  if (direction === 'up') return Math.PI
  if (direction === 'down') return 0
  if (direction === 'left') return -Math.PI / 2
  if (direction === 'right') return Math.PI / 2
  return null
}

export function movementYaw(source, target) {
  if (!source || !target) return null
  const dx = target[0] - source[0]
  const dz = target[1] - source[1]
  if (dx === 0 && dz === 0) return null
  return Math.atan2(dx, dz)
}

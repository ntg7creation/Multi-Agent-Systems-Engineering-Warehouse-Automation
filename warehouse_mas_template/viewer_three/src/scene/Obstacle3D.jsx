import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function Obstacle3D({ cell, board, dimmed = false }) {
  const [x, , z] = gridToWorld(cell.position, board)

  return (
    <mesh position={[x, CELL_SIZE * 0.38, z]} castShadow receiveShadow>
      <boxGeometry args={[CELL_SIZE * 0.86, CELL_SIZE * 0.76, CELL_SIZE * 0.86]} />
      <meshStandardMaterial
        color="#5e574f"
        roughness={0.82}
        transparent={dimmed}
        opacity={dimmed ? 0.2 : 1}
      />
    </mesh>
  )
}

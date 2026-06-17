import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function Item3D({ item, board, dimmed = false }) {
  if (!item.position || item.state === 'delivered' || item.state === 'carried') return null
  const [x, , z] = gridToWorld(item.position, board)

  return (
    <group position={[x, CELL_SIZE * 0.18, z]}>
      <mesh castShadow>
        <boxGeometry args={[CELL_SIZE * 0.34, CELL_SIZE * 0.34, CELL_SIZE * 0.34]} />
        <meshStandardMaterial
          color="#facc15"
          roughness={0.55}
          transparent={dimmed}
          opacity={dimmed ? 0.24 : 1}
        />
      </mesh>
    </group>
  )
}

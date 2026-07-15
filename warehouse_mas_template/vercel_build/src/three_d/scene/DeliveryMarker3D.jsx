import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function DeliveryMarker3D({ cell, board, dimmed = false }) {
  const [x, , z] = gridToWorld(cell.position, board)

  return (
    <group position={[x, 0.05, z]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[CELL_SIZE * 0.34, 32]} />
        <meshStandardMaterial
          color="#fb923c"
          emissive="#7c2d12"
          emissiveIntensity={0.14}
          transparent={dimmed}
          opacity={dimmed ? 0.2 : 1}
        />
      </mesh>
      <mesh position={[0, 0.16, 0]}>
        <coneGeometry args={[CELL_SIZE * 0.18, CELL_SIZE * 0.32, 4]} />
        <meshStandardMaterial color="#fed7aa" transparent={dimmed} opacity={dimmed ? 0.22 : 1} />
      </mesh>
    </group>
  )
}

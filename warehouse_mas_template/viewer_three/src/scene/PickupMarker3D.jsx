import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function PickupMarker3D({ cell, board, dimmed = false }) {
  const [x, , z] = gridToWorld(cell.position, board)

  return (
    <group position={[x, 0.04, z]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[CELL_SIZE * 0.24, CELL_SIZE * 0.37, 32]} />
        <meshStandardMaterial
          color="#34d399"
          emissive="#0f5138"
          emissiveIntensity={0.18}
          transparent={dimmed}
          opacity={dimmed ? 0.22 : 1}
        />
      </mesh>
      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[CELL_SIZE * 0.22, CELL_SIZE * 0.18, CELL_SIZE * 0.22]} />
        <meshStandardMaterial color="#34d399" transparent={dimmed} opacity={dimmed ? 0.22 : 1} />
      </mesh>
    </group>
  )
}

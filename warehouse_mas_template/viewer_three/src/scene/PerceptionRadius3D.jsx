import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function PerceptionRadius3D({ agent, board }) {
  const radiusCells = agent?.perception?.radius ?? agent?.perception_radius
  if (!agent || !radiusCells) return null

  const radius = Math.max(CELL_SIZE * 0.5, radiusCells * CELL_SIZE)
  const [x, , z] = gridToWorld(agent.position, board, CELL_SIZE, 0.04)

  return (
    <group position={[x, 0.04, z]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius - 0.035, radius + 0.035, 96]} />
        <meshBasicMaterial color="#38bdf8" transparent opacity={0.95} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[radius, 96]} />
        <meshBasicMaterial color="#38bdf8" transparent opacity={0.06} depthWrite={false} />
      </mesh>
    </group>
  )
}

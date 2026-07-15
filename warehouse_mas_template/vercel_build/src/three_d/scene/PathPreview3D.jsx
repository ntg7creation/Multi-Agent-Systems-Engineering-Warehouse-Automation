import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function PathPreview3D({ path = [], board }) {
  if (!path.length) return null

  return (
    <group>
      {path.map((position, index) => {
        const [x, , z] = gridToWorld(position, board, CELL_SIZE, 0.025)
        return (
          <mesh
            key={`${position[0]}-${position[1]}-${index}`}
            position={[x, 0.025, z]}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <circleGeometry args={[CELL_SIZE * 0.16, 20]} />
            <meshStandardMaterial
              color={index === 0 ? '#f8fafc' : '#93c5fd'}
              transparent
              opacity={index === 0 ? 0.8 : 0.58}
            />
          </mesh>
        )
      })}
    </group>
  )
}

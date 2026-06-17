import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

function cellColor(cellType) {
  if (cellType === 'pickup') return '#63b98d'
  if (cellType === 'dropoff') return '#d99258'
  if (cellType === 'blocked') return '#6b6258'
  return '#b9b4aa'
}

export function GridFloor3D({ board, onFloorClick, isDimmedCell = () => false }) {
  const rows = board?.rows ?? []

  return (
    <group>
      {rows.flatMap((row) =>
        row.map((cell) => {
          const [x, y, z] = gridToWorld(cell.position, board, CELL_SIZE, -0.01)
          const dimmed = isDimmedCell(cell.position)
          return (
            <mesh
              key={`${cell.position[0]}-${cell.position[1]}`}
              position={[x, y, z]}
              rotation={[-Math.PI / 2, 0, 0]}
              receiveShadow
              onClick={onFloorClick}
            >
              <planeGeometry args={[CELL_SIZE * 0.94, CELL_SIZE * 0.94]} />
              <meshStandardMaterial
                color={cellColor(cell.cell_type)}
                roughness={0.86}
                metalness={0.02}
                transparent={dimmed}
                opacity={dimmed ? 0.16 : 1}
              />
            </mesh>
          )
        }),
      )}
    </group>
  )
}

import { Canvas } from '@react-three/fiber'
import { GridFloor3D } from './GridFloor3D'
import { Agent3D } from './Agent3D'
import { CameraControls } from './CameraControls'
import { DeliveryMarker3D } from './DeliveryMarker3D'
import { Item3D } from './Item3D'
import { Obstacle3D } from './Obstacle3D'
import { PathPreview3D } from './PathPreview3D'
import { PerceptionRadius3D } from './PerceptionRadius3D'
import { PickupMarker3D } from './PickupMarker3D'
import { useSimulationStore } from '../state/useSimulationStore'

function positionKey(position) {
  return position ? `${position[0]},${position[1]}` : ''
}

function SceneContent() {
  const state = useSimulationStore((store) => store.state)
  const selectedAgentId = useSimulationStore((store) => store.selectedAgentId)
  const viewMode = useSimulationStore((store) => store.viewMode)
  const cameraFollowSelected = useSimulationStore((store) => store.cameraFollowSelected)
  const bufferDelayMs = useSimulationStore((store) => store.bufferDelayMs)
  const selectAgent = useSimulationStore((store) => store.selectAgent)

  const board = state?.board
  const agents = state?.agents ?? []
  const items = state?.items ?? []
  const rows = board?.rows ?? []
  const selectedAgent = agents.find((agent) => agent.agent_id === selectedAgentId) ?? null
  const blockedCells = rows.flatMap((row) => row.filter((cell) => cell.cell_type === 'blocked'))
  const pickupCells = rows.flatMap((row) => row.filter((cell) => cell.cell_type === 'pickup'))
  const deliveryCells = rows.flatMap((row) => row.filter((cell) => cell.cell_type === 'dropoff'))
  const agentViewActive = viewMode === 'agent' && selectedAgent
  const visibleCells = new Set()
  selectedAgent?.perception?.visible_cells?.forEach((cell) => {
    visibleCells.add(positionKey(cell.position))
  })
  if (selectedAgent?.position) visibleCells.add(positionKey(selectedAgent.position))
  const isVisiblePosition = (position) => !agentViewActive || visibleCells.has(positionKey(position))
  const isDimmedPosition = (position) => agentViewActive && !isVisiblePosition(position)

  return (
    <>
      <color attach="background" args={['#d9d6cf']} />
      <fog attach="fog" args={['#d9d6cf', 20, 58]} />
      <ambientLight intensity={0.92} />
      <directionalLight
        position={[6, 11, 7]}
        intensity={1.35}
        color="#fff4df"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
      />
      <hemisphereLight args={['#f8fafc', '#8a8174', 0.5]} />

      <CameraControls
        board={board}
        selectedAgent={selectedAgent}
        followSelected={cameraFollowSelected}
      />

      {board && (
        <GridFloor3D
          board={board}
          onFloorClick={() => selectAgent(null)}
          isDimmedCell={isDimmedPosition}
        />
      )}
      {blockedCells.map((cell) => (
        <Obstacle3D
          key={`blocked-${cell.position.join('-')}`}
          cell={cell}
          board={board}
          dimmed={isDimmedPosition(cell.position)}
        />
      ))}
      {pickupCells.map((cell) => (
        <PickupMarker3D
          key={`pickup-${cell.position.join('-')}`}
          cell={cell}
          board={board}
          dimmed={isDimmedPosition(cell.position)}
        />
      ))}
      {deliveryCells.map((cell) => (
        <DeliveryMarker3D
          key={`dropoff-${cell.position.join('-')}`}
          cell={cell}
          board={board}
          dimmed={isDimmedPosition(cell.position)}
        />
      ))}
      {items.map((item) => (
        <Item3D
          key={item.item_id}
          item={item}
          board={board}
          dimmed={isDimmedPosition(item.position)}
        />
      ))}
      {agentViewActive && <PerceptionRadius3D agent={selectedAgent} board={board} />}
      {selectedAgent && (
        <PathPreview3D path={selectedAgent.planned_path ?? []} board={board} />
      )}
      {agents.map((agent) => (
        <Agent3D
          key={`${state?.run_id ?? 'run'}-${agent.agent_id}`}
          agent={agent}
          board={board}
          selected={agent.agent_id === selectedAgentId}
          dimmed={agent.agent_id !== selectedAgentId && isDimmedPosition(agent.position)}
          movementDurationMs={bufferDelayMs}
          onSelect={selectAgent}
        />
      ))}
    </>
  )
}

export function WarehouseScene() {
  return (
    <section className="scene-panel">
      <Canvas shadows dpr={[1, 2]} onPointerMissed={() => useSimulationStore.getState().selectAgent(null)}>
        <SceneContent />
      </Canvas>
    </section>
  )
}

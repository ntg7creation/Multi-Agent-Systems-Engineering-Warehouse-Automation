import { useEffect, useMemo, useRef } from 'react'
import { OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { useThree } from '@react-three/fiber'
import { CELL_SIZE } from './constants'
import { gridToWorld } from './gridToWorld'

export function CameraControls({ board, selectedAgent, followSelected }) {
  const controlsRef = useRef()
  const { camera } = useThree()
  const maxDimension = Math.max(board?.width ?? 8, board?.height ?? 8)

  const initialPosition = useMemo(() => {
    const distance = Math.max(8, maxDimension * CELL_SIZE * 1.1)
    return [distance * 0.72, distance * 0.72, distance * 0.82]
  }, [maxDimension])

  useEffect(() => {
    camera.position.set(...initialPosition)
    camera.lookAt(0, 0, 0)
  }, [camera, initialPosition])

  useEffect(() => {
    if (!followSelected || !selectedAgent || !controlsRef.current) return
    const [x, , z] = gridToWorld(selectedAgent.position, board, CELL_SIZE, 0)
    controlsRef.current.target.set(x, 0.3, z)
    controlsRef.current.update()
  }, [board, followSelected, selectedAgent])

  return (
    <>
      <PerspectiveCamera makeDefault position={initialPosition} fov={45} near={0.1} far={1000} />
      <OrbitControls
        ref={controlsRef}
        enableDamping
        dampingFactor={0.08}
        maxPolarAngle={Math.PI * 0.48}
        minDistance={3}
        maxDistance={60}
      />
    </>
  )
}

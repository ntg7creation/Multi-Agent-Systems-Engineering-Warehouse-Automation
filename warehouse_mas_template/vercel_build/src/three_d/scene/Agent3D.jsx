import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'
import { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { useSimulationStore } from '../state/useSimulationStore'
import {
  CARRY_BOX_ANCHOR_POSITION,
  CELL_SIZE,
  MODEL_ASSETS,
} from './constants'
import {
  AgentAnimationController,
  buildAgentVisualSchedule,
  inferAgentYaw,
} from './agentAnimationController'

const fbxLoader = new FBXLoader()
const assetCache = new Map()

function normalizeAssetCandidates(paths) {
  return Array.isArray(paths) ? paths : [paths]
}

function loadFbxPath(path) {
  return new Promise((resolve, reject) => {
    fbxLoader.load(path, resolve, undefined, reject)
  })
}

function loadFbxOnce(paths, label) {
  const candidates = normalizeAssetCandidates(paths)
  const cacheKey = candidates.join('|')
  if (!assetCache.has(cacheKey)) {
    assetCache.set(
      cacheKey,
      (async () => {
        let lastError = null
        for (const path of candidates) {
          try {
            const object = await loadFbxPath(path)
            return object
          } catch (error) {
            lastError = error
          }
        }
        console.warn(
          `Could not load ${label}. Tried: ${candidates.join(', ')}. Make sure the FBX file exists in viewer_three/public.`,
          lastError,
        )
        throw lastError
      })(),
    )
  }
  return assetCache.get(cacheKey)
}

function useFbxAsset(paths, label) {
  const [asset, setAsset] = useState(null)
  const [failed, setFailed] = useState(false)
  const cacheKey = normalizeAssetCandidates(paths).join('|')

  useEffect(() => {
    let alive = true
    setFailed(false)
    loadFbxOnce(paths, label)
      .then((object) => {
        if (alive) setAsset(object)
      })
      .catch(() => {
        if (alive) setFailed(true)
      })
    return () => {
      alive = false
    }
  }, [cacheKey, label, paths])

  return { asset, failed }
}

function trackNamesMatch(character, clip) {
  const nodeNames = new Set()
  character.traverse((node) => {
    if (node.name) nodeNames.add(node.name)
  })
  return clip.tracks.some((track) => nodeNames.has(track.name.split('.')[0]))
}

function firstClip(asset) {
  return asset?.animations?.[0] ?? null
}

export function Agent3D({
  agent,
  board,
  selected,
  dimmed = false,
  movementDurationMs = 600,
  runId,
  simulationTick,
  playbackActive = false,
  isComplete = false,
  onSelect,
  onVisualDebug,
}) {
  const groupRef = useRef()
  const controllerRef = useRef(null)
  const previousAgentRef = useRef(null)
  const previousRunIdRef = useRef(null)
  const previousTickRef = useRef(null)
  const scheduledByPlaybackRef = useRef(false)
  const lastVisualDebugPushRef = useRef(0)
  const lastVisualDebugJsonRef = useRef('')
  const carryBoxOffset = useSimulationStore((store) => store.carryBoxOffset)
  const { asset: characterAsset, failed: characterFailed } = useFbxAsset(
    MODEL_ASSETS.character,
    'character',
  )
  const { asset: normalWalkingAsset } = useFbxAsset(MODEL_ASSETS.normalWalking, 'normal walking animation')
  const { asset: carryWalkingAsset } = useFbxAsset(MODEL_ASSETS.carryWalking, 'carry walking animation')
  const { asset: idleAsset } = useFbxAsset(MODEL_ASSETS.idle, 'idle animation')
  const { asset: carryIdleAsset } = useFbxAsset(MODEL_ASSETS.carryIdle, 'carry idle animation')
  const { asset: pickupAsset } = useFbxAsset(MODEL_ASSETS.pickup, 'pickup/place animation')
  const { asset: turnLeftAsset } = useFbxAsset(MODEL_ASSETS.turnLeft, 'left-turn animation')
  const currentActionType = agent.previous_action_result?.action?.type
  const isPickupOrPlaceAction = currentActionType === 'pickup' || currentActionType === 'place'

  const character = useMemo(() => {
    if (!characterAsset) return null
    const instance = cloneSkeleton(characterAsset)
    instance.name = `${agent.agent_id}_model`
    instance.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true
        child.receiveShadow = true
        if (Array.isArray(child.material)) {
          child.material = child.material.map((material) => material.clone())
        } else if (child.material) {
          child.material = child.material.clone()
        }
      }
    })
    return instance
  }, [agent.agent_id, characterAsset])

  useLayoutEffect(() => {
    if (!groupRef.current || !board) return undefined
    const controller = new AgentAnimationController({
      group: groupRef.current,
      board,
      cellSize: CELL_SIZE,
      agentId: agent.agent_id,
    })
    controllerRef.current = controller
    controller.setCarrying(Boolean(agent.carrying_item_id))
    controller.resetPose({
      cell: agent.position,
      yaw: inferAgentYaw(agent),
      board,
    })
    previousAgentRef.current = agent
    previousRunIdRef.current = runId
    previousTickRef.current = simulationTick

    return () => {
      controller.dispose()
      if (controllerRef.current === controller) controllerRef.current = null
    }
  }, [agent.agent_id])

  useEffect(() => {
    if (!character) return
    character.traverse((child) => {
      if (!child.isMesh || !child.material) return
      const materials = Array.isArray(child.material) ? child.material : [child.material]
      materials.forEach((material) => {
        material.transparent = dimmed
        material.opacity = dimmed ? 0.28 : 1
        material.depthWrite = !dimmed
        material.needsUpdate = true
      })
    })
  }, [character, dimmed])

  useEffect(() => {
    controllerRef.current?.setDebugEnabled(selected)
    if (!selected) onVisualDebug?.(agent.agent_id, null)
  }, [agent.agent_id, onVisualDebug, selected])

  useEffect(() => {
    const controller = controllerRef.current
    const normalWalkClip = firstClip(normalWalkingAsset)
    const carryWalkClip = firstClip(carryWalkingAsset)
    const idleClip = firstClip(idleAsset)
    const carryIdleClip = firstClip(carryIdleAsset)
    const pickupClip = firstClip(pickupAsset)
    const turnLeftClip = firstClip(turnLeftAsset)

    if (!controller || !character || !normalWalkClip || !carryWalkClip || !idleClip || !carryIdleClip) return undefined

    if (!normalWalkClip || !carryWalkClip) {
      console.warn('No animations found in the walking FBX files.')
      return undefined
    }

    if (!trackNamesMatch(character, normalWalkClip)) {
      console.warn(
        `${agent.agent_id}: normal walking animation track names did not match the character skeleton. If this agent does not animate, check Mixamo skeleton compatibility and track names.`,
      )
    }
    if (!trackNamesMatch(character, carryWalkClip)) {
      console.warn(`${agent.agent_id}: carry walking animation track names did not match the character skeleton.`)
    }
    if (!trackNamesMatch(character, idleClip)) {
      console.warn(`${agent.agent_id}: idle animation track names did not match the character skeleton.`)
    }
    if (!trackNamesMatch(character, carryIdleClip)) {
      console.warn(`${agent.agent_id}: carry idle animation track names did not match the character skeleton.`)
    }
    if (pickupClip && !trackNamesMatch(character, pickupClip)) {
      console.warn(`${agent.agent_id}: pickup/place animation track names did not match the character skeleton.`)
    }
    if (turnLeftClip && !trackNamesMatch(character, turnLeftClip)) {
      console.warn(`${agent.agent_id}: left-turn animation track names did not match the character skeleton.`)
    }

    controller.configureAnimations({
      character,
      clips: {
        walk: normalWalkClip,
        carryWalk: carryWalkClip,
        idle: idleClip,
        carryIdle: carryIdleClip,
        pickup: pickupClip,
        turnLeft: turnLeftClip,
      },
    })

    return () => {
      controller.disposeAnimations()
    }
  }, [
    agent.agent_id,
    character,
    normalWalkingAsset,
    carryWalkingAsset,
    idleAsset,
    carryIdleAsset,
    pickupAsset,
    turnLeftAsset,
  ])

  useLayoutEffect(() => {
    const controller = controllerRef.current
    if (!controller || !board) return
    controller.setBoard(board)
    controller.setCarrying(Boolean(agent.carrying_item_id))

    const previousAgent = previousAgentRef.current
    const previousRunId = previousRunIdRef.current
    const previousTick = previousTickRef.current
    const runChanged = previousRunId != null && previousRunId !== runId
    const tickReset = previousTick != null && simulationTick < previousTick
    const tickChanged = previousTick !== simulationTick || previousRunId !== runId

    if (!previousAgent || runChanged || tickReset) {
      controller.resetPose({
        cell: agent.position,
        yaw: inferAgentYaw(agent, controller.getYaw()),
        board,
      })
      previousAgentRef.current = agent
      previousRunIdRef.current = runId
      previousTickRef.current = simulationTick
      scheduledByPlaybackRef.current = false
      return
    }

    if (!tickChanged) return

    const stepDuration = Math.max(0.08, movementDurationMs / 1000)
    const schedule = buildAgentVisualSchedule({
      agent,
      previousAgent,
      stepDuration,
      previousYaw: controller.getYaw(),
    })
    if (schedule.segments.length) {
      scheduledByPlaybackRef.current = playbackActive
      controller.setSchedule(schedule.segments, {
        board,
        fallbackCell: agent.position,
        fallbackYaw: inferAgentYaw(agent, controller.getYaw()),
        startTime: schedule.startTime,
      })
    } else {
      scheduledByPlaybackRef.current = false
      controller.resetPose({
        cell: agent.position,
        yaw: inferAgentYaw(agent, controller.getYaw()),
        board,
      })
    }

    previousAgentRef.current = agent
    previousRunIdRef.current = runId
    previousTickRef.current = simulationTick
  }, [agent, board, movementDurationMs, playbackActive, runId, simulationTick])

  useFrame((frameState, delta) => {
    const advance = !scheduledByPlaybackRef.current || playbackActive || isComplete
    const controller = controllerRef.current
    controller?.update(delta, { advance })
    if (!selected || !controller || !onVisualDebug) return
    const now = frameState.clock.elapsedTime
    if (now - lastVisualDebugPushRef.current < 0.08) return
    lastVisualDebugPushRef.current = now
    const debugState = controller.getDebugState()
    const debugJson = JSON.stringify(debugState)
    if (debugJson === lastVisualDebugJsonRef.current) return
    lastVisualDebugJsonRef.current = debugJson
    onVisualDebug(agent.agent_id, debugState)
  })

  return (
    <group
      ref={groupRef}
      onClick={(event) => {
        event.stopPropagation()
        onSelect(agent.agent_id)
      }}
    >
      {selected && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.035, 0]}>
          <ringGeometry args={[CELL_SIZE * 0.36, CELL_SIZE * 0.48, 32]} />
          <meshBasicMaterial color="#60a5fa" transparent opacity={0.9} />
        </mesh>
      )}

      {character ? (
        <primitive object={character} scale={0.01} />
      ) : (
        <mesh position={[0, CELL_SIZE * 0.35, 0]} castShadow>
          <capsuleGeometry args={[CELL_SIZE * 0.18, CELL_SIZE * 0.48, 8, 16]} />
          <meshStandardMaterial
            color={characterFailed ? '#ef4444' : '#4f8cff'}
            transparent={dimmed}
            opacity={dimmed ? 0.28 : 1}
          />
        </mesh>
      )}

      {agent.carrying_item_id && (
        <group
          position={[
            CARRY_BOX_ANCHOR_POSITION.x,
            CARRY_BOX_ANCHOR_POSITION.y,
            CARRY_BOX_ANCHOR_POSITION.z,
          ]}
        >
          <mesh
            position={[carryBoxOffset.x, carryBoxOffset.y, carryBoxOffset.z]}
            castShadow
          >
            <boxGeometry args={[CELL_SIZE * 0.22, CELL_SIZE * 0.22, CELL_SIZE * 0.22]} />
            <meshStandardMaterial color="#facc15" transparent={dimmed} opacity={dimmed ? 0.3 : 1} />
          </mesh>
        </group>
      )}

      {!isPickupOrPlaceAction && (agent.mode === 'waiting' || agent.replanning_flag) && (
        <mesh position={[0, CELL_SIZE * 0.95, 0]}>
          <sphereGeometry args={[CELL_SIZE * 0.09, 16, 16]} />
          <meshStandardMaterial color={agent.replanning_flag ? '#f97316' : '#facc15'} />
        </mesh>
      )}
    </group>
  )
}

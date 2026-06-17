import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'
import { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { CELL_SIZE, MODEL_ASSETS } from './constants'
import { gridDirectionToYaw, gridToWorld, movementYaw } from './gridToWorld'

const fbxLoader = new FBXLoader()
const assetCache = new Map()

function loadFbxOnce(path, label) {
  if (!assetCache.has(path)) {
    assetCache.set(
      path,
      new Promise((resolve, reject) => {
        fbxLoader.load(
          path,
          (object) => {
            console.log(`${label} loaded:`, object)
            resolve(object)
          },
          undefined,
          (error) => {
            console.error(`Error loading ${path}. Make sure ${path} exists in viewer_three/public.`, error)
            reject(error)
          },
        )
      }),
    )
  }
  return assetCache.get(path)
}

function useFbxAsset(path, label) {
  const [asset, setAsset] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    loadFbxOnce(path, label)
      .then((object) => {
        if (alive) setAsset(object)
      })
      .catch(() => {
        if (alive) setFailed(true)
      })
    return () => {
      alive = false
    }
  }, [path, label])

  return { asset, failed }
}

function trackNamesMatch(character, clip) {
  const nodeNames = new Set()
  character.traverse((node) => {
    if (node.name) nodeNames.add(node.name)
  })
  return clip.tracks.some((track) => nodeNames.has(track.name.split('.')[0]))
}

function agentYaw(agent) {
  const action = agent.intended_action
  const fromDirection = gridDirectionToYaw(action?.direction)
  if (fromDirection !== null) return fromDirection
  const previous = agent.previous_action_result
  return movementYaw(previous?.source_position, previous?.target_position) ?? 0
}

function vectorFromArray(position) {
  return new THREE.Vector3(position[0], position[1], position[2])
}

export function Agent3D({
  agent,
  board,
  selected,
  dimmed = false,
  movementDurationMs = 600,
  onSelect,
}) {
  const groupRef = useRef()
  const mixerRef = useRef(null)
  const transitionRef = useRef(null)
  const targetKeyRef = useRef('')
  const { asset: characterAsset, failed: characterFailed } = useFbxAsset(
    MODEL_ASSETS.character,
    'character',
  )
  const { asset: walkingAsset } = useFbxAsset(MODEL_ASSETS.walking, 'animation')

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
    mixerRef.current?.stopAllAction()
    mixerRef.current = null

    if (!character || !walkingAsset) return undefined
    const clip = walkingAsset.animations?.[0]
    if (!clip) {
      console.warn('No animations found in /models/walking.fbx.')
      return undefined
    }

    console.log('animation clip name:', clip.name || '(unnamed clip)')
    if (!trackNamesMatch(character, clip)) {
      console.warn(
        `${agent.agent_id}: animation track names did not match the character skeleton. If this agent does not animate, check Mixamo skeleton compatibility and track names.`,
      )
    }

    const mixer = new THREE.AnimationMixer(character)
    const action = mixer.clipAction(clip)
    action.reset()
    action.play()
    mixerRef.current = mixer

    return () => {
      mixer.stopAllAction()
      mixer.uncacheRoot(character)
    }
  }, [agent.agent_id, character, walkingAsset])

  const targetWorldPosition = useMemo(
    () => gridToWorld(agent.position, board, CELL_SIZE, 0),
    [agent.position, board],
  )
  const targetKey = `${targetWorldPosition[0]},${targetWorldPosition[1]},${targetWorldPosition[2]}`

  useLayoutEffect(() => {
    if (!groupRef.current) return
    const target = vectorFromArray(targetWorldPosition)

    if (!targetKeyRef.current) {
      groupRef.current.position.copy(target)
      targetKeyRef.current = targetKey
      return
    }

    if (targetKeyRef.current === targetKey) return

    const from = groupRef.current.position.clone()
    transitionRef.current = {
      from,
      to: target,
      elapsed: 0,
      duration: Math.max(0.08, movementDurationMs / 1000),
    }
    targetKeyRef.current = targetKey
  }, [movementDurationMs, targetKey, targetWorldPosition])

  useFrame((_, delta) => {
    mixerRef.current?.update(delta)

    const transition = transitionRef.current
    if (!transition || !groupRef.current) return

    transition.elapsed += delta
    const progress = Math.min(transition.elapsed / transition.duration, 1)
    groupRef.current.position.lerpVectors(transition.from, transition.to, progress)

    if (progress >= 1) {
      groupRef.current.position.copy(transition.to)
      transitionRef.current = null
    }
  })

  const yaw = agentYaw(agent)

  return (
    <group
      ref={groupRef}
      rotation={[0, yaw, 0]}
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
        <mesh position={[0, CELL_SIZE * 0.78, 0]} castShadow>
          <boxGeometry args={[CELL_SIZE * 0.22, CELL_SIZE * 0.22, CELL_SIZE * 0.22]} />
          <meshStandardMaterial color="#facc15" transparent={dimmed} opacity={dimmed ? 0.3 : 1} />
        </mesh>
      )}

      {(agent.mode === 'waiting' || agent.replanning_flag) && (
        <mesh position={[0, CELL_SIZE * 0.95, 0]}>
          <sphereGeometry args={[CELL_SIZE * 0.09, 16, 16]} />
          <meshStandardMaterial color={agent.replanning_flag ? '#f97316' : '#facc15'} />
        </mesh>
      )}
    </group>
  )
}

import * as THREE from 'three'
import { CELL_SIZE, TURN_PORTION_OF_STEP } from './constants.js'
import { gridToWorld, movementYaw } from './gridToWorld.js'

const TURN_EPSILON = 0.001
const FADE_SECONDS = 0.08
const MIN_SEGMENT_SECONDS = 0.001
const VISUAL_STATES = {
  walk: 'WALK',
  turnLeft: 'TURN_LEFT',
  pickup: 'PICKUP',
  place: 'PLACE',
  idle: 'IDLE',
}
const LEFT_OF_DIRECTION = {
  forward: 'left',
  left: 'back',
  back: 'right',
  right: 'forward',
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function sameCell(a, b) {
  return Boolean(a && b && a[0] === b[0] && a[1] === b[1])
}

function normalizeYaw(yaw) {
  let normalized = yaw
  while (normalized <= -Math.PI) normalized += Math.PI * 2
  while (normalized > Math.PI) normalized -= Math.PI * 2
  return normalized
}

function signedYawDelta(fromYaw, toYaw) {
  return normalizeYaw(toYaw - fromYaw)
}

function successfulActionResult(agent) {
  const result = agent?.previous_action_result
  if (!result || result.success === false) return null
  return result
}

function successfulMoveResult(agent) {
  const result = successfulActionResult(agent)
  if (result?.action?.type !== 'move') return null
  if (!result.source_position || !result.target_position) return null
  if (sameCell(result.source_position, result.target_position)) return null
  return result
}

function movementDirection(source, target) {
  if (!source || !target) return null
  const dx = target[0] - source[0]
  const dy = target[1] - source[1]
  if (dx === 0 && dy === 1) return 'forward'
  if (dx === 0 && dy === -1) return 'back'
  if (dx === -1 && dy === 0) return 'left'
  if (dx === 1 && dy === 0) return 'right'
  return null
}

function isLeftTurnDirection(incomingDirection, outgoingDirection) {
  return Boolean(
    incomingDirection
    && outgoingDirection
    && LEFT_OF_DIRECTION[incomingDirection] === outgoingDirection,
  )
}

function directionFromYaw(yaw) {
  if (Math.abs(signedYawDelta(yaw, 0)) < TURN_EPSILON) return 'forward'
  if (Math.abs(signedYawDelta(yaw, Math.PI / 2)) < TURN_EPSILON) return 'right'
  if (Math.abs(signedYawDelta(yaw, -Math.PI / 2)) < TURN_EPSILON) return 'left'
  if (Math.abs(Math.abs(normalizeYaw(yaw)) - Math.PI) < TURN_EPSILON) return 'back'
  return null
}

function turnKindFromYawDelta(delta) {
  if (Math.abs(delta) < TURN_EPSILON) return 'straight'
  if (Math.abs(delta + Math.PI / 2) < TURN_EPSILON) return 'left'
  if (Math.abs(delta - Math.PI / 2) < TURN_EPSILON) return 'right'
  if (Math.abs(Math.abs(delta) - Math.PI) < TURN_EPSILON) return 'aboutFace'
  return 'headingChange'
}

function buildTurnDetection({ previousMove, currentMove, incomingYaw, outgoingYaw }) {
  const previousCell = previousMove?.source_position ?? null
  const waypointCell = previousMove?.target_position ?? currentMove?.source_position ?? null
  const nextCell = currentMove?.target_position ?? null
  const incomingDirection = movementDirection(previousCell, waypointCell) ?? directionFromYaw(incomingYaw)
  const outgoingDirection = movementDirection(waypointCell, nextCell)
  const turnDelta = signedYawDelta(incomingYaw, outgoingYaw)
  return {
    previousCell,
    waypointCell,
    nextCell,
    incomingDirection,
    outgoingDirection,
    turnKind: turnKindFromYawDelta(turnDelta),
    turnDelta,
    detectedTurn: Math.abs(turnDelta) > TURN_EPSILON,
    detectedLeftTurn: isLeftTurnDirection(incomingDirection, outgoingDirection),
  }
}

function stationaryActionCell(agent, result) {
  return result?.source_position ?? agent?.position ?? result?.target_position ?? [0, 0]
}

function stationaryActionYaw(result, fallbackYaw) {
  return movementYaw(result?.source_position, result?.target_position) ?? fallbackYaw
}

function clipDuration(clip) {
  return Math.max(MIN_SEGMENT_SECONDS, clip?.duration ?? MIN_SEGMENT_SECONDS)
}

function shouldPinRootPosition(trackName) {
  if (!trackName.endsWith('.position')) return false
  const nodeName = trackName.split('.')[0].toLowerCase()
  return (
    nodeName.includes('hips')
    || nodeName.includes('root')
    || nodeName.includes('armature')
    || nodeName.includes('pelvis')
  )
}

function pinRootPositionTrack(track) {
  const values = track.values.slice()
  if (values.length < 3) return track.clone()
  const x = values[0]
  const y = values[1]
  const z = values[2]
  for (let index = 0; index < values.length; index += 3) {
    values[index] = x
    values[index + 1] = y
    values[index + 2] = z
  }
  return new THREE.VectorKeyframeTrack(track.name, track.times.slice(), values)
}

function prepareClip(clip, name) {
  if (!clip) return null
  const tracks = clip.tracks.map((track) => (
    shouldPinRootPosition(track.name) ? pinRootPositionTrack(track) : track.clone()
  ))
  return new THREE.AnimationClip(`${name}-${clip.name || 'clip'}`, clip.duration, tracks)
}

function segmentDuration(segment) {
  return Math.max(MIN_SEGMENT_SECONDS, segment.endTime - segment.startTime)
}

function segmentProgress(segment, time) {
  return clamp01((time - segment.startTime) / segmentDuration(segment))
}

function roundTime(value) {
  return Number.isFinite(value) ? Number(value.toFixed(4)) : value
}

function walkSegment({ from, to, heading, startTime, endTime, turnDetection = null }) {
  return {
    type: 'walk',
    from,
    to,
    fromHeading: heading,
    toHeading: heading,
    heading,
    startTime,
    endTime,
    turnDetection,
    carrying: false,
  }
}

function turnLeftSegment({ cell, fromHeading, toHeading, startTime, endTime, turnDetection = null }) {
  return {
    type: 'turnLeft',
    cell,
    fromHeading,
    toHeading,
    stationary: true,
    startTime,
    endTime,
    turnDetection,
  }
}

function stationarySegment({ type, cell, heading, startTime, endTime }) {
  return {
    type,
    cell,
    fromHeading: heading,
    toHeading: heading,
    heading,
    stationary: true,
    startTime,
    endTime,
    carrying: false,
  }
}

function withCarryState(segment, carrying) {
  return {
    ...segment,
    carrying,
  }
}

export function inferAgentYaw(agent, fallbackYaw = 0) {
  const resultYaw = movementYaw(
    agent?.previous_action_result?.source_position,
    agent?.previous_action_result?.target_position,
  )
  if (resultYaw !== null) return resultYaw
  const directionYaw = movementYaw(agent?.position, agent?.intended_action?.target)
  if (directionYaw !== null) return directionYaw
  return fallbackYaw
}

export function buildAgentVisualSchedule({
  agent,
  previousAgent,
  stepDuration,
  previousYaw = 0,
}) {
  const safeStepDuration = Math.max(0.08, stepDuration)
  const result = successfulActionResult(agent)
  if (!result) return { segments: [], startTime: 0, turnDetection: null }
  const currentCarrying = Boolean(agent?.carrying_item_id)
  const previousCarrying = Boolean(previousAgent?.carrying_item_id)

  const actionType = result.action?.type
  if (actionType === 'move') {
    const currentMove = successfulMoveResult(agent)
    if (!currentMove) return { segments: [], startTime: 0, turnDetection: null }

    const from = currentMove.source_position
    const to = currentMove.target_position
    const toYaw = movementYaw(from, to) ?? previousYaw
    const previousMove = successfulMoveResult(previousAgent)
    const previousMoveYaw = previousMove
      ? movementYaw(previousMove.source_position, previousMove.target_position)
      : null
    const hasContiguousPreviousMove = Boolean(
      previousMove
      && previousMoveYaw !== null
      && sameCell(previousMove.target_position, from),
    )
    const fromYaw = hasContiguousPreviousMove ? previousMoveYaw : toYaw
    const turnDetection = buildTurnDetection({
      previousMove: hasContiguousPreviousMove ? previousMove : null,
      currentMove,
      incomingYaw: fromYaw,
      outgoingYaw: toYaw,
    })

    if (turnDetection.detectedTurn) {
      const turnStart = hasContiguousPreviousMove ? safeStepDuration : 0
      const turnEnd = turnStart + safeStepDuration * TURN_PORTION_OF_STEP
      const walkEnd = hasContiguousPreviousMove ? safeStepDuration * 2 : safeStepDuration
      const segments = []
      if (hasContiguousPreviousMove) {
        segments.push(
          withCarryState(
            walkSegment({
              from: previousMove.source_position,
              to: previousMove.target_position,
              heading: fromYaw,
              startTime: 0,
              endTime: turnStart,
              turnDetection,
            }),
            previousCarrying,
          ),
        )
      }
      segments.push(
        withCarryState(
          turnLeftSegment({
            cell: from,
            fromHeading: fromYaw,
            toHeading: toYaw,
            startTime: turnStart,
            endTime: turnEnd,
            turnDetection,
          }),
          currentCarrying,
        ),
        withCarryState(
          walkSegment({
            from,
            to,
            heading: toYaw,
            startTime: turnEnd,
            endTime: walkEnd,
            turnDetection,
          }),
          currentCarrying,
        ),
      )
      return {
        startTime: turnStart,
        turnDetection,
        segments,
      }
    }

    return {
      startTime: 0,
      turnDetection,
      segments: [
        withCarryState(
          walkSegment({
            from,
            to,
            heading: toYaw,
            startTime: 0,
            endTime: safeStepDuration,
            turnDetection,
          }),
          currentCarrying,
        ),
      ],
    }
  }

  if (actionType === 'pickup' || actionType === 'place') {
    const cell = stationaryActionCell(agent, result)
    const heading = stationaryActionYaw(result, previousYaw)
    return {
      startTime: 0,
      turnDetection: null,
      segments: [
        withCarryState(
          stationarySegment({
            type: actionType,
            cell,
            heading,
            startTime: 0,
            endTime: safeStepDuration,
          }),
          currentCarrying,
        ),
      ],
    }
  }

  return { segments: [], startTime: 0, turnDetection: null }
}

export function buildAgentVisualSegments(options) {
  return buildAgentVisualSchedule(options).segments
}

export class AgentAnimationController {
  constructor({
    group,
    board,
    cellSize = CELL_SIZE,
    agentId = 'agent',
  }) {
    this.group = group
    this.board = board
    this.cellSize = cellSize
    this.agentId = agentId
    this.mixer = null
    this.character = null
    this.actions = {}
    this.currentActionName = ''
    this.currentSegmentType = 'idle'
    this.segments = []
    this.elapsed = 0
    this.activeSegmentKey = ''
    this.yaw = 0
    this.debugEnabled = false
    this.lastTurnDetection = null
    this.isCarrying = false
  }

  setBoard(board) {
    this.board = board
  }

  getYaw() {
    return this.yaw
  }

  setDebugEnabled(enabled) {
    this.debugEnabled = Boolean(enabled)
  }

  setCarrying(carrying) {
    const nextCarrying = Boolean(carrying)
    if (this.isCarrying === nextCarrying) return
    this.isCarrying = nextCarrying
    if (!this.segments.length && this.currentSegmentType === 'idle') {
      this.transitionToIdle()
    }
  }

  configureAnimations({ character, clips }) {
    this.disposeAnimations()
    if (!character) return

    this.character = character
    this.mixer = new THREE.AnimationMixer(character)
    this.actions = {
      walk: this.createAction('walk', prepareClip(clips.walk, 'walk')),
      carryWalk: this.createAction('carryWalk', prepareClip(clips.carryWalk, 'carryWalk')),
      idle: this.createAction('idle', prepareClip(clips.idle, 'idle')),
      carryIdle: this.createAction('carryIdle', prepareClip(clips.carryIdle, 'carryIdle')),
      pickup: this.createAction('pickup', prepareClip(clips.pickup, 'pickup')),
      turnLeft: this.createAction('turnLeft', prepareClip(clips.turnLeft, 'turnLeft')),
    }
    this.transitionToIdle()
  }

  createAction(name, clip) {
    if (!this.mixer || !clip) return null
    const action = this.mixer.clipAction(clip)
    action.enabled = true
    action.clampWhenFinished = false
    action.loop = THREE.LoopRepeat
    return { name, clip, action }
  }

  disposeAnimations() {
    if (this.mixer) {
      this.mixer.stopAllAction()
      if (this.character) this.mixer.uncacheRoot(this.character)
    }
    this.mixer = null
    this.character = null
    this.actions = {}
    this.currentActionName = ''
    this.currentSegmentType = 'idle'
    this.activeSegmentKey = ''
  }

  dispose() {
    this.disposeAnimations()
    this.segments = []
  }

  resetPose({ cell, yaw = this.yaw, board = this.board }) {
    this.setBoard(board)
    this.segments = []
    this.elapsed = 0
    this.activeSegmentKey = ''
    this.currentSegmentType = 'idle'
    this.transitionToIdle()
    this.applyPose(cell, yaw)
  }

  setSchedule(segments, {
    board = this.board,
    fallbackCell = [0, 0],
    fallbackYaw = this.yaw,
    startTime = 0,
  } = {}) {
    this.setBoard(board)
    this.segments = segments
    this.activeSegmentKey = ''
    this.lastTurnDetection = segments.find((segment) => segment.turnDetection)?.turnDetection ?? null

    if (!segments.length) {
      this.resetPose({ cell: fallbackCell, yaw: fallbackYaw, board })
      return
    }

    const firstStartTime = segments[0].startTime
    const endTime = segments[segments.length - 1].endTime
    this.elapsed = Math.max(firstStartTime, Math.min(startTime, endTime))
    this.applyAtTime(this.elapsed)
  }

  update(delta, { advance = true } = {}) {
    if (!advance) return

    if (!this.segments.length) {
      this.mixer?.update(delta)
      this.pinCharacterRoot()
      return
    }

    let remaining = Math.max(0, delta)
    while (remaining > 0 && this.segments.length) {
      const segment = this.activeSegmentAtTime(this.elapsed)
      if (!segment) break

      this.activateSegment(segment)
      const available = Math.max(0, segment.endTime - this.elapsed)
      const step = Math.min(remaining, available)

      if (step > 0) {
        this.mixer?.update(step)
        this.elapsed = Math.min(segment.endTime, this.elapsed + step)
        this.applySegmentPose(segment, segmentProgress(segment, this.elapsed))
        this.pinCharacterRoot()
      }

      if (this.elapsed >= segment.endTime - MIN_SEGMENT_SECONDS) {
        this.completeSegment(segment)
        if (this.isFinalSegment(segment)) {
          this.finishSchedule(segment)
          break
        }
        this.elapsed = segment.endTime
        this.activeSegmentKey = ''
      }

      if (step <= 0) break
      remaining -= step
    }
  }

  applyAtTime(time) {
    const segment = this.activeSegmentAtTime(time)
    if (!segment) return
    this.activateSegment(segment)
    this.applySegmentPose(segment, segmentProgress(segment, time))
    this.pinCharacterRoot()
  }

  activeSegmentAtTime(time) {
    if (!this.segments.length) return null
    const lastIndex = this.segments.length - 1
    return this.segments.find((segment, index) => (
      time >= segment.startTime
      && (time < segment.endTime || (index === lastIndex && time <= segment.endTime))
    )) ?? this.segments[lastIndex]
  }

  isFinalSegment(segment) {
    return this.segments[this.segments.length - 1] === segment
  }

  activateSegment(segment) {
    const key = `${segment.type}:${segment.startTime}:${segment.endTime}`
    if (this.activeSegmentKey === key) return
    this.activeSegmentKey = key
    this.currentSegmentType = segment.type

    if (segment.type === 'walk') {
      const actionName = segment.carrying ? 'carryWalk' : 'walk'
      this.setLogicalYaw(segment.heading ?? segment.toHeading ?? this.yaw)
      this.transitionToAction(actionName, {
        duration: segmentDuration(segment),
        loop: THREE.LoopRepeat,
        reset: this.currentActionName !== actionName,
        exclusive: true,
        segment,
      })
      return
    }

    if (segment.type === 'turnLeft') {
      this.setLogicalYaw(segment.fromHeading ?? this.yaw)
      this.transitionToAction('turnLeft', {
        duration: segmentDuration(segment),
        loop: THREE.LoopOnce,
        reset: true,
        clampWhenFinished: true,
        exclusive: true,
        segment,
      })
      return
    }

    if (segment.type === 'pickup') {
      this.setLogicalYaw(segment.heading ?? segment.toHeading ?? this.yaw)
      this.transitionToAction('pickup', {
        duration: segmentDuration(segment),
        loop: THREE.LoopOnce,
        reset: true,
        clampWhenFinished: true,
        exclusive: true,
        segment,
      })
      return
    }

    if (segment.type === 'place') {
      this.setLogicalYaw(segment.heading ?? segment.toHeading ?? this.yaw)
      this.transitionToAction('pickup', {
        duration: segmentDuration(segment),
        loop: THREE.LoopOnce,
        reset: true,
        reverse: true,
        clampWhenFinished: true,
        exclusive: true,
        segment,
      })
      return
    }

    this.transitionToIdle()
  }

  transitionToAction(name, {
    duration,
    loop,
    reset = true,
    reverse = false,
    clampWhenFinished = false,
    exclusive = false,
    segment = null,
  }) {
    const entry = this.actions[name]
    if (!entry) {
      this.activeSegmentKey = ''
      this.fadeOutCurrent(null)
      this.currentActionName = 'idle'
      this.currentSegmentType = 'idle'
      return
    }

    const { action, clip } = entry
    const scheduledDuration = Math.max(MIN_SEGMENT_SECONDS, duration)
    const sourceClipDuration = clipDuration(clip)
    const playbackScale = sourceClipDuration / scheduledDuration
    action.enabled = true
    action.paused = false
    action.clampWhenFinished = clampWhenFinished
    action.setLoop(loop, loop === THREE.LoopOnce ? 1 : Infinity)
    action.setEffectiveWeight(1)
    action.setEffectiveTimeScale(reverse ? -playbackScale : playbackScale)

    if (this.currentActionName !== name) {
      if (exclusive) {
        this.stopOtherActions(action)
      } else {
        this.fadeOutCurrent(action)
        action.fadeIn(FADE_SECONDS)
      }
    }

    if (reset || this.currentActionName !== name) {
      action.reset()
      action.time = reverse ? sourceClipDuration : 0
    }

    action.play()
    this.evaluateCurrentAnimationPose()
    this.currentActionName = name
    this.debugAnimationStart(action, segment, {
      sourceClipDuration,
      scheduledDuration,
      timeScale: Math.abs(action.getEffectiveTimeScale()),
    })
  }

  transitionToIdle() {
    this.currentSegmentType = 'idle'
    const idleActionName = this.isCarrying ? 'carryIdle' : 'idle'
    const idleEntry = this.actions[idleActionName]
    if (!idleEntry) {
      this.fadeOutCurrent(null)
      this.currentActionName = 'idle'
      return
    }
    this.transitionToAction(idleActionName, {
      duration: clipDuration(idleEntry.clip),
      loop: THREE.LoopRepeat,
      reset: this.currentActionName !== idleActionName,
      exclusive: true,
      segment: {
        type: 'idle',
        carrying: this.isCarrying,
      },
    })
  }

  fadeOutCurrent(nextAction) {
    const currentEntry = this.actions[this.currentActionName]
    const currentAction = currentEntry?.action
    if (currentAction && currentAction !== nextAction) currentAction.fadeOut(FADE_SECONDS)
  }

  stopOtherActions(nextAction) {
    Object.values(this.actions).forEach((entry) => {
      const action = entry?.action
      if (!action || action === nextAction) return
      action.fadeOut(0.05)
      action.setEffectiveWeight(0)
      action.stop()
      action.enabled = false
    })
  }

  evaluateCurrentAnimationPose() {
    this.mixer?.update(0)
    this.pinCharacterRoot()
  }

  completeSegment(segment) {
    if (segment.type === 'turnLeft') {
      this.setLogicalYaw(segment.toHeading ?? this.yaw)
      return
    }
    if (segment.heading !== undefined) {
      this.setLogicalYaw(segment.heading)
    }
  }

  finishSchedule(finalSegment) {
    this.applySegmentPose(finalSegment, 1)
    this.segments = []
    this.activeSegmentKey = ''
    this.currentSegmentType = 'idle'
    this.transitionToIdle()
  }

  applySegmentPose(segment, progress) {
    if (segment.type === 'walk') {
      const from = gridToWorld(segment.from, this.board, this.cellSize, 0)
      const to = gridToWorld(segment.to, this.board, this.cellSize, 0)
      const position = new THREE.Vector3().fromArray(from).lerp(new THREE.Vector3().fromArray(to), progress)
      this.applyWorldPosition(position)
      return
    }

    const cell = segment.cell ?? segment.from ?? segment.to
    this.applyCellPosition(cell)
  }

  applyPose(cell, yaw) {
    this.applyCellPosition(cell)
    this.setLogicalYaw(yaw)
  }

  applyCellPosition(cell) {
    this.applyWorldPosition(new THREE.Vector3().fromArray(gridToWorld(cell, this.board, this.cellSize, 0)))
  }

  applyWorldPosition(position) {
    if (!this.group) return
    this.group.position.copy(position)
  }

  setLogicalYaw(yaw) {
    if (!this.group || yaw === null || yaw === undefined || Number.isNaN(yaw)) return
    this.group.rotation.y = yaw
    this.yaw = yaw
  }

  pinCharacterRoot() {
    if (!this.character) return
    this.character.position.set(0, 0, 0)
  }

  getDebugState() {
    const actionEntry = this.actions[this.currentActionName]
    const action = actionEntry?.action ?? null
    const clip = action?.getClip?.() ?? actionEntry?.clip ?? null
    const turnDetection = this.lastTurnDetection ?? {}
    return {
      visualState: VISUAL_STATES[this.currentSegmentType] ?? VISUAL_STATES[this.currentActionName] ?? 'IDLE',
      activeClip: clip?.name ?? '-',
      clipTime: action ? roundTime(action.time) : 0,
      clipDuration: clip ? roundTime(clip.duration) : 0,
      actionWeight: action ? roundTime(action.getEffectiveWeight()) : 0,
      actionEnabled: Boolean(action?.enabled),
      actionTimeScale: action ? roundTime(action.getEffectiveTimeScale()) : 0,
      actionRunning: Boolean(action?.isRunning?.()),
      turnDetected: Boolean(turnDetection.detectedTurn),
      incomingDirection: turnDetection.incomingDirection ?? '-',
      outgoingDirection: turnDetection.outgoingDirection ?? '-',
      turnKind: turnDetection.turnKind ?? '-',
    }
  }

  debugAnimationStart(action, segment, timing) {
    if (!this.debugEnabled) return
    const clip = action.getClip()
    console.log('[Agent animation start]', {
      agentId: this.agentId,
      event: 'animation-start',
      visualState: VISUAL_STATES[segment?.type] ?? segment?.type ?? this.currentActionName,
      segmentType: segment?.type ?? null,
      clip: clip.name,
      duration: clip.duration,
      scheduledDuration: roundTime(timing.scheduledDuration),
      enabled: action.enabled,
      weight: action.getEffectiveWeight(),
      timeScale: action.getEffectiveTimeScale(),
      time: action.time,
      loop: action.loop,
      isRunning: action.isRunning(),
      segmentStartTime: segment?.startTime ?? null,
      segmentEndTime: segment?.endTime ?? null,
      waypointCell: segment?.cell ?? null,
      incomingDirection: segment?.turnDetection?.incomingDirection,
      outgoingDirection: segment?.turnDetection?.outgoingDirection,
      turnKind: segment?.turnDetection?.turnKind,
      turnDetected: Boolean(segment?.turnDetection?.detectedTurn),
      overridingActions: Object.entries(this.actions)
        .filter(([, entry]) => entry?.action !== action)
        .map(([name, entry]) => ({
          name,
          enabled: Boolean(entry?.action?.enabled),
          weight: entry?.action ? entry.action.getEffectiveWeight() : 0,
          timeScale: entry?.action ? entry.action.getEffectiveTimeScale() : 0,
          time: entry?.action?.time ?? 0,
          isRunning: Boolean(entry?.action?.isRunning?.()),
        })),
    })
  }

}
